#!/usr/bin/env python3
"""Sync private signer wheels and extracted binaries into the public repo."""
from __future__ import annotations

import argparse
import tempfile
import fnmatch
import hashlib
import json
import platform
import shutil
import sys
import zipfile
from pathlib import Path
from typing import cast

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_private_signer_wheel import COMPILED_SUFFIXES, verify_wheel


PACKAGE_PREFIX = 'cs_demo_pwa_signer-'
MANIFEST_NAME = 'manifest.json'


def normalize_machine(machine: str) -> str:
    value = machine.lower().replace('-', '_')
    aliases = {
        'amd64': 'x86_64',
        'x64': 'x86_64',
        'arm64': 'aarch64',
    }
    return aliases.get(value, value)


def interpreter_tag() -> str:
    return f'cp{sys.version_info.major}{sys.version_info.minor}'


def wheel_arch_for_system(system: str, machine: str) -> str:
    normalized = normalize_machine(machine)
    if system == 'windows':
        if normalized == 'x86_64':
            return 'amd64'
        if normalized == 'aarch64':
            return 'arm64'
    if system == 'darwin' and normalized == 'aarch64':
        return 'arm64'
    return normalized


def expected_platform_tags() -> list[str]:
    system = platform.system().lower()
    arch = wheel_arch_for_system(system, platform.machine())
    if system == 'windows':
        return [f'win_{arch}']
    if system == 'darwin':
        return [f'macosx_*_{arch}', 'macosx_*_universal2']
    if system == 'linux':
        return [f'manylinux_*_{arch}', f'musllinux_*_{arch}', f'linux_{arch}']
    return [f'{system}_{arch}']


def is_platform_compatible(platform_tag: str) -> bool:
    return any(fnmatch.fnmatch(platform_tag, pattern) for pattern in expected_platform_tags())


def wheel_tags(wheel: Path) -> tuple[str, str, str] | None:
    name = wheel.name
    if not name.endswith('.whl') or not name.startswith(PACKAGE_PREFIX):
        return None

    stem = name[:-4]
    parts = stem.split('-')
    if len(parts) < 5:
        return None

    python_tag, abi_tag, platform_tag = parts[-3:]
    return python_tag, abi_tag, platform_tag


def directory_name(python_tag: str, abi_tag: str, platform_tag: str) -> str:
    return f'{python_tag}-{abi_tag}-{platform_tag}'


def clean_vendor_dir(vendor_root: Path):
    if not vendor_root.exists():
        vendor_root.mkdir(parents=True)
        return

    for child in vendor_root.iterdir():
        if child.name == MANIFEST_NAME:
            child.unlink()
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def extension_members(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return [
            name
            for name in archive.namelist()
            if not name.endswith('/')
            and name.startswith('cs_demo_pwa_signer')
            and Path(name).suffix in COMPILED_SUFFIXES
        ]


def sync_private_signer_artifacts(repo: Path, source_wheelhouse: Path, expected_count: int | None = None):
    wheelhouse = repo / 'wheelhouse'
    vendor_root = repo / 'src' / 'cs_demo_downloader' / '_vendor' / 'cs_demo_pwa_signer'
    wheelhouse.mkdir(parents=True, exist_ok=True)
    vendor_root.mkdir(parents=True, exist_ok=True)

    source_wheels = sorted(source_wheelhouse.glob(f'{PACKAGE_PREFIX}*.whl'))
    if expected_count is not None and len(source_wheels) != expected_count:
        raise RuntimeError(f'Expected {expected_count} signer wheels, found {len(source_wheels)} in {source_wheelhouse}')

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        wheel_copies: list[Path] = []
        for source_wheel in source_wheels:
            temp_wheel = temp_dir / source_wheel.name
            _ = shutil.copy2(source_wheel, temp_wheel)
            wheel_copies.append(temp_wheel)

        for existing in wheelhouse.glob(f'{PACKAGE_PREFIX}*.whl'):
            existing.unlink()

        clean_vendor_dir(vendor_root)

        entries: list[dict[str, str]] = []
        seen_tags: set[tuple[str, str, str]] = set()
        for source_wheel in wheel_copies:
            errors = verify_wheel(source_wheel)
            if errors:
                details = '; '.join(errors)
                raise RuntimeError(f'{source_wheel}: {details}')

            tags = wheel_tags(source_wheel)
            if tags is None:
                raise RuntimeError(f'Unrecognized signer wheel filename: {source_wheel.name}')
            python_tag, abi_tag, platform_tag = tags
            tag_key = (python_tag, abi_tag, platform_tag)
            if tag_key in seen_tags:
                raise RuntimeError(f'Duplicate signer wheel tags detected: {tag_key}')
            seen_tags.add(tag_key)

            target_wheel = wheelhouse / source_wheel.name
            _ = shutil.copy2(source_wheel, target_wheel)

            members = extension_members(source_wheel)
            if len(members) != 1:
                raise RuntimeError(f'Expected exactly one compiled signer extension in {source_wheel.name}, found: {members}')

            member = members[0]
            target_dir = vendor_root / directory_name(python_tag, abi_tag, platform_tag)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_extension = target_dir / Path(member).name
            with zipfile.ZipFile(source_wheel) as archive:
                with archive.open(member) as source, target_extension.open('wb') as destination:
                    payload = source.read()
                    _ = destination.write(payload)

            entries.append(
                {
                    'wheel': source_wheel.name,
                    'python_tag': python_tag,
                    'abi_tag': abi_tag,
                    'platform_tag': platform_tag,
                    'directory': target_dir.name,
                    'extension': target_extension.name,
                    'sha256': hashlib.sha256(payload).hexdigest(),
                }
            )

        manifest = {
            'package': 'cs_demo_pwa_signer',
            'entries': sorted(entries, key=lambda entry: (entry['python_tag'], entry['abi_tag'], entry['platform_tag'])),
        }
        manifest_path = vendor_root / MANIFEST_NAME
        _ = manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument('--repo', type=Path, required=True, help='Path to public downloader repository root')
    _ = parser.add_argument('--wheelhouse', type=Path, required=True, help='Path containing built signer wheel artifacts')
    _ = parser.add_argument('--expected-count', type=int, default=None, help='Expected number of signer wheels')
    args = parser.parse_args()
    repo = cast(Path, args.repo)
    wheelhouse = cast(Path, args.wheelhouse)
    expected_count = cast(int | None, args.expected_count)

    try:
        sync_private_signer_artifacts(repo, wheelhouse, expected_count=expected_count)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
