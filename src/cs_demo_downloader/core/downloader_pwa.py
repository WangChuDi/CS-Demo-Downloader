"""
完美世界电竞平台 Demo 下载器
"""
import hashlib
import random
import time
import requests
from typing import List, Dict, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


PWA_MATCH_LIST_URL = 'https://pwaweblogin.wmpvp.com/user-info/recent-ladder-score-list'
PWA_WEB_API_APPID = 20000
PWA_SIGN_TAIL64 = '969c1bcfdc527c319157cc48f83b1d106ebdeca3e8d9763f1ae6b88dde9b3ea9'
PWA_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) perfectworldarena/1.0.26051411 '
    'Chrome/80.0.3987.163 Electron/8.5.5 Safari/537.36'
)

_public_ip_cache: Optional[str] = None


def sign_demo_request(randnum: str, timestamp: str, data: str) -> str:
    """生成 PWA demo URL 请求签名。"""
    prefix = hashlib.md5((randnum + timestamp + data).encode('utf-8')).hexdigest()
    payload = f'{PWA_WEB_API_APPID}{prefix}{PWA_SIGN_TAIL64}'
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


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
    iv = steamid[-16:].encode('utf-8')
    timestamp_text = str(timestamp)
    key = (timestamp_text + steamid[len(timestamp_text) - 16:]).encode('utf-8')
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    padder = PKCS7(128).padder()
    padded = padder.update(ip_addr.encode('utf-8')) + padder.finalize()
    encrypted = cipher.update(padded) + cipher.finalize()
    return f'{timestamp}-{encrypted.hex()}'


def build_download_headers(
    steamid: str,
    public_ip: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> Dict[str, str]:
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
) -> List[str]:
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
            data = response.json()
            match_data = data.get('data', [])
            if isinstance(match_data, list):
                return [match['match'] for match in match_data if 'match' in match]
        
        return []
    except requests.RequestException as e:
        print(f"Error getting PWA match list: {e}")
        return []


def get_demo_url(match_id: str, access_token: str, cup_id: int = 0) -> str:
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
    signature = sign_demo_request(randnum, timestamp, data)
    return (
        f'https://pwaweblogin.wmpvp.com/csgo/demo/{match_id}_{cup_id}.dem'
        f'?a={PWA_WEB_API_APPID}&r={randnum}&s={signature}&t={timestamp}&{data}'
    )


def get_all_demo_urls(
    steamid: str,
    access_token: str,
    size: int = 20
) -> Dict[str, str]:
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
    demo_urls = {}
    
    for match_id in match_ids:
        demo_url = get_demo_url(match_id, access_token)
        demo_urls[match_id] = demo_url
    
    return demo_urls
