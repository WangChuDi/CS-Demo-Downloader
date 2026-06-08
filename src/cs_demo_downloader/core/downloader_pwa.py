"""
完美世界电竞平台 Demo 下载器
"""
import json
import random
import subprocess
import sys
import time
import requests
from collections.abc import Callable
from collections.abc import Mapping
from importlib import import_module, machinery, resources, util
from pathlib import Path
from packaging import tags
from typing import Protocol, cast

from .metadata import JSONValue, MatchMetadata, MatchPlayer, MatchTeam, json_object, optional_float, optional_int, optional_str, to_json_value


PWA_MATCH_LIST_URL = 'https://pwaweblogin.wmpvp.com/user-info/recent-ladder-score-list'
PWA_USER_MATCH_LIST_URL = 'https://pwaweblogin.wmpvp.com/user-info/match-list'
PWA_USER_INFO_URL = 'https://pwaweblogin.wmpvp.com/user-info'
PWA_SEASON_LADDER_SCORE_LIST_URL = 'https://pwaweblogin.wmpvp.com/user-info/season-ladder-score-list'
PWA_MATCH_REPORT_URL = 'https://pwaweblogin.wmpvp.com/match-api/report'
PWA_MATCH_ROUND_SIMPLE_LIST_URL = 'https://pwaweblogin.wmpvp.com/match-api/match-round-simple-list'
PWA_PERFECT_MOMENT_URL_PREFIX = 'https://pwacdn.wmpvp.com/client/perfectmoment'
PWA_WEB_API_APPID = 20000
PWA_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) perfectworldarena/1.0.26051411 '
    'Chrome/80.0.3987.163 Electron/8.5.5 Safari/537.36'
)

_public_ip_cache: str | None = None
DemoUrlSigner = Callable[[str, str, str], str]
PwaEtDecryptor = Callable[[str, str], object]
PwaReportFetcher = Callable[[str, str, str], Mapping[str, object] | None]
PwaExtraFetcher = Callable[[str, str, str], Mapping[str, object]]


class PwaSignerUnavailableError(RuntimeError):
    """Raised when the proprietary compiled PWA signer wheel is not installed."""


class PwaDecryptorUnavailableError(RuntimeError):
    """Raised when the private PWA e/t decryptor executable cannot run."""


class _CompiledPwaSigner(Protocol):
    def sign_demo_request(self, randnum: str, timestamp: str, data: str) -> str:
        ...

    def build_x_pwa_signature(self, steamid: str, timestamp: int, ip_addr: str) -> str:
        ...

    def decrypt_pwa_response(self, encrypted: str, token: str) -> str:
        ...


