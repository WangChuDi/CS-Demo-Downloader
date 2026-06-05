#!/usr/bin/env python3
"""Select the private PWA signer wheel matching the current interpreter."""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import cast


PACKAGE_PREFIX = 'cs_demo_pwa_signer-'


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
    system = platform.system().lower()
    arch = wheel_arch_for_system(system, platform.machine())
    if system == 'windows':
        return platform_tag == f'win_{arch}'
    if system == 'darwin':
        return platform_tag.startswith('macosx_') and (
            platform_tag.endswith(f'_{arch}') or platform_tag.endswith('_universal2')
        )
    if system == 'linux':
        return platform_tag == f'linux_{arch}' or (
            platform_tag.endswith(f'_{arch}')
            and (platform_tag.startswith('manylinux_') or platform_tag.startswith('musllinux_'))
        )
    return platform_tag == f'{system}_{arch}'


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


def is_compatible(wheel: Path) -> bool:
    tags = wheel_tags(wheel)
    if tags is None:
        return False

    python_tag, abi_tag, platform_tag = tags
    expected_python = interpreter_tag()
    if python_tag != expected_python or abi_tag != expected_python:
        return False


    return is_platform_compatible(platform_tag)


def select_wheel(wheelhouse: Path) -> Path:
    wheels = sorted(wheelhouse.glob(f'{PACKAGE_PREFIX}*.whl'))
    compatible = [wheel for wheel in wheels if is_compatible(wheel)]

    if not compatible:
        expected = f'{interpreter_tag()}-{interpreter_tag()}-[{", ".join(expected_platform_tags())}]'
        available = ', '.join(wheel.name for wheel in wheels) or 'none'
        message = f'No compatible cs-demo-pwa-signer wheel found in {wheelhouse}. Expected tags like {expected}. Available wheels: {available}'
        raise RuntimeError(message)

    if len(compatible) > 1:
        names = ', '.join(wheel.name for wheel in compatible)
        raise RuntimeError(f'Multiple compatible cs-demo-pwa-signer wheels found in {wheelhouse}: {names}')

    return compatible[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument('wheelhouse', nargs='?', type=Path, default=Path('wheelhouse'))
    args = parser.parse_args()
    wheelhouse = cast(Path, args.wheelhouse)

    try:
        print(select_wheel(wheelhouse))
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
