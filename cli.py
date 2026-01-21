#!/usr/bin/env python3
"""
CS Demo Downloader - 命令行入口
用于脚本和 Docker 自动化下载
"""
import argparse
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config, Config
from core.downloader_5e import get_all_demo_urls as get_5e_demos
from core.downloader_pwa import get_all_demo_urls as get_pwa_demos
from core.utils import download_and_extract


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
            print(f"\nMatch {match_id}: {demo_url}")
            download_and_extract(demo_url, config.download_path, print_progress)
            print()  # 换行


def main():
    parser = argparse.ArgumentParser(
        description='CS Demo Downloader - 下载 5E 和完美世界 CS2 Demo'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # download 命令
    download_parser = subparsers.add_parser('download', help='下载 Demo')
    download_parser.add_argument(
        '--all', action='store_true',
        help='下载所有平台的 Demo'
    )
    download_parser.add_argument(
        '--platform', choices=['5e', 'pwa'],
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
        config = load_config(args.config)
        
        # 覆盖下载路径
        if args.output:
            config.download_path = args.output
        
        # 确保下载路径存在
        if not config.download_path:
            config.download_path = os.path.join(os.getcwd(), 'demos')
        
        os.makedirs(config.download_path, exist_ok=True)
        print(f"Download path: {config.download_path}")
        
        # 执行下载
        if args.all or args.platform is None:
            download_5e_demos(config)
            download_pwa_demos(config)
        elif args.platform == '5e':
            download_5e_demos(config)
        elif args.platform == 'pwa':
            download_pwa_demos(config)
        
        print("\n=== Download complete ===")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
