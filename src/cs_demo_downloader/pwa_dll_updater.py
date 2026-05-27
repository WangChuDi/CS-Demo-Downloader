"""Download the latest PvpAlive.dll from the official client ZIP by HTTP Range."""
from __future__ import annotations

import binascii
import json
import os
import struct
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urljoin

import requests


LATEST_YML_URL = "https://client.wmpvp.com/download/latest.yml"
TARGET_MEMBER = "plugin/PvpAlive.dll"
MAX_EOCD_SEARCH = 66000


class PvpAliveUpdateError(RuntimeError):
    """Raised when the PvpAlive.dll update flow fails."""


@dataclass(frozen=True)
class CentralDirectoryInfo:
    offset: int
    size: int
    entry_count: int


@dataclass(frozen=True)
class ZipEntry:
    filename: str
    flags: int
    compression_method: int
    crc32: int
    compressed_size: int
    uncompressed_size: int
    local_header_offset: int


@dataclass(frozen=True)
class LatestClientInfo:
    latest_yml_url: str
    version: str
    installer_path: str
    zip_url: str


def _parse_simple_latest_yml(text: str) -> Dict[str, object]:
    data: Dict[str, object] = {}
    files: List[Dict[str, str]] = []
    in_files = False
    current_file: Dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped == 'files:':
            in_files = True
            continue
        if in_files and stripped.startswith('- '):
            current_file = {}
            files.append(current_file)
            remainder = stripped[2:].strip()
            if ':' in remainder:
                key, value = remainder.split(':', 1)
                current_file[key.strip()] = value.strip().strip("'\"")
            continue
        if in_files and raw_line.startswith(' ') and current_file is not None and ':' in stripped:
            key, value = stripped.split(':', 1)
            current_file[key.strip()] = value.strip().strip("'\"")
            continue
        in_files = False
        if ':' in stripped:
            key, value = stripped.split(':', 1)
            data[key.strip()] = value.strip().strip("'\"")

    if files:
        data['files'] = files
    return data


