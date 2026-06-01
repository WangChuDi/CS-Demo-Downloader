#!/usr/bin/env python3
"""
CS Demo Downloader - 命令行入口
用于脚本和 Docker 自动化下载
"""
import argparse
import json
import sys
import os
from typing import Callable

from .core.config import load_config, Config, ConfigLoadError
from .core.downloader_5e import get_all_demo_urls as get_5e_demos
from .core.downloader_pwa import get_all_demo_urls as get_pwa_demos
from .core.downloader_pwa import build_download_headers as build_pwa_download_headers
from .core.downloader_steam import get_all_demo_urls as get_steam_demos
from .core.utils import download_and_extract, redact_url
from .pwa_dll_updater import LATEST_YML_URL, PvpAliveUpdateError, update_cached_pvp_alive_dll


PwaDemoSigner = Callable[[str, str, str], str]


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
        print(f"\n=== Downloading 5E demos for {user.label} ===")
        demo_urls = get_5e_demos(user.userid)
        
        if not demo_urls:
            print(f"No demos found for {user.label}")
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
        print(f"\n=== Downloading PWA demos for {user.label} ===")
        try:
            signer = build_pwa_demo_url_signer(config)
        except RuntimeError as e:
            print(f"Unable to configure PWA signer for {user.label}: {e}", file=sys.stderr)
            continue
        demo_urls = get_pwa_demos(user.steamid, user.access_token, signer=signer)
        
        if not demo_urls:
            print(f"No demos found for {user.label}")
            continue
        
        print(f"Found {len(demo_urls)} demos")
        
        for match_id, demo_url in demo_urls.items():
            print(f"\nMatch {match_id}: {redact_url(demo_url)}")
            try:
                headers = build_pwa_download_headers(user.steamid)
            except RuntimeError as e:
                print(f"Unable to build PWA download headers for {user.label}: {e}", file=sys.stderr)
                continue
            download_and_extract(demo_url, config.download_path, print_progress, headers=headers)
            print()  # 换行


def build_pwa_demo_url_signer(config: Config) -> PwaDemoSigner | None:
    pwa_config = config.pwa or {}
    provider = pwa_config.get('signature_provider', 'compiled').strip().lower()
    if provider in {'', 'compiled'}:
        return None

    dll_path = pwa_config.get('pvp_alive_dll', os.path.join('cache', 'PvpAlive.dll'))
    bridge_path = pwa_config.get('pvp_alive_bridge_exe') or None
    timeout = int(pwa_config.get('pvp_alive_timeout', '10'))

    def build_inner_json(randnum: str, timestamp: str, data: str) -> str:
        return json.dumps(
            {'randnum': randnum, 'timestamp': timestamp, 'data': data},
            separators=(',', ':'),
            ensure_ascii=False,
        )

    if provider == 'pvp_alive_native':
        from .pwa_bridge import call_pvp_alive_swap_data

        def native_signer(randnum: str, timestamp: str, data: str) -> str:
            return call_pvp_alive_swap_data(
                dll_path=dll_path,
                inner_json=build_inner_json(randnum, timestamp, data),
                bridge_path=bridge_path,
                timeout=timeout,
            )

        return native_signer

    if provider == 'pvp_alive_wine':
        from .pwa_bridge import call_pvp_alive_swap_data_wine

        wine_binary = pwa_config.get('pvp_alive_wine_executable') or 'wine'

        def wine_signer(randnum: str, timestamp: str, data: str) -> str:
            return call_pvp_alive_swap_data_wine(
                dll_path=dll_path,
                inner_json=build_inner_json(randnum, timestamp, data),
                bridge_path=bridge_path,
                timeout=timeout,
                wine_binary=wine_binary,
            )

        return wine_signer

    message = f"Unsupported PWA signature_provider '{provider}'. Use 'compiled', 'pvp_alive_native', or 'pvp_alive_wine'."
    raise RuntimeError(message)


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
        print(f"\n=== Downloading Steam official demos for {user.label} ===")
        demo_urls = get_steam_demos(
            user.api_key,
            user.steamid,
            user.steamidkey,
            user.knowncode,
            demo_url_resolver=demo_url_resolver,
        )

        if not demo_urls:
            print(f"No demos found for {user.label}")
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

    pvp_alive_parser = subparsers.add_parser(
        'update-pvpalive-dll',
        help='通过 HTTP Range 从官方客户端 ZIP 提取并缓存 PvpAlive.dll'
    )
    pvp_alive_parser.add_argument(
        '--latest-yml-url',
        default=LATEST_YML_URL,
        help='官方 latest.yml URL'
    )
    pvp_alive_parser.add_argument(
        '--target',
        default=os.path.join('cache', 'PvpAlive.dll'),
        help='目标缓存 DLL 路径'
    )
    pvp_alive_parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='网络请求超时时间（秒）'
    )
    pvp_alive_parser.add_argument(
        '--force',
        action='store_true',
        help='即使缓存版本已是最新也强制重新下载 DLL'
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
    elif args.command == 'update-pvpalive-dll':
        try:
            dll_path = update_cached_pvp_alive_dll(
                latest_yml_url=args.latest_yml_url,
                target_path=args.target,
                timeout=args.timeout,
                force=args.force,
            )
        except PvpAliveUpdateError as e:
            print(f"Error updating PvpAlive.dll: {e}", file=sys.stderr)
            return 1

        print(f"Updated PvpAlive.dll: {dll_path}")
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
