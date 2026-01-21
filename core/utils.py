"""
通用工具模块 - 下载、解压、时间戳工具
"""
import os
import datetime
import time
import zipfile
import requests
from typing import Callable, Optional


def get_end_of_day_timestamp(date: Optional[datetime.date] = None) -> int:
    """获取指定日期的 23:59:59 时间戳，默认为当天"""
    if date is None:
        dt = datetime.datetime.now()
    else:
        dt = datetime.datetime.combine(date, datetime.time())
    
    end_of_day = dt.replace(hour=23, minute=59, second=59)
    return int(time.mktime(end_of_day.timetuple()))


def get_timestamp_days_ago(days: int) -> int:
    """获取 N 天前的 23:59:59 时间戳"""
    now = datetime.datetime.now()
    target_date = now - datetime.timedelta(days=days)
    end_of_day = target_date.replace(hour=23, minute=59, second=59)
    return int(time.mktime(end_of_day.timetuple()))


def download_file(
    url: str,
    local_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Optional[str]:
    """
    下载文件，支持进度回调
    
    Args:
        url: 下载链接
        local_path: 本地保存路径
        progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
    
    Returns:
        成功返回文件路径，失败返回 None
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            
            # 检查响应类型
            content_type = r.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                print(f"Invalid response type: {content_type}")
                return None
            
            total_size = int(r.headers.get('content-length', 0))
            chunk_size = 8192
            downloaded_size = 0
            
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded_size, total_size)
        
        return local_path
    
    except requests.RequestException as e:
        print(f"Download error: {e}")
        return None


def unzip_file(zip_path: str, extract_path: str) -> bool:
    """
    解压 ZIP 文件
    
    Args:
        zip_path: ZIP 文件路径
        extract_path: 解压目标路径
    
    Returns:
        成功返回 True，失败返回 False
    """
    try:
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        return True
    except zipfile.BadZipFile as e:
        print(f"Bad zip file: {e}")
        return False
    except Exception as e:
        print(f"Unzip error: {e}")
        return False


def download_and_extract(
    url: str,
    demo_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    下载并解压 Demo 文件
    
    Args:
        url: Demo 下载链接
        demo_path: Demo 保存目录
        progress_callback: 进度回调函数
    
    Returns:
        成功返回 True，失败返回 False
    """
    if not url:
        print("URL is empty, skipping.")
        return False
    
    # 从 URL 提取文件名
    filename = url.split('/')[-1]
    
    # 检查解压后的 .dem 文件是否已存在
    dem_filename = filename.replace('.zip', '.dem')
    if not dem_filename.endswith('.dem'):
        dem_filename = filename.split('.')[0] + '.dem'
    
    dem_path = os.path.join(demo_path, dem_filename)
    if os.path.exists(dem_path):
        print(f"File {dem_filename} already exists, skipping.")
        return True
    
    # 下载 ZIP 文件
    zip_path = os.path.join(demo_path, filename)
    if not zip_path.endswith('.zip'):
        zip_path += '.zip'
    
    downloaded = download_file(url, zip_path, progress_callback)
    if not downloaded:
        return False
    
    # 解压
    if unzip_file(zip_path, demo_path):
        # 删除 ZIP 文件
        try:
            os.remove(zip_path)
        except OSError:
            pass
        print(f"Downloaded and extracted to {demo_path}")
        return True
    
    return False