def fetch_latest_client_info(latest_yml_url: str = LATEST_YML_URL, timeout: int = 30) -> LatestClientInfo:
    try:
        response = requests.get(latest_yml_url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise PvpAliveUpdateError(f"latest.yml download failed: {exc}") from exc

    data = _parse_simple_latest_yml(response.text)
    version = str(data.get('version') or '').strip()
    filename = str(data.get('path') or '').strip()
    if not filename:
        files = data.get('files')
        if isinstance(files, list) and files and isinstance(files[0], dict):
            filename = str(files[0].get('url') or '').strip()
    if not filename:
        raise PvpAliveUpdateError("latest.yml does not contain path or files[0].url")
    if not filename.lower().endswith('.exe'):
        raise PvpAliveUpdateError(f"latest.yml path is not an .exe file: {filename}")

    zip_name = filename[:-4] + '.zip'
    return LatestClientInfo(
        latest_yml_url=latest_yml_url,
        version=version,
        installer_path=filename,
        zip_url=urljoin(latest_yml_url, zip_name),
    )


def fetch_latest_zip_url(latest_yml_url: str = LATEST_YML_URL, timeout: int = 30) -> str:
    return fetch_latest_client_info(latest_yml_url, timeout).zip_url


def http_head(url: str, timeout: int) -> Dict[str, str]:
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise PvpAliveUpdateError(f"ZIP HEAD failed: {exc}") from exc
    return dict(response.headers)


def http_range(url: str, start: int, end: int, timeout: int) -> bytes:
    if start < 0 or end < start:
        raise PvpAliveUpdateError(f"invalid Range requested: bytes={start}-{end}")
    try:
        response = requests.get(url, headers={'Range': f'bytes={start}-{end}'}, timeout=timeout)
    except requests.RequestException as exc:
        raise PvpAliveUpdateError(f"Range request failed for bytes={start}-{end}: {exc}") from exc
    if response.status_code != 206:
        raise PvpAliveUpdateError(f"Range request bytes={start}-{end} did not return 206")
    return response.content


def _content_length(headers: Dict[str, str]) -> int:
    value = None
    for key, header_value in headers.items():
        if key.lower() == 'content-length':
            value = header_value
            break
    if not value:
        raise PvpAliveUpdateError("ZIP does not provide Content-Length")
    try:
        return int(value)
    except ValueError as exc:
        raise PvpAliveUpdateError(f"invalid ZIP Content-Length: {value}") from exc


def find_eocd(tail_bytes: bytes, absolute_tail_start: int) -> CentralDirectoryInfo:
    index = tail_bytes.rfind(b'PK\x05\x06')
    if index < 0:
        raise PvpAliveUpdateError("EOCD not found in ZIP tail")
    if len(tail_bytes) - index < 22:
        raise PvpAliveUpdateError("central directory parsing failed: truncated EOCD")
    fields = struct.unpack_from('<4s4H2LH', tail_bytes, index)
    _, disk_no, cd_disk, entries_disk, entries_total, cd_size, cd_offset, comment_len = fields
    if disk_no != 0 or cd_disk != 0 or entries_disk != entries_total:
        raise PvpAliveUpdateError("multi-disk ZIP archives are not supported")
    if len(tail_bytes) - index < 22 + comment_len:
        raise PvpAliveUpdateError("central directory parsing failed: truncated ZIP comment")
    if cd_size == 0xffffffff or cd_offset == 0xffffffff or entries_total == 0xffff:
        raise PvpAliveUpdateError("ZIP64 not supported")
    return CentralDirectoryInfo(offset=cd_offset, size=cd_size, entry_count=entries_total)


def _decode_filename(raw: bytes, flags: int) -> str:
    if flags & 0x800:
        return raw.decode('utf-8')
    for encoding in ('utf-8', 'cp437', 'gbk'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('cp437', errors='replace')


def parse_central_directory(cd_bytes: bytes, entry_count: int | None = None) -> List[ZipEntry]:
    entries: List[ZipEntry] = []
    offset = 0
    while offset < len(cd_bytes):
        if len(cd_bytes) - offset < 46:
            raise PvpAliveUpdateError("central directory parsing failed: truncated entry")
        if cd_bytes[offset:offset + 4] != b'PK\x01\x02':
            raise PvpAliveUpdateError("central directory parsing failed: invalid entry signature")
        fields = struct.unpack_from('<4s2H4H3L5H2L', cd_bytes, offset)
        (
            _, _version_made, _version_needed, flags, method, _mtime, _mdate,
            crc32, compressed_size, uncompressed_size, filename_len, extra_len,
            comment_len, _disk_start, _internal_attr, _external_attr,
            local_header_offset,
        ) = fields
        if compressed_size == 0xffffffff or uncompressed_size == 0xffffffff or local_header_offset == 0xffffffff:
            raise PvpAliveUpdateError("ZIP64 entry not supported")
        name_start = offset + 46
        name_end = name_start + filename_len
        extra_end = name_end + extra_len
        comment_end = extra_end + comment_len
        if comment_end > len(cd_bytes):
            raise PvpAliveUpdateError("central directory parsing failed: entry exceeds directory size")
        filename = _decode_filename(cd_bytes[name_start:name_end], flags).replace('\\', '/')
        entries.append(ZipEntry(
            filename=filename,
            flags=flags,
            compression_method=method,
            crc32=crc32,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            local_header_offset=local_header_offset,
        ))
        offset = comment_end
    if entry_count is not None and len(entries) != entry_count:
        raise PvpAliveUpdateError(
            f"central directory parsing failed: expected {entry_count} entries, got {len(entries)}"
        )
    return entries


def find_zip_entry(entries: Iterable[ZipEntry], member_path: str = TARGET_MEMBER) -> ZipEntry:
    normalized_target = member_path.replace('\\', '/')
    plugin_dlls = []
    for entry in entries:
        normalized = entry.filename.replace('\\', '/')
        if normalized == normalized_target:
            return entry
        if normalized.lower().startswith('plugin/') and normalized.lower().endswith('.dll'):
            plugin_dlls.append(normalized)
    choices = ', '.join(plugin_dlls) if plugin_dlls else 'none'
    raise PvpAliveUpdateError(f"{normalized_target} not found in ZIP; available plugin/*.dll files: {choices}")


def fetch_and_extract_entry(zip_url: str, entry: ZipEntry, timeout: int = 30) -> bytes:
    header = http_range(zip_url, entry.local_header_offset, entry.local_header_offset + 29, timeout)
    if len(header) != 30 or header[:4] != b'PK\x03\x04':
        raise PvpAliveUpdateError("local file header signature is invalid")
    filename_len, extra_len = struct.unpack_from('<HH', header, 26)
    data_start = entry.local_header_offset + 30 + filename_len + extra_len
    data_end = data_start + entry.compressed_size - 1
    compressed_data = http_range(zip_url, data_start, data_end, timeout)

    if entry.compression_method == 0:
        data = compressed_data
    elif entry.compression_method == 8:
        try:
            data = zlib.decompress(compressed_data, -zlib.MAX_WBITS)
        except zlib.error as exc:
            raise PvpAliveUpdateError(f"deflate decompression failed: {exc}") from exc
    else:
        raise PvpAliveUpdateError(f"unsupported compression method: {entry.compression_method}")

    if len(data) != entry.uncompressed_size:
        raise PvpAliveUpdateError(
            f"uncompressed size mismatch: expected {entry.uncompressed_size}, got {len(data)}"
        )
    actual_crc = binascii.crc32(data) & 0xffffffff
    if actual_crc != entry.crc32:
        raise PvpAliveUpdateError(f"CRC32 mismatch: expected {entry.crc32:08x}, got {actual_crc:08x}")
    return data


def download_zip_member_by_range(zip_url: str, member_path: str = TARGET_MEMBER, timeout: int = 30) -> bytes:
    headers = http_head(zip_url, timeout)
    total_size = _content_length(headers)
    tail_start = max(0, total_size - MAX_EOCD_SEARCH)
    tail = http_range(zip_url, tail_start, total_size - 1, timeout)
    cd_info = find_eocd(tail, tail_start)
    cd_end = cd_info.offset + cd_info.size - 1
    cd_bytes = http_range(zip_url, cd_info.offset, cd_end, timeout)
    entries = parse_central_directory(cd_bytes, cd_info.entry_count)
    entry = find_zip_entry(entries, member_path)
    return fetch_and_extract_entry(zip_url, entry, timeout)


def atomic_write(path: str | os.PathLike[str], data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(target.parent), delete=False) as temp_file:
            temp_name = temp_file.name
            temp_file.write(data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name:
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise PvpAliveUpdateError(f"temporary file write or atomic replace failed: {exc}") from exc


def _metadata_path(target_path: str | os.PathLike[str]) -> Path:
    return Path(str(target_path) + '.json')


def _read_metadata(path: Path) -> Dict[str, object]:
    try:
        with open(path, 'r', encoding='utf-8') as metadata_file:
            data = json.load(metadata_file)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        raise PvpAliveUpdateError(f"cached DLL metadata read failed: {exc}") from exc
    if not isinstance(data, dict):
        raise PvpAliveUpdateError("cached DLL metadata is not a JSON object")
    return data


def _write_metadata(path: Path, metadata: Dict[str, object]) -> None:
    atomic_write(path, json.dumps(metadata, indent=2, sort_keys=True).encode('utf-8'))


def _metadata_matches(metadata: Dict[str, object], info: LatestClientInfo, target_path: Path) -> bool:
    return (
        target_path.exists()
        and metadata.get('latest_yml_url') == info.latest_yml_url
        and metadata.get('version') == info.version
        and metadata.get('installer_path') == info.installer_path
        and metadata.get('zip_url') == info.zip_url
    )


def update_cached_pvp_alive_dll(
    latest_yml_url: str = LATEST_YML_URL,
    target_path: str = "cache/PvpAlive.dll",
    timeout: int = 30,
    force: bool = False,
) -> str:
    """Fetch latest client ZIP URL, range-extract plugin/PvpAlive.dll, and atomically cache it."""
    info = fetch_latest_client_info(latest_yml_url, timeout)
    target = Path(target_path)
    metadata_file = _metadata_path(target)
    metadata = _read_metadata(metadata_file)
    if not force and _metadata_matches(metadata, info, target):
        return str(target)

    data = download_zip_member_by_range(info.zip_url, TARGET_MEMBER, timeout)
    atomic_write(target_path, data)
    _write_metadata(metadata_file, {
        'latest_yml_url': info.latest_yml_url,
        'version': info.version,
        'installer_path': info.installer_path,
        'zip_url': info.zip_url,
        'dll_path': str(target),
        'dll_size': len(data),
        'dll_crc32': f"{binascii.crc32(data) & 0xffffffff:08x}",
        'updated_at': int(time.time()),
    })
    return str(target)
