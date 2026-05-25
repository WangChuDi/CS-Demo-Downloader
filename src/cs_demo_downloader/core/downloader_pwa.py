"""
完美世界电竞平台 Demo 下载器
"""
import requests
from typing import Optional, List, Dict


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
    url = 'https://pwaweblogin.wmpvp.com/user-info/recent-ladder-score-list'
    
    params = {
        'access_token': access_token,
        'size': size,
        'uid': steamid
    }
    
    headers = {
        'Host': 'pwaweblogin.wmpvp.com',
        'x-pwa-steamid': steamid,
        'pwasteamid': steamid,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) perfectworldarena/1.0.24120411 Chrome/80.0.3987.163 Electron/8.5.5 Safari/537.36'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            match_data = data.get('data', [])
            if isinstance(match_data, list):
                return [match['match'] for match in match_data if 'match' in match]
        
        return []
    except requests.RequestException as e:
        print(f"Error getting PWA match list: {e}")
        return []


def get_demo_url(match_id: str) -> str:
    """
    构造完美世界 Demo 下载链接
    
    Args:
        match_id: 比赛 ID
    
    Returns:
        Demo 下载 URL
    """
    return f'https://pwaweblogin.wmpvp.com/csgo/demo/{match_id}_0.dem'


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
        demo_url = get_demo_url(match_id)
        demo_urls[match_id] = demo_url
    
    return demo_urls