def call_pwa_et_decryptor_exe(
    encrypted: str,
    token: str,
    executable_path: str,
    timeout: int = 10,
) -> str:
    """Call a private executable that decrypts PWA response data.e/data.t.

    The public repository intentionally knows only the process boundary. The
    executable receives stdin JSON with ``e`` and ``t`` fields and must print the
    decrypted JSON text to stdout.
    """
    payload = json.dumps({'e': encrypted, 't': token}, separators=(',', ':'), ensure_ascii=False)
    try:
        completed = subprocess.run(
            (executable_path,),
            input=payload,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PwaDecryptorUnavailableError(f'PWA e/t decryptor execution failed: {exc}') from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or 'no stderr'
        raise PwaDecryptorUnavailableError(f'PWA e/t decryptor failed with exit code {completed.returncode}: {stderr}')

    plaintext = completed.stdout.strip()
    if not plaintext:
        raise PwaDecryptorUnavailableError('PWA e/t decryptor returned empty output')
    return plaintext


def decrypt_pwa_et_payload(
    encrypted: str,
    token: str,
    decryptor: PwaEtDecryptor | None = None,
    decryptor_exe: str | None = None,
    decryptor_timeout: int = 10,
) -> object | None:
    """Decrypt a PWA encrypted response payload through an injected private boundary."""
    decrypted: object | None = None
    try:
        if decryptor is not None:
            decrypted = decryptor(encrypted, token)
    except PwaDecryptorUnavailableError as exc:
        print(f'PWA e/t decryptor unavailable: {exc}')
        return None

    if decrypted is None:
        try:
            decrypted = _load_compiled_signer().decrypt_pwa_response(encrypted, token)
        except (PwaSignerUnavailableError, AttributeError) as exc:
            if not decryptor_exe:
                print(f'PWA e/t decryptor unavailable: {exc}')
                return None

    if decrypted is None and decryptor_exe:
        try:
            decrypted = call_pwa_et_decryptor_exe(encrypted, token, decryptor_exe, timeout=decryptor_timeout)
        except PwaDecryptorUnavailableError as exc:
            print(f'PWA e/t decryptor unavailable: {exc}')
            return None

    if decrypted is None:
        return None
    if isinstance(decrypted, str):
        try:
            return cast(object, json.loads(decrypted))
        except json.JSONDecodeError as exc:
            print(f'PWA e/t decryptor returned invalid JSON: {exc}')
            return None
    return decrypted


def _load_compiled_signer() -> _CompiledPwaSigner:
    try:
        module = import_module('cs_demo_pwa_signer')
    except ModuleNotFoundError as exc:
        if exc.name == 'cs_demo_pwa_signer':
            return _load_vendored_compiled_signer(exc)
        raise

    return cast(_CompiledPwaSigner, cast(object, module))


def _load_vendored_compiled_signer(exc: ModuleNotFoundError) -> _CompiledPwaSigner:
    package_root = resources.files('cs_demo_downloader')
    vendor_dir = package_root.joinpath('_vendor').joinpath('cs_demo_pwa_signer')

    manifest_path = vendor_dir.joinpath('manifest.json')
    if not manifest_path.is_file():
        raise PwaSignerUnavailableError('Bundled PWA signer manifest is missing. Install a matching cs-demo-pwa-signer wheel for this runtime.') from exc

    manifest_data = cast(object, json.loads(manifest_path.read_text(encoding='utf-8')))
    if not isinstance(manifest_data, dict):
        raise PwaSignerUnavailableError('Bundled PWA signer manifest is invalid.') from exc
    manifest = cast(dict[str, object], manifest_data)
    entries_value = manifest.get('entries', [])
    if not isinstance(entries_value, list):
        raise PwaSignerUnavailableError('Bundled PWA signer manifest entries are invalid.') from exc

    supported_tags = list(tags.sys_tags())
    available_entries: dict[tuple[str, str, str], dict[str, str]] = {}
    entries = cast(list[object], entries_value)
    for entry_value in entries:
        if not isinstance(entry_value, dict):
            continue
        entry_object = cast(dict[str, object], entry_value)
        python_tag_value = entry_object.get('python_tag')
        abi_tag_value = entry_object.get('abi_tag')
        platform_tag_value = entry_object.get('platform_tag')
        directory_value = entry_object.get('directory')
        extension_value = entry_object.get('extension')
        if not all(isinstance(value, str) for value in (python_tag_value, abi_tag_value, platform_tag_value, directory_value, extension_value)):
            continue
        python_tag = cast(str, python_tag_value)
        abi_tag = cast(str, abi_tag_value)
        platform_tag = cast(str, platform_tag_value)
        directory = cast(str, directory_value)
        extension = cast(str, extension_value)
        entry = {
            'python_tag': python_tag,
            'abi_tag': abi_tag,
            'platform_tag': platform_tag,
            'directory': directory,
            'extension': extension,
        }
        available_entries[(python_tag, abi_tag, platform_tag)] = entry

    for supported_tag in supported_tags:
        entry = available_entries.get((supported_tag.interpreter, supported_tag.abi, supported_tag.platform))
        if entry is None:
            continue

        candidate = vendor_dir.joinpath(entry['directory']).joinpath(entry['extension'])
        if not candidate.is_file():
            continue

        if Path(entry['extension']).suffix not in set(machinery.EXTENSION_SUFFIXES):
            continue

        with resources.as_file(candidate) as extension_path:
            spec = util.spec_from_file_location('cs_demo_pwa_signer', extension_path)
            if spec is None or spec.loader is None:
                break
            module = util.module_from_spec(spec)
            sys.modules['cs_demo_pwa_signer'] = module
            try:
                spec.loader.exec_module(module)
            except (ImportError, OSError) as load_exc:
                _ = sys.modules.pop('cs_demo_pwa_signer', None)
                message = f"Bundled PWA signer for tag {supported_tag} is not compatible with this runtime: {load_exc}"
                raise PwaSignerUnavailableError(message) from load_exc
            return cast(_CompiledPwaSigner, cast(object, module))

    available_tags = ', '.join(f'{python_tag}-{abi_tag}-{platform_tag}' for python_tag, abi_tag, platform_tag in sorted(available_entries)) or 'none'
    current_tags = ', '.join(f'{tag.interpreter}-{tag.abi}-{tag.platform}' for tag in supported_tags[:10])
    message = (
        "PWA signing requires a compatible compiled signer. "
        f"No bundled signer matches this runtime. Current supported tags include: {current_tags}. "
        f"Bundled signer tags: {available_tags}. Install a matching 'cs-demo-pwa-signer' wheel for this runtime."
    )
    raise PwaSignerUnavailableError(message) from exc


def sign_demo_request(randnum: str, timestamp: str, data: str) -> str:
    """生成 PWA demo URL 请求签名。"""
    return _load_compiled_signer().sign_demo_request(randnum, timestamp, data)


def _build_signed_pwa_params(
    params: Mapping[str, object],
    signer: DemoUrlSigner | None = None,
    randnum: str | None = None,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Build PWA web API parameters with a/r/s/t signature fields."""
    normalized_params = {str(key): str(value) for key, value in params.items()}
    data = '&'.join(f'{key}={value}' for key, value in sorted(normalized_params.items()))
    rand_value = randnum or str(random.randint(100000, 999999))
    timestamp_value = timestamp or str(int(time.time()))
    signature = (signer or sign_demo_request)(rand_value, timestamp_value, data)
    return {
        'a': str(PWA_WEB_API_APPID),
        'r': rand_value,
        's': signature,
        't': timestamp_value,
        **normalized_params,
    }


def _format_query_params(params: Mapping[str, str]) -> str:
    return '&'.join(f'{key}={value}' for key, value in params.items())


def get_public_ip() -> str:
    """获取用于 PWA 下载头签名的公网 IPv4。"""
    global _public_ip_cache
    if _public_ip_cache:
        return _public_ip_cache

    for url in ('https://api.ipify.org/', 'https://ifconfig.me/ip'):
        try:
            ip_addr = requests.get(url, timeout=10).text.strip()
        except requests.RequestException:
            continue

        parts = ip_addr.split('.')
        if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) < 256 for part in parts):
            _public_ip_cache = ip_addr
            return ip_addr

    raise RuntimeError('Unable to determine public IPv4 for PWA download signature')


def build_x_pwa_signature(steamid: str, timestamp: int, ip_addr: str) -> str:
    """生成 PWA 下载请求所需的 X-PWA-Signature 头。"""
    return _load_compiled_signer().build_x_pwa_signature(steamid, timestamp, ip_addr)


def build_download_headers(
    steamid: str,
    public_ip: str | None = None,
    timestamp: int | None = None,
) -> dict[str, str]:
    """构造 PWA demo 文件下载请求头。"""
    ip_addr = public_ip or get_public_ip()
    ts = timestamp if timestamp is not None else int(time.time())
    return {
        'User-Agent': PWA_USER_AGENT,
        'Referer': 'https://client.wmpvp.com',
        'X-PWA-SteamId': steamid,
        'X-PWA-Signature': build_x_pwa_signature(steamid, ts, ip_addr),
        'PwaSteamId': steamid,
        'x-pwa-steamid': steamid,
        'pwasteamid': steamid,
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN',
    }


def get_match_list(
    steamid: str,
    access_token: str,
    size: int = 20,
    signer: DemoUrlSigner | None = None,
    season: str | None = None,
    max_seasons: int = 3,
    et_decryptor: PwaEtDecryptor | None = None,
    et_decryptor_exe: str | None = None,
    et_decryptor_timeout: int = 10,
) -> list[str]:
    """
    获取完美世界比赛列表
    
    Args:
        steamid: Steam ID（如 76561198159976336）
        access_token: 访问令牌
        size: 返回数量限制
    
    Returns:
        match_id 列表
    """
    records = get_match_list_records(
        steamid,
        access_token,
        size=size,
        signer=signer,
        season=season,
        max_seasons=max_seasons,
        et_decryptor=et_decryptor,
        et_decryptor_exe=et_decryptor_exe,
        et_decryptor_timeout=et_decryptor_timeout,
    )
    match_ids: list[str] = []
    for match_record in records:
        match_id = match_record.get('match')
        if isinstance(match_id, str):
            match_ids.append(match_id)
    return match_ids


def get_match_list_records(
    steamid: str,
    access_token: str,
    size: int = 20,
    signer: DemoUrlSigner | None = None,
    acw_tc: str | None = None,
    season: str | None = None,
    max_seasons: int = 3,
    et_decryptor: PwaEtDecryptor | None = None,
    et_decryptor_exe: str | None = None,
    et_decryptor_timeout: int = 10,
) -> list[dict[str, object]]:
    """获取完美世界比赛列表原始记录。"""
    if season is not None:
        recent_records = _get_recent_ladder_records(steamid, access_token, size=size, signer=signer, acw_tc=acw_tc, season=season)
        if recent_records:
            return recent_records
        return _get_user_match_list_records(
            steamid,
            access_token,
            size=size,
            season=season,
            acw_tc=acw_tc,
            et_decryptor=et_decryptor,
            et_decryptor_exe=et_decryptor_exe,
            et_decryptor_timeout=et_decryptor_timeout,
        )

    records = _get_recent_ladder_records(steamid, access_token, size=size, signer=signer, acw_tc=acw_tc, season=None)
    if records:
        return records[:size]

    aggregated: list[dict[str, object]] = []
    for season_record in get_candidate_season_records(steamid, access_token, max_seasons=max_seasons, acw_tc=acw_tc):
        season_name = optional_str(season_record.get('season'))
        if season_name is None:
            continue
        match_count = optional_int(season_record.get('match_count'))
        if match_count == 0:
            continue
        season_records = _get_recent_ladder_records(steamid, access_token, size=size, signer=signer, acw_tc=acw_tc, season=season_name)
        if not season_records:
            season_records = _get_user_match_list_records(
                steamid,
                access_token,
                size=size,
                season=season_name,
                acw_tc=acw_tc,
                et_decryptor=et_decryptor,
                et_decryptor_exe=et_decryptor_exe,
                et_decryptor_timeout=et_decryptor_timeout,
            )
        for record in season_records:
            record.setdefault('season', season_name)
            aggregated.append(record)
            if len(aggregated) >= size:
                return aggregated
    return aggregated


def _get_recent_ladder_records(
    steamid: str,
    access_token: str,
    size: int,
    signer: DemoUrlSigner | None,
    acw_tc: str | None,
    season: str | None,
) -> list[dict[str, object]]:
    signed_params = _build_signed_pwa_params({
        'access_token': access_token,
        'size': str(size),
        'uid': steamid,
        **({'season': season} if season else {}),
    }, signer=signer)
    
    headers = build_pwa_list_headers(steamid, access_token, acw_tc=acw_tc)
    
    try:
        response = requests.get(PWA_MATCH_LIST_URL, params=signed_params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            response_data = cast(object, response.json())
            if not isinstance(response_data, dict):
                return []
            data = cast(dict[str, object], response_data)
            match_data = data.get('data', [])
            if not isinstance(match_data, list):
                return []
            matches = cast(list[object], match_data)
            records: list[dict[str, object]] = []
            for match in matches:
                if not isinstance(match, dict):
                    continue
                records.append({str(key): value for key, value in match.items()})
            return records
        
        return []
    except requests.RequestException as e:
        print(f"Error getting PWA match list: {e}")
        return []


def _get_user_match_list_records(
    steamid: str,
    access_token: str,
    size: int,
    season: str,
    acw_tc: str | None,
    et_decryptor: PwaEtDecryptor | None,
    et_decryptor_exe: str | None,
    et_decryptor_timeout: int,
) -> list[dict[str, object]]:
    """Fetch and decrypt PWA user-info/match-list records for a season."""
    params = {
        'access_token': access_token,
        'uid': steamid,
        'page': '1',
        'page_size': str(size),
        'season': season,
    }
    headers = build_pwa_list_headers(steamid, access_token, acw_tc=acw_tc)

    try:
        response = requests.get(PWA_USER_MATCH_LIST_URL, params=params, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA encrypted match list for season {season}: {e}")
        return []
    if response.status_code != 200:
        return []

    response_data = cast(object, response.json())
    if not isinstance(response_data, dict):
        return []
    data = response_data.get('data')
    if not isinstance(data, Mapping):
        return _coerce_pwa_match_list_records(data)[:size]

    encrypted = optional_str(data.get('e'))
    token = optional_str(data.get('t'))
    if encrypted is None or token is None:
        return _coerce_pwa_match_list_records(data)[:size]

    decrypted = decrypt_pwa_et_payload(
        encrypted,
        token,
        decryptor=et_decryptor,
        decryptor_exe=et_decryptor_exe,
        decryptor_timeout=et_decryptor_timeout,
    )
    return _coerce_pwa_match_list_records(decrypted)[:size]


def _coerce_pwa_match_list_records(payload: object) -> list[dict[str, object]]:
    """Normalize known PWA match-list response shapes to records with a match key."""
    candidate = payload
    if isinstance(candidate, Mapping):
        for key in ('list', 'records', 'matches', 'items', 'data'):
            value = candidate.get(key)
            if isinstance(value, list):
                candidate = value
                break
    if not isinstance(candidate, list):
        return []

    records: list[dict[str, object]] = []
    for row in candidate:
        if not isinstance(row, Mapping):
            continue
        record = {str(key): value for key, value in row.items()}
        match_id = _pwa_record_match_id(record)
        if match_id is not None:
            record['match'] = match_id
        records.append(record)
    return records


def _pwa_record_match_id(record: Mapping[str, object]) -> str | None:
    for key in ('match', 'match_id', 'matchId', 'matchid', 'short_match_id'):
        value = optional_str(record.get(key))
        if value is not None:
            return value
    nested_match = record.get('match_info') or record.get('matchInfo')
    if isinstance(nested_match, Mapping):
        for key in ('match', 'match_id', 'matchId', 'matchid', 'short_match_id'):
            value = optional_str(nested_match.get(key))
            if value is not None:
                return value
    return None


def get_current_season(steamid: str, access_token: str, acw_tc: str | None = None) -> str | None:
    """Best-effort read of the current PWA season from user-info."""
    headers = build_pwa_list_headers(steamid, access_token, acw_tc=acw_tc)
    try:
        response = requests.post(PWA_USER_INFO_URL, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA user info: {e}")
        return None
    if response.status_code != 200:
        return None
    response_data = cast(object, response.json())
    if not isinstance(response_data, dict):
        return None
    data = response_data.get('data')
    if not isinstance(data, Mapping):
        return None
    return optional_str(data.get('season'))


def get_season_ladder_records(
    steamid: str,
    access_token: str,
    ignore_season: str | None = None,
    acw_tc: str | None = None,
) -> list[dict[str, object]]:
    """Fetch PWA historical season ladder records."""
    params = {
        'access_token': access_token,
        'uid': steamid,
    }
    if ignore_season:
        params['ignore_season'] = ignore_season
    headers = build_pwa_list_headers(steamid, access_token, acw_tc=acw_tc)
    try:
        response = requests.get(PWA_SEASON_LADDER_SCORE_LIST_URL, params=params, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA season ladder list: {e}")
        return []
    if response.status_code != 200:
        return []
    response_data = cast(object, response.json())
    if not isinstance(response_data, dict):
        return []
    data = response_data.get('data', [])
    if not isinstance(data, list):
        return []
    records: list[dict[str, object]] = []
    for item in data:
        if isinstance(item, dict):
            records.append({str(key): value for key, value in item.items()})
    return records


def get_candidate_season_records(
    steamid: str,
    access_token: str,
    max_seasons: int = 3,
    acw_tc: str | None = None,
) -> list[dict[str, object]]:
    """Return newest-first candidate seasons, including current season when known."""
    current_season = get_current_season(steamid, access_token, acw_tc=acw_tc)
    history = get_season_ladder_records(steamid, access_token, ignore_season=current_season, acw_tc=acw_tc)
    candidates: list[dict[str, object]] = []
    if current_season is not None:
        candidates.append({'season': current_season})
    candidates.extend(history)
    unique_candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in candidates:
        season_name = optional_str(candidate.get('season'))
        if season_name is None or season_name in seen:
            continue
        seen.add(season_name)
        unique_candidates.append(candidate)
        if len(unique_candidates) >= max_seasons:
            break
    return unique_candidates


def build_pwa_list_headers(
    steamid: str,
    access_token: str,
    acw_tc: str | None = None,
) -> dict[str, str]:
    """Build headers matching PWA client recent-ladder-score-list requests."""
    cookie_parts = [f'steam_cn_token={access_token}']
    if acw_tc:
        cookie_parts.append(f'acw_tc={acw_tc}')
    return {
        'Host': 'pwaweblogin.wmpvp.com',
        'pwasteamid': steamid,
        'PwaSteamId': steamid,
        'x-pwa-steamid': steamid,
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'no-cors',
        'Referer': 'https://client.wmpvp.com/',
        'User-Agent': PWA_USER_AGENT,
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN',
        'Cookie': '; '.join(cookie_parts),
    }


def get_demo_url(
    match_id: str,
    access_token: str,
    cup_id: int = 0,
    signer: DemoUrlSigner | None = None,
) -> str:
    """
    构造完美世界 Demo 下载链接
    
    Args:
        match_id: 比赛 ID
        access_token: 访问令牌
        cup_id: 杯赛 ID，天梯 demo 通常为 0
    
    Returns:
        Demo 下载 URL
    """
    sorted_params = {
        'access_token': access_token,
        'cup_id': str(cup_id),
        'match_id': str(match_id),
    }
    signed_params = _build_signed_pwa_params(sorted_params, signer=signer)
    return (
        f'https://pwaweblogin.wmpvp.com/csgo/demo/{match_id}_{cup_id}.dem'
        f'?{_format_query_params(signed_params)}'
    )


def get_all_demo_urls(
    steamid: str,
    access_token: str,
    size: int = 20,
    signer: DemoUrlSigner | None = None,
    season: str | None = None,
    max_seasons: int = 3,
    et_decryptor: PwaEtDecryptor | None = None,
    et_decryptor_exe: str | None = None,
    et_decryptor_timeout: int = 10,
) -> dict[str, str]:
    """
    获取用户所有比赛的 Demo 下载链接
    
    Args:
        steamid: Steam ID
        access_token: 访问令牌
        size: 返回数量限制
    
    Returns:
        {match_id: demo_url} 字典
    """
    match_ids = get_match_list(
        steamid,
        access_token,
        size,
        signer=signer,
        season=season,
        max_seasons=max_seasons,
        et_decryptor=et_decryptor,
        et_decryptor_exe=et_decryptor_exe,
        et_decryptor_timeout=et_decryptor_timeout,
    )
    demo_urls: dict[str, str] = {}
    
    for match_id in match_ids:
        demo_url = get_demo_url(match_id, access_token, signer=signer)
        demo_urls[match_id] = demo_url
    
    return demo_urls


def fetch_match_report(match_id: str, steamid: str, access_token: str) -> Mapping[str, object] | None:
    """Best-effort PWA match report fetch for metadata enrichment."""
    headers = {
        'Host': 'pwaweblogin.wmpvp.com',
        'x-pwa-steamid': steamid,
        'pwasteamid': steamid,
        'User-Agent': PWA_USER_AGENT,
        'Content-Type': 'application/json;charset=UTF-8',
    }
    payload = {
        'access_token': access_token,
        'match_id': match_id,
    }

    try:
        response = requests.post(PWA_MATCH_REPORT_URL, json=payload, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA match report for match {match_id}: {e}")
        return None

    if response.status_code != 200:
        return None

    response_data = cast(object, response.json())
    if not isinstance(response_data, dict):
        return None
    data = response_data.get('data')
    if not isinstance(data, dict):
        return None
    return {str(key): value for key, value in data.items()}


def fetch_perfect_moment(match_id: str) -> Mapping[str, object] | None:
    """Best-effort fetch for PWA perfect moment lightweight metadata."""
    try:
        response = requests.get(f'{PWA_PERFECT_MOMENT_URL_PREFIX}/{match_id}', timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA perfect moment for match {match_id}: {e}")
        return None

    if response.status_code != 200:
        return None
    data = cast(object, response.json())
    if not isinstance(data, dict):
        return None
    return {str(key): value for key, value in data.items()}


def fetch_match_round_simple_list(match_id: str, steamid: str, access_token: str) -> list[object]:
    """Best-effort fetch for PWA per-round simple stat rows."""
    headers = {
        'Host': 'pwaweblogin.wmpvp.com',
        'x-pwa-steamid': steamid,
        'pwasteamid': steamid,
        'User-Agent': PWA_USER_AGENT,
        'Content-Type': 'application/json;charset=UTF-8',
    }
    payload = {
        'access_token': access_token,
        'match_id': match_id,
    }

    try:
        response = requests.post(PWA_MATCH_ROUND_SIMPLE_LIST_URL, json=payload, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting PWA round simple list for match {match_id}: {e}")
        return []

    if response.status_code != 200:
        return []
    response_data = cast(object, response.json())
    if not isinstance(response_data, dict):
        return []
    data = response_data.get('data', [])
    if not isinstance(data, list):
        return []
    return data


def fetch_match_extra_data(match_id: str, steamid: str, access_token: str) -> Mapping[str, object]:
    """Best-effort fetch for PWA advanced/raw metadata endpoints."""
    extras: dict[str, object] = {}
    perfect_moment = fetch_perfect_moment(match_id)
    if perfect_moment is not None:
        extras['perfect_moment'] = perfect_moment
    round_simple_list = fetch_match_round_simple_list(match_id, steamid, access_token)
    if round_simple_list:
        extras['round_simple_list'] = round_simple_list
    return extras


def build_match_metadata(
    summary: Mapping[str, object],
    demo_url: str,
    report_data: Mapping[str, object] | None = None,
) -> MatchMetadata | None:
    """Build normalized PWA metadata from list and optional report payloads."""
    report_root = report_data or {}
    report_value = report_root.get('report')
    report = report_value if isinstance(report_value, Mapping) else {}
    demo_info_value = report_root.get('demo_info')
    demo_info = demo_info_value if isinstance(demo_info_value, Mapping) else {}

    match_id = optional_str(report.get('match_id')) or optional_str(report_root.get('match_id')) or optional_str(summary.get('match'))
    if match_id is None:
        return None

    report_demo_url = optional_str(demo_info.get('demo_url'))
    normalized_demo_url = report_demo_url or demo_url
    demo_available = _pwa_demo_available(demo_info, normalized_demo_url)

    return MatchMetadata(
        platform='pwa',
        match_id=match_id,
        demo_url=normalized_demo_url,
        demo_available=demo_available,
        map_name=optional_str(report.get('map')) or optional_str(summary.get('map')),
        map_label=optional_str(report.get('map')) or optional_str(summary.get('map_name')),
        location=optional_str(report.get('location')) or optional_str(report.get('server_location')) or optional_str(summary.get('location')),
        match_winner=optional_str(report.get('match_winner')) or optional_str(report.get('winner')) or optional_str(summary.get('match_winner')),
        season=optional_int(report.get('season')) or optional_int(summary.get('season')),
        season_type=optional_str(report.get('season_type')) or optional_str(summary.get('season_type')),
        year=optional_int(report.get('year')) or optional_int(summary.get('year')),
        round_total=optional_int(report.get('round_total')) or optional_int(report.get('round_count')) or optional_int(summary.get('round_total')),
        started_at=optional_int(report.get('match_starttime')) or optional_int(summary.get('match_starttime')),
        ended_at=optional_int(report.get('match_endtime')) or optional_int(summary.get('match_endtime')),
        teams=_pwa_teams(report),
        players=_pwa_players(report),
        match_awards=_pwa_match_awards(report),
        demo_info=_pwa_demo_info(demo_info),
        round_results=_pwa_round_results(report),
        platform_match=_pwa_platform_match(report_root, report),
        raw_summary=json_object(dict(summary)),
        raw_detail=json_object(dict(report_root)),
    )


def get_all_demo_metadata(
    steamid: str,
    access_token: str,
    size: int = 20,
    signer: DemoUrlSigner | None = None,
    report_fetcher: PwaReportFetcher | None = fetch_match_report,
    extra_fetcher: PwaExtraFetcher | None = fetch_match_extra_data,
    season: str | None = None,
    max_seasons: int = 3,
    et_decryptor: PwaEtDecryptor | None = None,
    et_decryptor_exe: str | None = None,
    et_decryptor_timeout: int = 10,
) -> list[MatchMetadata]:
    """获取用户所有 PWA 比赛的规范化 metadata。"""
    metadata: list[MatchMetadata] = []
    for summary in get_match_list_records(
        steamid,
        access_token,
        size,
        signer=signer,
        season=season,
        max_seasons=max_seasons,
        et_decryptor=et_decryptor,
        et_decryptor_exe=et_decryptor_exe,
        et_decryptor_timeout=et_decryptor_timeout,
    ):
        match_id = summary.get('match')
        if not isinstance(match_id, str):
            continue
        cup_id = optional_int(summary.get('cup_id')) or 0
        demo_url = get_demo_url(match_id, access_token, cup_id=cup_id, signer=signer)
        report_data = report_fetcher(match_id, steamid, access_token) if report_fetcher is not None else None
        extra_data = extra_fetcher(match_id, steamid, access_token) if extra_fetcher is not None else {}
        if extra_data:
            report_data = {**dict(report_data or {}), **dict(extra_data)}
        match_metadata = build_match_metadata(summary, demo_url, report_data=report_data)
        if match_metadata is not None:
            metadata.append(match_metadata)
    return metadata


def _pwa_demo_available(demo_info: Mapping[str, object], demo_url: str | None) -> bool | None:
    available = demo_info.get('demo_is_available')
    if isinstance(available, bool):
        return available
    has_demo = demo_info.get('has_demo')
    if isinstance(has_demo, bool):
        return has_demo
    return demo_url is not None


def _pwa_demo_info(demo_info: Mapping[str, object]) -> dict[str, JSONValue]:
    return _pwa_compact_stats(demo_info, {
        'demo_id': 'demo_id',
        'demo_is_available': 'demo_is_available',
        'expire_soon': 'expire_soon',
        'expired': 'expired',
        'has_demo': 'has_demo',
        'is_disabled': 'is_disabled',
    })


def _pwa_round_results(report: Mapping[str, object]) -> list[dict[str, JSONValue]]:
    results_value = report.get('results')
    if not isinstance(results_value, list):
        return []
    results: list[dict[str, JSONValue]] = []
    for row in results_value:
        if isinstance(row, Mapping):
            item = _pwa_compact_stats(row, {
                'round': 'round',
                'win_type': 'win_type',
                'half_match_type': 'half_match_type',
            })
            for normalized_key, source_key in (
                ('win_camp', 'win_camp'),
                ('win_team_id', 'win_team_id'),
                ('lose_team_id', 'lose_team_id'),
                ('bomb_planter', 'bomb_planter'),
                ('bomb_defuser', 'bomb_defuser'),
            ):
                value = optional_str(row.get(source_key))
                if value is not None:
                    item[normalized_key] = value
            results.append(item)
    return results


def _pwa_platform_match(report_root: Mapping[str, object], report: Mapping[str, object]) -> dict[str, JSONValue]:
    stats = _pwa_compact_stats(report_root, {
        'game_abbr': 'game_abbr',
        'match_count': 'match_count',
        'match_number': 'match_number',
        'match_result_type': 'match_result_type',
        'match_winner_id': 'match_winner_id',
        'round_winner_id': 'round_winner_id',
        'short_match_id': 'short_match_id',
    })
    stats.update(_pwa_compact_stats(report, {
        'cup_id': 'cup_id',
        'game_mode': 'game_mode',
        'match_type': 'match_type',
        'ticket_id': 'ticket_id',
        'zone_id': 'zone_id',
        'is_green': 'is_green',
        'is_grudge_match': 'is_grudge_match',
        'need_bp': 'need_bp',
        'no_demo': 'no_demo',
        'time_stamp': 'time_stamp',
    }))
    for normalized_key, source_key in (
        ('win_camp', 'win_camp'),
        ('win_team_id', 'win_team_id'),
        ('lose_team_id', 'lose_team_id'),
    ):
        value = optional_str(report.get(source_key))
        if value is not None:
            stats[normalized_key] = value
    return stats


def _pwa_teams(report: Mapping[str, object]) -> list[MatchTeam]:
    teams: list[MatchTeam] = []
    t_score = optional_int(report.get('t_win_times'))
    ct_score = optional_int(report.get('ct_win_times'))
    teams.append(MatchTeam(
        name='T',
        team_id=optional_str(report.get('t_team_id')),
        player_ids=_pwa_team_player_ids(report, 'T'),
        side='T',
        first_half_side='T',
        score=t_score,
        origin_elo=optional_int(report.get('t_origin_elo')),
        change_elo=optional_int(report.get('t_change_elo')),
    ))
    teams.append(MatchTeam(
        name='CT',
        team_id=optional_str(report.get('ct_team_id')),
        player_ids=_pwa_team_player_ids(report, 'CT'),
        side='CT',
        first_half_side='CT',
        score=ct_score,
        origin_elo=optional_int(report.get('ct_origin_elo')),
        change_elo=optional_int(report.get('ct_change_elo')),
    ))
    return teams


def _pwa_match_awards(report: Mapping[str, object]) -> dict[str, JSONValue]:
    awards: dict[str, JSONValue] = {}
    for normalized_key, source_key in (
        ('mvp_player_id', 'mvp_uid'),
        ('most_assists_player_id', 'most_assist_uid'),
        ('most_awp_kills_player_id', 'most_awp_uid'),
        ('most_clutches_player_id', 'most_end_uid'),
        ('most_first_kills_player_id', 'most_first_kill_uid'),
        ('most_headshots_player_id', 'most_headshot_uid'),
        ('most_jump_kills_player_id', 'most_jump_uid'),
        ('most_1v2_clutches_player_id', 'most_1v2_uid'),
    ):
        value = optional_str(report.get(source_key))
        if value is not None:
            awards[normalized_key] = value
    return awards


def _pwa_team_player_ids(report: Mapping[str, object], side: str) -> list[str]:
    players_value = report.get('players')
    if not isinstance(players_value, list):
        return []
    player_ids: list[str] = []
    for row in players_value:
        if not isinstance(row, Mapping):
            continue
        if optional_str(row.get('camp')) != side:
            continue
        player_id = optional_str(row.get('user_id')) or optional_str(row.get('uid')) or optional_str(row.get('steam_id'))
        if player_id is not None:
            player_ids.append(player_id)
    return player_ids


def _pwa_players(report: Mapping[str, object]) -> list[MatchPlayer]:
    players_value = report.get('players')
    if not isinstance(players_value, list):
        return []

    players: list[MatchPlayer] = []
    for row in players_value:
        if not isinstance(row, Mapping):
            continue
        camp = optional_str(row.get('camp'))
        multi_kills = _pwa_multi_kills(row)
        clutches = _pwa_clutches(row)
        players.append(MatchPlayer(
            player_id=optional_str(row.get('user_id')) or optional_str(row.get('uid')),
            steam_id=optional_str(row.get('steam_id')),
            name=optional_str(row.get('steam_nick')),
            profile=_pwa_player_profile(row),
            team_index=optional_int(row.get('team_id')),
            side=camp,
            ladder_stats=_pwa_ladder_stats(row),
            kills=optional_int(row.get('kill')),
            deaths=optional_int(row.get('death')),
            assists=optional_int(row.get('assist')),
            rating=optional_float(row.get('rating')) or optional_float(row.get('pw_rating')),
            adr=optional_float(row.get('adpr')),
            rws=optional_float(row.get('rws')),
            headshots=optional_int(row.get('headshot_kill_count')),
            first_kills=optional_int(row.get('first_kill')),
            first_deaths=optional_int(row.get('first_death')),
            multi_kill_count=sum(multi_kills.values()),
            multi_kills=multi_kills,
            clutch_count=sum(clutches.values()),
            clutches=clutches,
            utility_stats=_pwa_utility_stats(row),
            impact_stats=_pwa_impact_stats(row),
            award_flags=_pwa_award_flags(row),
            platform_stats=_pwa_player_platform_stats(row),
            raw=json_object(dict(row)),
        ))
    return players


def _pwa_ladder_stats(row: Mapping[str, object]) -> dict[str, JSONValue]:
    return _pwa_compact_stats(row, {
        'score': 'score',
        'level': 'level',
        'rank': 'rank',
        'rank_name': 'rank_name',
        'change_score': 'change_score',
        'elo': 'elo',
    })


def _pwa_player_profile(row: Mapping[str, object]) -> dict[str, JSONValue]:
    steam_id = optional_str(row.get('steam_id'))
    stats: dict[str, JSONValue] = {}
    for normalized_key, source in (
        ('profile_url', row.get('profile_url') or row.get('personal_url')),
        ('avatar_url', row.get('avatar') or row.get('avatar_url') or row.get('steam_avatar')),
        ('nickname', row.get('steam_nick') or row.get('nickname')),
        ('steam_profile_url', f'https://steamcommunity.com/profiles/{steam_id}' if steam_id else None),
        ('steam_account_id', row.get('steamAccountId')),
    ):
        value = _pwa_normalized_scalar(source)
        if value is not None:
            stats[normalized_key] = value
    return stats


def _pwa_player_platform_stats(row: Mapping[str, object]) -> dict[str, JSONValue]:
    sensitive_keys = {
        'access_token',
        'cellphone',
        'currentLoginIp',
        'lastLoginIp',
        'real_name_valid',
        'real_name_valid_type',
    }
    stats: dict[str, JSONValue] = {}
    for key, value in row.items():
        normalized_key = str(key)
        if normalized_key in sensitive_keys:
            continue
        stats[normalized_key] = to_json_value(value)
    return stats


def _pwa_utility_stats(row: Mapping[str, object]) -> dict[str, JSONValue]:
    return _pwa_compact_stats(row, {
        'bomb_plants': 'plant_bomb',
        'bomb_defuses': 'defuse_bomb',
        'utility_damage': 'grenade_damage',
        'enemy_utility_damage': 'throw_harm_enemy',
        'enemies_flashed': 'flash_enemy',
        'enemy_flash_duration': 'flash_enemy_time',
        'teammates_flashed': 'flash_team',
        'team_flash_duration': 'flash_team_time',
    })


def _pwa_impact_stats(row: Mapping[str, object]) -> dict[str, JSONValue]:
    return _pwa_compact_stats(row, {
        'awp_kills': 'awp_kill',
        'jump_kills': 'jump_kill',
        'knife_kills': 'knife_kill',
        'first_kills': 'first_kill',
        'first_deaths': 'first_death',
        'entry_kills': 'entry_kill',
        'trade_kills': 'trade_kill',
        'assisted_kills': 'assisted_kill',
        'revenge_kills': 'revenge_kill',
        'team_kills': 'team_kill',
    })


def _pwa_award_flags(row: Mapping[str, object]) -> dict[str, JSONValue]:
    flags: dict[str, JSONValue] = {}
    for normalized_key, source_key in (
        ('is_mvp', 'is_mvp'),
        ('is_svp', 'is_svp'),
        ('is_highlight', 'is_highlight'),
    ):
        value = optional_int(row.get(source_key))
        if value is not None:
            flags[normalized_key] = bool(value)
    return flags


def _pwa_multi_kills(row: Mapping[str, object]) -> dict[str, int]:
    keys = {
        '2': 'two_kill',
        '3': 'three_kill',
        '4': 'four_kill',
        '5': 'five_kill',
    }
    values: dict[str, int] = {}
    for normalized_key, source_key in keys.items():
        value = optional_int(row.get(source_key))
        if value is not None:
            values[normalized_key] = value
    return values


def _pwa_clutches(row: Mapping[str, object]) -> dict[str, int]:
    values: dict[str, int] = {}
    for index in range(1, 6):
        key = f'1v{index}'
        value = optional_int(row.get(key))
        if value is not None:
            values[str(index)] = value
    return values


def _pwa_compact_stats(row: Mapping[str, object], mapping: Mapping[str, str]) -> dict[str, JSONValue]:
    stats: dict[str, JSONValue] = {}
    for normalized_key, source_key in mapping.items():
        value = _pwa_normalized_scalar(row.get(source_key))
        if value is not None:
            stats[normalized_key] = value
    return stats


def _pwa_normalized_scalar(value: object) -> JSONValue:
    if value is None or isinstance(value, bool):
        return value if isinstance(value, bool) else None
    int_value = optional_int(value)
    if int_value is not None:
        return int_value
    float_value = optional_float(value)
    if float_value is not None:
        return float_value
    return optional_str(value)
