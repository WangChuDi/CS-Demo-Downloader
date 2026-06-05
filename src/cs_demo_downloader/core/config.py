"""
配置管理模块
"""
import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


class ConfigLoadError(Exception):
    """配置文件加载失败"""


@dataclass
class User5E:
    """5E 用户配置"""
    label: str
    userid: str

    @property
    def name(self) -> str:
        return self.label


@dataclass
class UserPWA:
    """完美世界用户配置"""
    label: str
    steamid: str
    access_token: str

    @property
    def name(self) -> str:
        return self.label


@dataclass
class UserSteam:
    """Steam 官匹用户配置"""
    label: str
    steamid: str
    api_key: str
    steamidkey: str
    knowncode: str

    @property
    def name(self) -> str:
        return self.label


@dataclass
class Config:
    """应用配置"""
    download_path: str = "."
    steam_resolver: Dict[str, str] = field(default_factory=dict)
    steam_gc: Dict[str, str] = field(default_factory=dict)
    pwa: Dict[str, str] = field(default_factory=dict)
    users_5e: List[Dict[str, str]] = field(default_factory=list)
    users_pwa: List[Dict[str, str]] = field(default_factory=list)
    users_steam: List[Dict[str, str]] = field(default_factory=list)
    
    def get_users_5e(self) -> List[User5E]:
        """获取 5E 用户列表"""
        return [User5E(**u) for u in self.users_5e]
    
    def get_users_pwa(self) -> List[UserPWA]:
        """获取完美世界用户列表"""
        default_access_token = self.pwa.get('default_access_token', '')
        users = []
        for user in self.users_pwa:
            data = dict(user)
            data.setdefault('access_token', default_access_token)
            users.append(UserPWA(**data))
        return users

    def get_users_steam(self) -> List[UserSteam]:
        """获取 Steam 官匹用户列表"""
        return [UserSteam(**u) for u in self.users_steam]
    
    def add_user_5e(self, label: str, userid: str):
        """添加 5E 用户"""
        self.users_5e.append({"label": label, "userid": userid})
    
    def add_user_pwa(self, label: str, steamid: str, access_token: str):
        """添加完美世界用户"""
        self.users_pwa.append({
            "label": label,
            "steamid": steamid,
            "access_token": access_token
        })

    def add_user_steam(
        self,
        label: str,
        steamid: str,
        api_key: str,
        steamidkey: str,
        knowncode: str
    ):
        """添加 Steam 官匹用户"""
        self.users_steam.append({
            "label": label,
            "steamid": steamid,
            "api_key": api_key,
            "steamidkey": steamidkey,
            "knowncode": knowncode
        })
    
    def remove_user_5e(self, index: int):
        """删除 5E 用户"""
        if 0 <= index < len(self.users_5e):
            self.users_5e.pop(index)
    
    def remove_user_pwa(self, index: int):
        """删除完美世界用户"""
        if 0 <= index < len(self.users_pwa):
            self.users_pwa.pop(index)

    def remove_user_steam(self, index: int):
        """删除 Steam 官匹用户"""
        if 0 <= index < len(self.users_steam):
            self.users_steam.pop(index)


def get_config_path() -> str:
    """获取配置文件路径"""
    # 优先使用当前目录
    for filename in ('config.jsonc', 'config.json'):
        local_config = os.path.join(os.getcwd(), filename)
        if os.path.exists(local_config):
            return local_config
    
    # 其次使用用户目录
    home = os.path.expanduser('~')
    config_dir = os.path.join(home, '.cs_demo_downloader')
    return os.path.join(config_dir, 'config.jsonc')


def strip_jsonc_comments(text: str) -> str:
    """Strip // and /* */ comments while preserving string contents."""
    result = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ''

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == '/' and next_char == '/':
            i += 2
            while i < len(text) and text[i] not in '\r\n':
                i += 1
            continue

        if char == '/' and next_char == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            if i + 1 >= len(text):
                raise ValueError('Unterminated block comment in JSONC config')
            i += 2
            continue

        result.append(char)
        i += 1

    return ''.join(result)


def _normalize_user_label(user: Dict[str, Any]) -> Dict[str, str]:
    normalized = {str(key): str(value) for key, value in user.items() if value is not None}
    if 'label' not in normalized and 'name' in normalized:
        normalized['label'] = normalized.pop('name')
    return normalized


def _normalize_config_data(data: Dict[str, Any]) -> Dict[str, Any]:
    five_e = data.get('five_e', {}) or {}
    pwa = data.get('pwa', {}) or {}
    steam = data.get('steam', {}) or {}

    pwa_config = {
        str(key): str(value)
        for key, value in pwa.items()
        if key != 'users' and value is not None
    }

    users_pwa = [_normalize_user_label(user) for user in pwa.get('users', data.get('users_pwa', []))]
    default_access_token = pwa_config.get('default_access_token', '')
    for user in users_pwa:
        if 'access_token' not in user and default_access_token:
            user['access_token'] = default_access_token

    return {
        'download_path': data.get('download_path', '.'),
        'steam_resolver': steam.get('resolver', data.get('steam_resolver', {})) or {},
        'steam_gc': steam.get('gc', data.get('steam_gc', {})) or {},
        'pwa': pwa_config,
        'users_5e': [_normalize_user_label(user) for user in five_e.get('users', data.get('users_5e', []))],
        'users_pwa': users_pwa,
        'users_steam': [_normalize_user_label(user) for user in steam.get('users', data.get('users_steam', []))],
    }


def load_config(config_path: Optional[str] = None) -> Config:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，None 则使用默认路径
    
    Returns:
        Config 对象
    """
    explicit_path = config_path is not None

    if config_path is None:
        config_path = get_config_path()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.loads(strip_jsonc_comments(f.read()))
                return Config(**_normalize_config_data(data))
        except (json.JSONDecodeError, ValueError, TypeError, IOError) as e:
            message = f"Error loading config '{config_path}': {e}"
            if explicit_path:
                raise ConfigLoadError(message) from e
            print(message)
    elif explicit_path:
        raise ConfigLoadError(f"Config file not found: {config_path}")

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
                'five_e': {'users': config.users_5e},
                'pwa': {**config.pwa, 'users': config.users_pwa},
                'steam': {
                    'users': config.users_steam,
                    'resolver': config.steam_resolver,
                    'gc': config.steam_gc,
                },
            }
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving config: {e}")
