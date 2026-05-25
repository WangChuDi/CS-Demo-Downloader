"""Steam demo URL resolver backed by akiver/boiler-writter.

This module intentionally shells out to a user-provided boiler-writter binary.
It does not bundle or download the binary because boiler-writter is a native
program with separate licensing and platform distribution concerns.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional


class BoilerResolverError(RuntimeError):
    """Raised when boiler-writter cannot resolve a match."""


BOILER_WRITTER_RELEASE_API = "https://api.github.com/repos/akiver/boiler-writter/releases/latest"


MatchListParser = Callable[[str], Optional[str]]


def get_default_cache_dir() -> Path:
    base = os.getenv("CS_DEMO_DOWNLOADER_CACHE")
    if base:
        return Path(base)
    return Path.home() / ".cache" / "cs-demo-downloader"


def get_boiler_platform_asset_name(version: str, system: Optional[str] = None, machine: Optional[str] = None) -> str:
    system_name = (system or platform.system()).lower()
    machine_name = (machine or platform.machine()).lower()
    version_number = version[1:] if version.startswith("v") else version

    if system_name == "windows":
        return f"boiler-writter-win-{version_number}.zip"
    if system_name == "darwin":
        if machine_name in {"arm64", "aarch64"}:
            return f"boiler-writter-mac-arm64-{version_number}.zip"
        return f"boiler-writter-mac-{version_number}.zip"
    if system_name == "linux":
        return f"boiler-writter-linux-{version_number}.zip"

    raise BoilerResolverError(f"Unsupported platform for boiler-writter: {system_name}/{machine_name}")


def find_executable_in_zip(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith('/')]

    candidates = [name for name in names if Path(name).name in {"boiler-writter", "boiler-writter.exe"}]
    if not candidates:
        raise BoilerResolverError("Downloaded boiler-writter archive does not contain an executable")
    return candidates[0]


def verify_sha256(path: Path, expected_digest: str) -> None:
    digest = expected_digest.removeprefix("sha256:").strip().lower()
    if not digest:
        return

    hasher = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            hasher.update(chunk)

    actual = hasher.hexdigest()
    if actual != digest:
        raise BoilerResolverError(f"boiler-writter checksum mismatch: expected {digest}, got {actual}")


def download_boiler_writter(
    cache_dir: Optional[str] = None,
    release_api_url: str = BOILER_WRITTER_RELEASE_API,
    force: bool = False,
) -> str:
    """Download and cache the latest boiler-writter release for this platform."""
    cache_root = Path(cache_dir) if cache_dir else get_default_cache_dir()

    try:
        with urllib.request.urlopen(release_api_url, timeout=30) as response:
            release = json.loads(response.read().decode('utf-8'))
    except OSError as e:
        raise BoilerResolverError(f"Failed to fetch boiler-writter release metadata: {e}") from e

    version = release.get('tag_name')
    if not version:
        raise BoilerResolverError("boiler-writter release metadata is missing tag_name")

    asset_name = get_boiler_platform_asset_name(version)
    assets = release.get('assets', [])
    asset = next((item for item in assets if item.get('name') == asset_name), None)
    if asset is None:
        raise BoilerResolverError(f"boiler-writter release asset not found: {asset_name}")

    install_dir = cache_root / 'boiler-writter' / version
    executable_name = 'boiler-writter.exe' if platform.system().lower() == 'windows' else 'boiler-writter'
    executable_path = install_dir / executable_name
    if executable_path.exists() and not force:
        return str(executable_path)

    install_dir.mkdir(parents=True, exist_ok=True)
    archive_path = install_dir / asset_name
    download_url = asset.get('browser_download_url')
    if not download_url:
        raise BoilerResolverError(f"boiler-writter asset is missing download URL: {asset_name}")

    try:
        urllib.request.urlretrieve(download_url, archive_path)
    except OSError as e:
        raise BoilerResolverError(f"Failed to download boiler-writter asset: {e}") from e

    digest = asset.get('digest', '')
    if digest:
        verify_sha256(archive_path, digest)

    member_name = find_executable_in_zip(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extract(member_name, install_dir)

    extracted_path = install_dir / member_name
    if extracted_path != executable_path:
        extracted_path.replace(executable_path)

    if platform.system().lower() != 'windows':
        executable_path.chmod(executable_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return str(executable_path)


def extract_demo_url_from_match_list(message: object) -> Optional[str]:
    """Extract the first `.dem.bz2` URL from a Steam GC match-list message."""
    matches = getattr(message, 'matches', [])
    for match in matches:
        round_stats = getattr(match, 'roundstatsall', [])
        for stats in round_stats:
            demo_url = getattr(stats, 'map', '')
            if isinstance(demo_url, str) and demo_url.endswith('.dem.bz2'):
                return demo_url
    return None


def extract_demo_url_from_match_list_file(path: str) -> Optional[str]:
    """Extract a demo URL from boiler-writter's protobuf output.

    Requires the optional `csgo` protobuf bindings. `boiler-writter` writes a
    serialized `CMsgGCCStrike15_v2_MatchList`; the demo URL is normally stored
    in `matches[*].roundstatsall[*].map`.
    """
    try:
        pb2 = importlib.import_module('csgo.protobufs.cstrike15_gcmessages_pb2')
    except ImportError as e:
        raise BoilerResolverError(
            "Steam match-list protobuf parser requires optional dependencies. "
            "Install with cs-demo-downloader[steam-boiler]."
        ) from e

    message = pb2.CMsgGCCStrike15_v2_MatchList()
    with open(path, 'rb') as file:
        message.ParseFromString(file.read())

    return extract_demo_url_from_match_list(message)


@dataclass
class BoilerWritterResolver:
    """Resolve Steam share codes using a local boiler-writter executable.

    The executable requires the local Steam client to be running and logged in.
    `resolve_demo_url()` accepts decoded share-code fields and returns the real
    `.dem.bz2` URL when the generated protobuf can be parsed by a parser
    callback.
    """

    executable_path: str = "boiler-writter"
    timeout: int = 60
    match_list_parser: MatchListParser = extract_demo_url_from_match_list_file
    auto_download: bool = False
    cache_dir: Optional[str] = None

    def resolve_demo_url(self, share_code: str, decoded: Dict[str, int]) -> Optional[str]:
        with tempfile.NamedTemporaryFile(delete=False) as output_file:
            output_path = output_file.name

        try:
            self.write_match_list(output_path, decoded)
            return self.match_list_parser(output_path)
        finally:
            try:
                os.remove(output_path)
            except OSError:
                pass

    def write_match_list(self, output_path: str, decoded: Dict[str, int]) -> None:
        required = ("matchid", "outcomeid", "token")
        missing = [key for key in required if key not in decoded]
        if missing:
            raise BoilerResolverError(f"Missing decoded share-code fields: {', '.join(missing)}")

        executable_path = self.executable_path
        if self.auto_download:
            executable_path = download_boiler_writter(cache_dir=self.cache_dir)

        command = [
            executable_path,
            output_path,
            str(decoded["matchid"]),
            str(decoded["outcomeid"]),
            str(decoded["token"]),
        ]

        try:
            subprocess.run(command, check=True, timeout=self.timeout, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise BoilerResolverError(f"boiler-writter executable not found: {self.executable_path}") from e
        except subprocess.TimeoutExpired as e:
            raise BoilerResolverError("boiler-writter timed out while contacting Steam GC") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            detail = f": {stderr}" if stderr else ""
            raise BoilerResolverError(f"boiler-writter failed{detail}") from e

