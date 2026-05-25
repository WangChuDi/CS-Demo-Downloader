"""
下载工作线程
"""
from PyQt5.QtCore import QThread, pyqtSignal
from typing import Dict, List, Optional, Tuple

from cs_demo_downloader.core.downloader_5e import get_all_demo_urls as get_5e_demos
from cs_demo_downloader.core.downloader_pwa import get_all_demo_urls as get_pwa_demos
from cs_demo_downloader.core.downloader_pwa import build_download_headers as build_pwa_download_headers
from cs_demo_downloader.core.downloader_steam import get_all_demo_urls as get_steam_demos
from cs_demo_downloader.core.utils import download_and_extract
from cs_demo_downloader.core.config import Config
from cs_demo_downloader.cli import build_steam_demo_url_resolver


class FetchDemosWorker(QThread):
    """获取 Demo 列表的工作线程"""
    
    # 信号: (platform, user_name, match_id, demo_url, steamid)
    demo_found = pyqtSignal(str, str, str, str, str)
    # 信号: (message)
    status_update = pyqtSignal(str)
    # 信号: 完成
    finished_signal = pyqtSignal()
    
    def __init__(self, config: Config, platform: str = 'all'):
        super().__init__()
        self.config = config
        self.platform = platform  # 'all', '5e', 'pwa', 'steam'
    
    def run(self):
        if self.platform in ('all', '5e'):
            self._fetch_5e_demos()
        
        if self.platform in ('all', 'pwa'):
            self._fetch_pwa_demos()

        if self.platform in ('all', 'steam'):
            self._fetch_steam_demos()
        
        self.finished_signal.emit()
    
    def _fetch_5e_demos(self):
        users = self.config.get_users_5e()
        for user in users:
            self.status_update.emit(f"正在获取 5E 用户 {user.name} 的比赛列表...")
            demo_urls = get_5e_demos(user.userid)
            
            for match_id, demo_url in demo_urls.items():
                self.demo_found.emit('5e', user.name, match_id, demo_url, '')
    
    def _fetch_pwa_demos(self):
        users = self.config.get_users_pwa()
        for user in users:
            self.status_update.emit(f"正在获取完美世界用户 {user.name} 的比赛列表...")
            demo_urls = get_pwa_demos(user.steamid, user.access_token)
            
            for match_id, demo_url in demo_urls.items():
                self.demo_found.emit('pwa', user.name, match_id, demo_url, user.steamid)

    def _fetch_steam_demos(self):
        users = self.config.get_users_steam()
        demo_url_resolver = build_steam_demo_url_resolver(self.config)
        for user in users:
            self.status_update.emit(f"正在获取 Steam 官匹用户 {user.name} 的比赛列表...")
            demo_urls = get_steam_demos(
                user.api_key,
                user.steamid,
                user.steamidkey,
                user.knowncode,
                demo_url_resolver=demo_url_resolver,
            )

            for match_id, demo_url in demo_urls.items():
                self.demo_found.emit('steam', user.name, match_id, demo_url, '')


class DownloadWorker(QThread):
    """下载 Demo 的工作线程"""
    
    # 信号: (current_index, total_count, match_id, status)
    progress_update = pyqtSignal(int, int, str, str)
    # 信号: (downloaded_bytes, total_bytes)
    download_progress = pyqtSignal(int, int)
    # 信号: (match_id, success)
    download_complete = pyqtSignal(str, bool)
    # 信号: 全部完成
    all_complete = pyqtSignal()
    
    def __init__(self, demos: List[Tuple[str, str, str, str]], download_path: str):
        """
        Args:
            demos: [(match_id, demo_url, user_name, platform_or_steamid), ...]
            download_path: 下载目录
        """
        super().__init__()
        self.demos = demos
        self.download_path = download_path
        self._stop_flag = False
    
    def stop(self):
        self._stop_flag = True
    
    def run(self):
        total = len(self.demos)
        
        for i, (match_id, demo_url, user_name, platform_or_steamid) in enumerate(self.demos):
            if self._stop_flag:
                break
            
            self.progress_update.emit(i + 1, total, match_id, "下载中...")
            
            def progress_callback(downloaded, total_size):
                self.download_progress.emit(downloaded, total_size)
            
            headers: Optional[Dict[str, str]] = None
            if 'pwaweblogin.wmpvp.com/csgo/demo/' in demo_url and platform_or_steamid:
                try:
                    headers = build_pwa_download_headers(platform_or_steamid)
                except RuntimeError:
                    self.download_complete.emit(match_id, False)
                    self.progress_update.emit(i + 1, total, match_id, "失败")
                    continue

            success = download_and_extract(
                demo_url,
                self.download_path,
                progress_callback,
                headers=headers,
            )
            
            self.download_complete.emit(match_id, success)
            
            status = "已完成" if success else "失败"
            self.progress_update.emit(i + 1, total, match_id, status)
        
        self.all_complete.emit()
