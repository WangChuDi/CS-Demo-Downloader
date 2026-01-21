"""
配置管理模块
"""
import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class User5E:
    """5E 用户配置"""
    name: str
    userid: str


@dataclass
class UserPWA:
    """完美世界用户配置"""
    name: str
    steamid: str
    access_token: str


@dataclass
class Config:
    """应用配置"""
    download_path: str = ""
    users_5e: List[Dict[str, str]] = field(default_factory=list)
    users_pwa: List[Dict[str, str]] = field(default_factory=list)
    
    def get_users_5e(self) -> List[User5E]:
        """获取 5E 用户列表"""
        return [User5E(**u) for u in self.users_5e]
    
    def get_users_pwa(self) -> List[UserPWA]:
        """获取完美世界用户列表"""
        return [UserPWA(**u) for u in self.users_pwa]
    
    def add_user_5e(self, name: str, userid: str):
        """添加 5E 用户"""
        self.users_5e.append({"name": name, "userid": userid})
    
    def add_user_pwa(self, name: str, steamid: str, access_token: str):
        """添加完美世界用户"""
        self.users_pwa.append({
            "name": name,
            "steamid": steamid,
            "access_token": access_token
        })
    
    def remove_user_5e(self, index: int):
        """删除 5E 用户"""
        if 0 <= index < len(self.users_5e):
            self.users_5e.pop(index)
    
    def remove_user_pwa(self, index: int):
        """删除完美世界用户"""
        if 0 <= index < len(self.users_pwa):
            self.users_pwa.pop(index)


def get_config_path() -> str:
    """获取配置文件路径"""
    # 优先使用当前目录
    local_config = os.path.join(os.getcwd(), 'config.json')
    if os.path.exists(local_config):
        return local_config
    
    # 其次使用用户目录
    home = os.path.expanduser('~')
    config_dir = os.path.join(home, '.cs_demo_downloader')
    return os.path.join(config_dir, 'config.json')


def load_config(config_path: Optional[str] = None) -> Config:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，None 则使用默认路径
    
    Returns:
        Config 对象
    """
    if config_path is None:
        config_path = get_config_path()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Config(
                    download_path=data.get('download_path', ''),
                    users_5e=data.get('users_5e', []),
                    users_pwa=data.get('users_pwa', [])
                )
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")
    
    return Config()


def save_config(config: Config, config_path: Optional[str] = None):
    """
    保存配置文件
    
    Args:
        config: Config 对象
        config_path: 配置文件路径，None 则使用默认路径
    """
    if config_path is None:
        config_path = get_config_path()
    
    # 确保目录存在
    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            data = {
                'download_path': config.download_path,
                'users_5e': config.users_5e,
                'users_pwa': config.users_pwa
            }
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving config: {e}")
