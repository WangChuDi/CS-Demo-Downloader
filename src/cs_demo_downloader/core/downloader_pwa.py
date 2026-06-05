"""
完美世界电竞平台 Demo 下载器
"""
import json
import random
import sys
import time
import requests
from collections.abc import Callable
from importlib import import_module, machinery, resources, util
from pathlib import Path
from packaging import tags
from typing import Protocol, cast


PWA_MATCH_LIST_URL = 'https://pwaweblogin.wmpvp.com/user-info/recent-ladder-score-list'
PWA_WEB_API_APPID = 20000
PWA_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) perfectworldarena/1.0.26051411 '
    'Chrome/80.0.3987.163 Electron/8.5.5 Safari/537.36'
)

_public_ip_cache: str | None = None
DemoUrlSigner = Callable[[str, str, str], str]


class PwaSignerUnavailableError(RuntimeError):
    """Raised when the proprietary compiled PWA signer wheel is not installed."""


class _CompiledPwaSigner(Protocol):
    def sign_demo_request(self, randnum: str, timestamp: str, data: str) -> str:
        ...

    def build_x_pwa_signature(self, steamid: str, timestamp: int, ip_addr: str) -> str:
        ...


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
    size: int = 20
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
    params = {
        'access_token': access_token,
        'size': size,
        'uid': steamid
    }
    
    headers = {
        'Host': 'pwaweblogin.wmpvp.com',
        'x-pwa-steamid': steamid,
        'pwasteamid': steamid,
        'User-Agent': PWA_USER_AGENT,
    }
    
    try:
        response = requests.get(PWA_MATCH_LIST_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            response_data = cast(object, response.json())
            if not isinstance(response_data, dict):
                return []
            data = cast(dict[str, object], response_data)
            match_data = data.get('data', [])
            if not isinstance(match_data, list):
                return []
            matches = cast(list[object], match_data)
            match_ids: list[str] = []
            for match in matches:
                if not isinstance(match, dict):
                    continue
                match_record = cast(dict[str, object], match)
                match_id = match_record.get('match')
                if isinstance(match_id, str):
                    match_ids.append(match_id)
            return match_ids
        
        return []
    except requests.RequestException as e:
        print(f"Error getting PWA match list: {e}")
        return []


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
    data = '&'.join(f'{key}={value}' for key, value in sorted(sorted_params.items()))
    randnum = str(random.randint(100000, 999999))
    timestamp = str(int(time.time()))
    signature = (signer or sign_demo_request)(randnum, timestamp, data)
    return (
        f'https://pwaweblogin.wmpvp.com/csgo/demo/{match_id}_{cup_id}.dem'
        f'?a={PWA_WEB_API_APPID}&r={randnum}&s={signature}&t={timestamp}&{data}'
    )


def get_all_demo_urls(
    steamid: str,
    access_token: str,
    size: int = 20,
    signer: DemoUrlSigner | None = None,
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
    match_ids = get_match_list(steamid, access_token, size)
    demo_urls: dict[str, str] = {}
    
    for match_id in match_ids:
        demo_url = get_demo_url(match_id, access_token, signer=signer)
        demo_urls[match_id] = demo_url
    
    return demo_urls
