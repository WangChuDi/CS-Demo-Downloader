#!/usr/bin/env python3
"""
CS Demo Downloader - 命令行入口
用于脚本和 Docker 自动化下载
"""
import argparse
import sys
import os

from .core.config import load_config, Config, ConfigLoadError
from .core.downloader_5e import get_all_demo_urls as get_5e_demos
from .core.downloader_pwa import get_all_demo_urls as get_pwa_demos
from .core.downloader_pwa import build_download_headers as build_pwa_download_headers
from .core.downloader_steam import get_all_demo_urls as get_steam_demos
from .core.utils import download_and_extract, redact_url


def print_progress(downloaded: int, total: int):
    """打印下载进度"""
    if total > 0:
        percent = int(100 * downloaded / total)
        bar_len = 50
        filled = int(bar_len * downloaded / total)
        bar = '=' * filled + '-' * (bar_len - filled)
        print(f'\r[{bar}] {percent}%', end='', flush=True)


def download_5e_demos(config: Config):
    """下载所有 5E 用户的 Demo"""
    users = config.get_users_5e()
    if not users:
        print("No 5E users configured.")
        return
    
    for user in users:
        print(f"\n=== Downloading 5E demos for {user.name} ===")
        demo_urls = get_5e_demos(user.userid)
        
        if not demo_urls:
            print(f"No demos found for {user.name}")
            continue
        
        print(f"Found {len(demo_urls)} demos")
        
        for match_id, demo_url in demo_urls.items():
            print(f"\nMatch {match_id}: {demo_url}")
            download_and_extract(demo_url, config.download_path, print_progress)
            print()  # 换行


def download_pwa_demos(config: Config):
    """下载所有完美世界用户的 Demo"""
    users = config.get_users_pwa()
    if not users:
        print("No PWA users configured.")
        return
    
    for user in users:
        print(f"\n=== Downloading PWA demos for {user.name} ===")
        demo_urls = get_pwa_demos(user.steamid, user.access_token)
        
        if not demo_urls:
            print(f"No demos found for {user.name}")
            continue
        
        print(f"Found {len(demo_urls)} demos")
        
        for match_id, demo_url in demo_urls.items():
            print(f"\nMatch {match_id}: {redact_url(demo_url)}")
            try:
                headers = build_pwa_download_headers(user.steamid)
            except RuntimeError as e:
                print(f"Unable to build PWA download headers for {user.name}: {e}", file=sys.stderr)
                continue
            download_and_extract(demo_url, config.download_path, print_progress, headers=headers)
            print()  # 换行


def build_steam_demo_url_resolver(config: Config):
    resolver_config = config.steam_resolver or {}
    resolver_type = resolver_config.get('type', '').strip().lower()

    if resolver_type == 'boiler':
        from .steam.boiler_resolver import BoilerWritterResolver

        executable_path = resolver_config.get('executable_path', 'boiler-writter')
        timeout = int(resolver_config.get('timeout', '60'))
        auto_download = str(resolver_config.get('auto_download', 'false')).lower() in {'1', 'true', 'yes'}
        cache_dir = resolver_config.get('cache_dir')
        resolver = BoilerWritterResolver(
            executable_path=executable_path,
            timeout=timeout,
            auto_download=auto_download,
            cache_dir=cache_dir,
        )
        return resolver.resolve_demo_url

    if resolver_type == 'steam-login':
        from .steam.login_resolver import SteamLoginResolver

        gc_config = config.steam_gc or {}
        resolver = SteamLoginResolver(
            username_env=gc_config.get('username_env', 'STEAM_GC_USERNAME'),
            password_env=gc_config.get('password_env', 'STEAM_GC_PASSWORD'),
            two_factor_secret_env=gc_config.get('two_factor_secret_env', 'STEAM_GC_TWO_FACTOR_SECRET'),
            auth_code_env=gc_config.get('auth_code_env', 'STEAM_GC_AUTH_CODE'),
            sentry_dir=gc_config.get('sentry_dir'),
            timeout=int(gc_config.get('timeout', '30')),
        )
        return resolver.resolve_demo_url

    return None


def download_steam_demos(config: Config):
    """下载所有 Steam 官匹用户的 Demo"""
    users = config.get_users_steam()
    if not users:
        print("No Steam users configured.")
        return

    demo_url_resolver = build_steam_demo_url_resolver(config)

    for user in users:
        print(f"\n=== Downloading Steam official demos for {user.name} ===")
        demo_urls = get_steam_demos(
            user.api_key,
            user.steamid,
            user.steamidkey,
            user.knowncode,
            demo_url_resolver=demo_url_resolver,
        )

        if not demo_urls:
            print(f"No demos found for {user.name}")
            continue

        print(f"Found {len(demo_urls)} demos")

        for match_id, demo_url in demo_urls.items():
            print(f"\nMatch {match_id}: {demo_url}")
            download_and_extract(demo_url, config.download_path, print_progress)
            print()  # 换行


def main():
    parser = argparse.ArgumentParser(
        description='CS Demo Downloader - 下载 5E、完美世界和 Steam 官匹 CS2 Demo'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # download 命令
    download_parser = subparsers.add_parser('download', help='下载 Demo')
    download_parser.add_argument(
        '--all', action='store_true',
        help='下载所有平台的 Demo'
    )
    download_parser.add_argument(
        '--platform', choices=['5e', 'pwa', 'steam'],
        help='只下载指定平台的 Demo'
    )
    download_parser.add_argument(
        '--config', type=str,
        help='配置文件路径'
    )
    download_parser.add_argument(
        '--output', type=str,
        help='下载目录（覆盖配置文件中的设置）'
    )
    
    args = parser.parse_args()
    
    if args.command == 'download':
        # 加载配置
        try:
            config = load_config(args.config)
        except ConfigLoadError as e:
            print(e, file=sys.stderr)
            return 1
        
        # 覆盖下载路径
        if args.output:
            config.download_path = args.output
        
        # 确保下载路径存在
        if not config.download_path:
            config.download_path = os.path.join(os.getcwd(), 'demos')

        try:
            os.makedirs(config.download_path, exist_ok=True)
        except OSError as e:
            print(f"Error creating download path '{config.download_path}': {e}", file=sys.stderr)
            return 1

        print(f"Download path: {config.download_path}")
        
        # 执行下载
        if args.all or args.platform is None:
            download_5e_demos(config)
            download_pwa_demos(config)
            download_steam_demos(config)
        elif args.platform == '5e':
            download_5e_demos(config)
        elif args.platform == 'pwa':
            download_pwa_demos(config)
        elif args.platform == 'steam':
            download_steam_demos(config)
        
        print("\n=== Download complete ===")
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
