"""
5E 平台 Demo 下载器
"""
import requests
from typing import Optional, List, Dict
from .utils import get_end_of_day_timestamp, get_timestamp_days_ago


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

URL_ID_TRANSFER = 'https://gate.5eplay.com/userinterface/http/v1/userinterface/idTransfer'


def get_uuid(userid: str) -> Optional[str]:
    """
    通过 5E userid 获取 uuid
    
    Args:
        userid: 5E 用户 ID（如 11814738gjdwn7）
    
    Returns:
        uuid 字符串，失败返回 None
    """
    try:
        payload = {
            "trans": {
                "domain": userid
            }
        }
        response = requests.post(URL_ID_TRANSFER, json=payload, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            uuid = data.get('data', {}).get('uuid')
            return uuid
        else:
            print(f"Failed to get uuid, status: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error getting uuid: {e}")
        return None


def get_match_list(
    uuid: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: int = 30
) -> List[str]:
    """
    获取比赛列表
    
    Args:
        uuid: 用户 uuid
        start_time: 开始时间戳（默认 180 天前）
        end_time: 结束时间戳（默认当天）
        limit: 返回数量限制
    
    Returns:
        match_id 列表
    """
    if start_time is None:
        start_time = get_timestamp_days_ago(180)
    if end_time is None:
        end_time = get_end_of_day_timestamp()
    
    url = (
        f'https://gate.5eplay.com/crane/http/api/data/match/list'
        f'?match_type=-1&page=1&date=0'
        f'&start_time={start_time}&end_time={end_time}'
        f'&uuid={uuid}&limit={limit}&cs_type=0'
    )
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            match_data = data.get('data', [])
            if isinstance(match_data, list):
                return [match['match_id'] for match in match_data if 'match_id' in match]
        
        return []
    except requests.RequestException as e:
        print(f"Error getting match list: {e}")
        return []


def get_demo_url(match_id: str) -> Optional[str]:
    """
    获取比赛的 Demo 下载链接
    
    Args:
        match_id: 比赛 ID
    
    Returns:
        Demo 下载 URL，失败返回 None
    """
    url = f'https://gate.5eplay.com/crane/http/api/data/match/{match_id}'
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            demo_url = data.get('data', {}).get('main', {}).get('demo_url')
            return demo_url
        
        return None
    except requests.RequestException as e:
        print(f"Error getting demo url for match {match_id}: {e}")
        return None


def get_all_demo_urls(userid: str, limit: int = 30) -> Dict[str, str]:
    """
    获取用户所有比赛的 Demo 下载链接
    
    Args:
        userid: 5E 用户 ID
        limit: 返回数量限制
    
    Returns:
        {match_id: demo_url} 字典
    """
    uuid = get_uuid(userid)
    if not uuid:
        return {}
    
    match_ids = get_match_list(uuid, limit=limit)
    demo_urls = {}
    
    for match_id in match_ids:
        demo_url = get_demo_url(match_id)
        if demo_url:
            demo_urls[match_id] = demo_url
    
    return demo_urls
