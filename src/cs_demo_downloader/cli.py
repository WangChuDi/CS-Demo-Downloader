#!/usr/bin/env python3
"""
CS Demo Downloader - 命令行入口
用于脚本和 Docker 自动化下载
"""
import argparse
import datetime
import json
import os
import signal
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from types import FrameType
from typing import Callable

from .core.config import Config, ConfigLoadError, load_config, write_default_docker_config
from .core.downloader_5e import get_all_demo_urls as get_5e_demos
from .core.downloader_5e import get_all_demo_metadata as get_5e_metadata
from .core.downloader_pwa import build_download_headers as build_pwa_download_headers
from .core.downloader_pwa import call_pwa_et_decryptor_exe
from .core.downloader_pwa import get_all_demo_urls as get_pwa_demos
from .core.downloader_pwa import get_all_demo_metadata as get_pwa_metadata
from .core.downloader_steam import get_all_demo_urls as get_steam_demos
from .core.logging import log_error, log_info
from .core.metadata import MatchMetadata, metadata_list_to_dicts
from .core.utils import download_and_extract, get_demo_filename_from_url, redact_url
from .pwa_dll_updater import LATEST_YML_URL, PvpAliveUpdateError, update_cached_pvp_alive_dll


PwaDemoSigner = Callable[[str, str, str], str]
PwaEtDecryptor = Callable[[str, str], str]
VALID_PLATFORMS = ('5e', 'pwa', 'steam')
METADATA_PLATFORMS = ('5e', 'pwa')
SCHEDULE_PLATFORM_VALUES = ('all', *VALID_PLATFORMS)
TRUE_VALUES = {'1', 'true', 'yes', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'off', ''}


class SchedulerConfigError(ValueError):
    """Raised when scheduler settings are invalid."""


@dataclass
class SchedulerSettings:
    enabled: bool = False
    interval_seconds: int = 86400
    daily_time: str | None = None
    run_on_start: bool = False
    config_path: str | None = None
    output_path: str | None = None
    platforms: str | list[str] | None = None


def print_progress(downloaded: int, total: int):
    """Print download progress without flooding container logs."""
    if total <= 0:
        return

    percent = int(100 * downloaded / total)
    progress_mode = os.environ.get('CS_DEMO_PROGRESS', 'auto').strip().lower()
    if progress_mode == 'none':
        return

    if progress_mode == 'bar' or (progress_mode == 'auto' and sys.stdout.isatty()):
        bar_len = 50
        filled = int(bar_len * downloaded / total)
        bar = '=' * filled + '-' * (bar_len - filled)
        print(f'\r[{bar}] {percent}%', end='', flush=True)
        if downloaded >= total:
            print(flush=True)
        return

    bucket = min(100, (percent // 10) * 10)
    last_bucket = getattr(print_progress, '_last_plain_bucket', -10)
    if bucket >= 100 or bucket > last_bucket:
        log_info(f'Download progress: {bucket}%')
        setattr(print_progress, '_last_plain_bucket', bucket)
    if downloaded >= total:
        setattr(print_progress, '_last_plain_bucket', -10)


def download_5e_demos(config: Config):
    """下载所有 5E 用户的 Demo"""
    users = config.get_users_5e()
    if not users:
        log_info('No 5E users configured.')
        return

    for user in users:
        log_info(f'Downloading 5E demos for {user.label}.')
        if config.save_metadata_with_demo:
            metadata_matches = get_5e_metadata(user.userid)
            if not metadata_matches:
                log_info(f'No demos found for {user.label}.')
                continue

            log_info(f'Found {len(metadata_matches)} demos.')
            for match in metadata_matches:
                if not match.demo_url:
                    continue
                log_info(f'Match {match.match_id}: {match.demo_url}')
                if download_and_extract(match.demo_url, config.download_path, print_progress):
                    write_demo_metadata(match, config.download_path)
                print(flush=True)
            continue

        demo_urls = get_5e_demos(user.userid)

        if not demo_urls:
            log_info(f'No demos found for {user.label}.')
            continue

        log_info(f'Found {len(demo_urls)} demos.')

        for match_id, demo_url in demo_urls.items():
            log_info(f'Match {match_id}: {demo_url}')
            download_and_extract(demo_url, config.download_path, print_progress)
            print()


def download_pwa_demos(config: Config):
    """下载所有完美世界用户的 Demo"""
    users = config.get_users_pwa()
    if not users:
        log_info('No PWA users configured.')
        return

    for user in users:
        log_info(f'Downloading PWA demos for {user.label}.')
        try:
            signer = build_pwa_demo_url_signer(config)
        except RuntimeError as e:
            log_error(f'Unable to configure PWA signer for {user.label}: {e}')
            continue
        decryptor = build_pwa_et_decryptor(config)
        if config.save_metadata_with_demo:
            metadata_matches = get_pwa_metadata(
                user.steamid,
                user.access_token,
                signer=signer,
                et_decryptor=decryptor,
            )
            if not metadata_matches:
                log_info(f'No demos found for {user.label}.')
                continue

            log_info(f'Found {len(metadata_matches)} demos.')
            for match in metadata_matches:
                if not match.demo_url:
                    continue
                log_info(f'Match {match.match_id}: {redact_url(match.demo_url)}')
                try:
                    headers = build_pwa_download_headers(user.steamid)
                except RuntimeError as e:
                    log_error(f'Unable to build PWA download headers for {user.label}: {e}')
                    continue
                if download_and_extract(match.demo_url, config.download_path, print_progress, headers=headers):
                    write_demo_metadata(match, config.download_path)
                print(flush=True)
            continue

        demo_urls = get_pwa_demos(user.steamid, user.access_token, signer=signer, et_decryptor=decryptor)

        if not demo_urls:
            log_info(f'No demos found for {user.label}.')
            continue

        log_info(f'Found {len(demo_urls)} demos.')

        for match_id, demo_url in demo_urls.items():
            log_info(f'Match {match_id}: {redact_url(demo_url)}')
            try:
                headers = build_pwa_download_headers(user.steamid)
            except RuntimeError as e:
                log_error(f'Unable to build PWA download headers for {user.label}: {e}')
                continue
            download_and_extract(demo_url, config.download_path, print_progress, headers=headers)
            print()


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

    message = (
        f"Unsupported PWA signature_provider '{provider}'. "
        "Use 'compiled', 'pvp_alive_native', or 'pvp_alive_wine'."
    )
    raise RuntimeError(message)


def metadata_path_for_demo_url(demo_url: str, demo_path: str) -> str:
    demo_filename = get_demo_filename_from_url(demo_url)
    base_name, _extension = os.path.splitext(demo_filename)
    return os.path.join(demo_path, f'{base_name}.metadata.json')


def write_demo_metadata(match: MatchMetadata, demo_path: str) -> str | None:
    if not match.demo_url:
        return None
    metadata_path = metadata_path_for_demo_url(match.demo_url, demo_path)
    payload = metadata_list_to_dicts([match], include_raw=False)[0]
    try:
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as metadata_file:
            json.dump(payload, metadata_file, ensure_ascii=False, indent=2)
            metadata_file.write('\n')
    except OSError as e:
        log_error(f"Error writing metadata '{metadata_path}': {e}")
        return None
    log_info(f'Metadata saved to {metadata_path}')
    return metadata_path


def build_pwa_et_decryptor(config: Config) -> PwaEtDecryptor | None:
    pwa_config = config.pwa or {}
    executable_path = pwa_config.get('et_decryptor_exe') or pwa_config.get('pwa_response_decryptor_exe') or ''
    if not executable_path.strip():
        return None
    timeout = int(pwa_config.get('et_decryptor_timeout', pwa_config.get('pwa_response_decryptor_timeout', '10')))

    def decryptor(encrypted: str, token: str) -> str:
        return call_pwa_et_decryptor_exe(
            encrypted=encrypted,
            token=token,
            executable_path=executable_path,
            timeout=timeout,
        )

    return decryptor


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
        log_info('No Steam users configured.')
        return

    demo_url_resolver = build_steam_demo_url_resolver(config)

    for user in users:
        log_info(f'Downloading Steam official demos for {user.label}.')
        demo_urls = get_steam_demos(
            user.api_key,
            user.steamid,
            user.steamidkey,
            user.knowncode,
            demo_url_resolver=demo_url_resolver,
        )

        if not demo_urls:
            log_info(f'No demos found for {user.label}.')
            continue

        log_info(f'Found {len(demo_urls)} demos.')

        for match_id, demo_url in demo_urls.items():
            log_info(f'Match {match_id}: {demo_url}')
            download_and_extract(demo_url, config.download_path, print_progress)
            print()


def run_download(config: Config, output_path: str | None = None, platforms: list[str] | None = None) -> int:
    if output_path:
        config.download_path = output_path

    if not config.download_path:
        config.download_path = os.path.join(os.getcwd(), 'demos')

    try:
        os.makedirs(config.download_path, exist_ok=True)
    except OSError as e:
        log_error(f"Error creating download path '{config.download_path}': {e}")
        return 1

    log_info(f'Download path: {config.download_path}')

    selected_platforms = platforms or list(VALID_PLATFORMS)
    for platform in selected_platforms:
        if platform == '5e':
            download_5e_demos(config)
        elif platform == 'pwa':
            download_pwa_demos(config)
        elif platform == 'steam':
            download_steam_demos(config)

    log_info('Download complete.')
    return 0


def run_download_command(
    config_path: str | None,
    output_path: str | None,
    platform: str | None,
    all_platforms: bool,
) -> int:
    try:
        config_path = _ensure_default_config(config_path, os.environ)
        config = load_config(config_path)
    except (ConfigLoadError, SchedulerConfigError, OSError) as e:
        log_error(str(e))
        return 1

    platforms = None if all_platforms or platform is None else [platform]
    return run_download(config, output_path=output_path, platforms=platforms)


def collect_5e_metadata(config: Config, limit: int) -> list[MatchMetadata]:
    users = config.get_users_5e()
    if not users:
        return []

    matches: list[MatchMetadata] = []
    for user in users:
        matches.extend(get_5e_metadata(user.userid, limit=limit))
    return matches


def collect_pwa_metadata(config: Config, limit: int) -> list[MatchMetadata]:
    users = config.get_users_pwa()
    if not users:
        return []

    matches: list[MatchMetadata] = []
    for user in users:
        try:
            signer = build_pwa_demo_url_signer(config)
        except RuntimeError as e:
            log_error(f'Unable to configure PWA signer for {user.label}: {e}')
            continue
        decryptor = build_pwa_et_decryptor(config)
        matches.extend(get_pwa_metadata(user.steamid, user.access_token, size=limit, signer=signer, et_decryptor=decryptor))
    return matches


def run_metadata(
    config: Config,
    platform: str | None = None,
    all_platforms: bool = False,
    limit: int = 20,
    pretty: bool = False,
    include_raw: bool = False,
) -> int:
    selected_platforms = list(METADATA_PLATFORMS) if all_platforms or platform is None else [platform]
    matches: list[MatchMetadata] = []

    for selected_platform in selected_platforms:
        if selected_platform == '5e':
            matches.extend(collect_5e_metadata(config, limit=limit))
        elif selected_platform == 'pwa':
            matches.extend(collect_pwa_metadata(config, limit=limit))

    payload = metadata_list_to_dicts(
        matches,
        include_raw=include_raw,
    )
    indent = 2 if pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent))
    return 0


def run_metadata_command(
    config_path: str | None,
    platform: str | None,
    all_platforms: bool,
    limit: int,
    pretty: bool,
    include_raw: bool,
) -> int:
    try:
        config = load_config(config_path)
    except ConfigLoadError as e:
        log_error(str(e))
        return 1

    return run_metadata(
        config,
        platform=platform,
        all_platforms=all_platforms,
        limit=limit,
        pretty=pretty,
        include_raw=include_raw,
    )


def _parse_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise SchedulerConfigError(f"Invalid boolean for {field_name}: {value}")


def _parse_positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as e:
        raise SchedulerConfigError(f"{field_name} must be a positive integer") from e

    if parsed <= 0:
        raise SchedulerConfigError(f"{field_name} must be a positive integer")
    return parsed


def _parse_daily_time(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(':')
    if len(parts) != 2:
        raise SchedulerConfigError(f"{field_name} must use HH:MM format")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as e:
        raise SchedulerConfigError(f"{field_name} must use HH:MM format") from e
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise SchedulerConfigError(f"{field_name} must be between 00:00 and 23:59")
    return f'{hour:02d}:{minute:02d}'


def _seconds_until_daily_time(daily_time: str, now: datetime.datetime | None = None) -> int:
    current = now or datetime.datetime.now().astimezone()
    hour_text, minute_text = daily_time.split(':', 1)
    target = current.replace(
        hour=int(hour_text),
        minute=int(minute_text),
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += datetime.timedelta(days=1)
    return max(1, int((target - current).total_seconds()))


def _should_create_default_config(env: Mapping[str, str]) -> bool:
    value = _env_value(env, 'CS_DEMO_CREATE_DEFAULT_CONFIG', 'CS_DEMO_DOCKER_AUTO_CONFIG')
    if value is None:
        return False
    return _parse_bool(value, 'CS_DEMO_CREATE_DEFAULT_CONFIG')


def _ensure_default_config(config_path: str | None, env: Mapping[str, str]) -> str | None:
    if not _should_create_default_config(env):
        return config_path

    target_path = config_path or '/config/config.jsonc'
    if os.path.exists(target_path):
        return target_path

    write_default_docker_config(target_path)
    log_info(f'Created default Docker config at {target_path}. Edit the mounted config file with your account settings.')
    return target_path


def _resolve_daily_time(
    cli_daily_time: str | None,
    env: Mapping[str, str],
    config: Config,
) -> str | None:
    if cli_daily_time is not None:
        return _parse_daily_time(cli_daily_time, 'daily_time')

    env_daily_time = _env_value(env, 'CS_DEMO_SCHEDULE_DAILY_TIME')
    if env_daily_time is not None:
        return _parse_daily_time(env_daily_time, 'CS_DEMO_SCHEDULE_DAILY_TIME')

    return _parse_daily_time(_scheduler_value(config, 'daily_time'), 'scheduler.daily_time')


def _next_wait_seconds(settings: SchedulerSettings) -> int:
    if settings.daily_time:
        return _seconds_until_daily_time(settings.daily_time)
    return settings.interval_seconds


def _schedule_description(settings: SchedulerSettings) -> str:
    if settings.daily_time:
        return f'daily at {settings.daily_time}'
    return f'every {settings.interval_seconds} seconds'


def _env_value(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        if name in env:
            return env[name]
    return None


def _scheduler_value(config: Config, *names: str) -> object | None:
    scheduler = config.scheduler or {}
    for name in names:
        value = scheduler.get(name)
        if value is not None:
            return value
    return None


def _normalize_platforms(value: object, field_name: str) -> str | list[str] | None:
    if isinstance(value, str):
        raw_values = value.split(',')
    elif isinstance(value, (list, tuple)):
        raw_values = value
    else:
        raise SchedulerConfigError(
            f"Invalid scheduler platform '{value}'. Use values from: {', '.join(SCHEDULE_PLATFORM_VALUES)}."
        )

    platforms: list[str] = []
    for raw_value in raw_values:
        platform = str(raw_value).strip().lower()
        if not platform:
            continue
        if platform == 'all':
            if len([item for item in raw_values if str(item).strip()]) > 1:
                raise SchedulerConfigError(
                    f"Invalid scheduler platform '{value}'. Use 'all' alone or values from: {', '.join(VALID_PLATFORMS)}."
                )
            return None
        if platform not in VALID_PLATFORMS:
            raise SchedulerConfigError(
                f"Invalid scheduler platform '{platform}'. Use values from: {', '.join(SCHEDULE_PLATFORM_VALUES)}."
            )
        if platform not in platforms:
            platforms.append(platform)

    if not platforms:
        raise SchedulerConfigError(
            f"Invalid scheduler platform '{value}'. Use values from: {', '.join(SCHEDULE_PLATFORM_VALUES)}."
        )
    if len(platforms) == 1:
        return platforms[0]
    return platforms


def _platform_list(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    return [value]


def _resolve_interval_seconds(
    cli_interval: int | None,
    env: Mapping[str, str],
    config: Config,
) -> int:
    if cli_interval is not None:
        return _parse_positive_int(cli_interval, 'interval_seconds')

    env_seconds = _env_value(env, 'CS_DEMO_SCHEDULE_INTERVAL_SECONDS')
    if env_seconds is not None:
        return _parse_positive_int(env_seconds, 'CS_DEMO_SCHEDULE_INTERVAL_SECONDS')

    env_minutes = _env_value(env, 'CS_DEMO_SCHEDULE_INTERVAL_MINUTES')
    if env_minutes is not None:
        return _parse_positive_int(env_minutes, 'CS_DEMO_SCHEDULE_INTERVAL_MINUTES') * 60

    env_hours = _env_value(env, 'CS_DEMO_SCHEDULE_INTERVAL_HOURS')
    if env_hours is not None:
        return _parse_positive_int(env_hours, 'CS_DEMO_SCHEDULE_INTERVAL_HOURS') * 3600

    config_interval = _scheduler_value(config, 'interval_seconds')
    if config_interval is not None:
        return _parse_positive_int(config_interval, 'scheduler.interval_seconds')

    return 86400


def resolve_scheduler_settings(
    config_path: str | None = None,
    output_path: str | None = None,
    platforms: str | None = None,
    enabled: bool | None = None,
    interval_seconds: int | None = None,
    daily_time: str | None = None,
    run_on_start: bool | None = None,
    env: Mapping[str, str] | None = None,
    base_config: Config | None = None,
) -> SchedulerSettings:
    env_map = os.environ if env is None else env
    explicit_enabled = enabled
    env_enabled = None
    if explicit_enabled is None:
        env_enabled = _env_value(env_map, 'CS_DEMO_SCHEDULE_ENABLED')
        if env_enabled is not None:
            explicit_enabled = _parse_bool(env_enabled, 'enabled')

    if explicit_enabled is False and base_config is None:
        disabled_platforms = platforms or _env_value(
            env_map,
            'CS_DEMO_SCHEDULE_PLATFORMS',
            'CS_DEMO_SCHEDULE_PLATFORM',
        )
        return SchedulerSettings(
            enabled=False,
            interval_seconds=86400,
            daily_time=_parse_daily_time(_env_value(env_map, 'CS_DEMO_SCHEDULE_DAILY_TIME'), 'CS_DEMO_SCHEDULE_DAILY_TIME'),
            run_on_start=False,
            config_path=config_path or _env_value(env_map, 'CS_DEMO_SCHEDULE_CONFIG'),
            output_path=output_path or _env_value(env_map, 'CS_DEMO_SCHEDULE_OUTPUT'),
            platforms=_normalize_platforms(disabled_platforms, 'platforms') if disabled_platforms is not None else None,
        )

    env_config_path = _env_value(env_map, 'CS_DEMO_SCHEDULE_CONFIG')
    schedule_config_path = config_path or env_config_path
    if base_config is None:
        schedule_config_path = _ensure_default_config(schedule_config_path, env_map)
    config = base_config if base_config is not None else load_config(schedule_config_path)

    resolved_config_path = config_path or env_config_path or str(_scheduler_value(config, 'config') or '') or None
    resolved_output_path = (
        output_path
        or _env_value(env_map, 'CS_DEMO_SCHEDULE_OUTPUT')
        or str(_scheduler_value(config, 'output') or '')
        or None
    )

    platform_value = (
        platforms
        or _env_value(env_map, 'CS_DEMO_SCHEDULE_PLATFORMS', 'CS_DEMO_SCHEDULE_PLATFORM')
        or _scheduler_value(config, 'platforms', 'platform')
    )
    resolved_platforms = _normalize_platforms(platform_value, 'platforms') if platform_value is not None else None

    if enabled is not None:
        resolved_enabled = enabled
    else:
        env_enabled = _env_value(env_map, 'CS_DEMO_SCHEDULE_ENABLED')
        config_enabled = _scheduler_value(config, 'enabled')
        resolved_enabled = _parse_bool(env_enabled if env_enabled is not None else config_enabled or False, 'enabled')

    if run_on_start is not None:
        resolved_run_on_start = run_on_start
    else:
        env_run_on_start = _env_value(env_map, 'CS_DEMO_SCHEDULE_RUN_ON_START')
        config_run_on_start = _scheduler_value(config, 'run_on_start')
        resolved_run_on_start = _parse_bool(
            env_run_on_start if env_run_on_start is not None else config_run_on_start or False,
            'run_on_start',
        )

    return SchedulerSettings(
        enabled=resolved_enabled,
        interval_seconds=_resolve_interval_seconds(interval_seconds, env_map, config),
        daily_time=_resolve_daily_time(daily_time, env_map, config),
        run_on_start=resolved_run_on_start,
        config_path=resolved_config_path,
        output_path=resolved_output_path,
        platforms=resolved_platforms,
    )


def _install_signal_handlers(stop_event: threading.Event):
    def handle_shutdown(signum: int, _frame: FrameType | None):
        signal_name = signal.Signals(signum).name
        log_info(f'Received {signal_name}, stopping scheduler.')
        stop_event.set()

    for signal_name in ('SIGINT', 'SIGTERM'):
        shutdown_signal = getattr(signal, signal_name, None)
        if shutdown_signal is not None:
            signal.signal(shutdown_signal, handle_shutdown)


def _run_scheduled_download(settings: SchedulerSettings) -> int:
    platform_list = _platform_list(settings.platforms)
    if platform_list is None:
        return run_download_command(settings.config_path, settings.output_path, None, True)
    if len(platform_list) == 1:
        return run_download_command(settings.config_path, settings.output_path, platform_list[0], False)

    try:
        config = load_config(settings.config_path)
    except ConfigLoadError as e:
        log_error(str(e))
        return 1
    return run_download(config, output_path=settings.output_path, platforms=platform_list)


def run_schedule_command(
    config_path: str | None = None,
    output_path: str | None = None,
    platforms: str | None = None,
    enabled: bool | None = None,
    interval_seconds: int | None = None,
    daily_time: str | None = None,
    run_on_start: bool | None = None,
    env: Mapping[str, str] | None = None,
    stop_event: threading.Event | None = None,
    install_signal_handlers: bool = True,
    run_once: bool = False,
) -> int:
    try:
        settings = resolve_scheduler_settings(
            config_path=config_path,
            output_path=output_path,
            platforms=platforms,
            enabled=enabled,
            interval_seconds=interval_seconds,
            daily_time=daily_time,
            run_on_start=run_on_start,
            env=env,
        )
    except (ConfigLoadError, SchedulerConfigError) as e:
        log_error(str(e))
        return 1

    event = stop_event or threading.Event()

    if not settings.enabled:
        log_info(
            'Scheduler disabled. Container is idle. '
            'Set CS_DEMO_SCHEDULE_ENABLED=true or scheduler.enabled=true to enable automatic downloads.'
        )
        if run_once:
            return 0
        if install_signal_handlers:
            _install_signal_handlers(event)
        event.wait()
        return 0

    if install_signal_handlers:
        _install_signal_handlers(event)

    log_info(
        'Scheduler enabled: '
        f"mode={_schedule_description(settings)}, run_on_start={settings.run_on_start}, "
        f"platforms={','.join(_platform_list(settings.platforms) or list(VALID_PLATFORMS))}."
    )

    if settings.run_on_start:
        log_info('Running scheduled download immediately on startup.')
        exit_code = _run_scheduled_download(settings)
        if run_once:
            return exit_code
        if exit_code != 0:
            return exit_code
    else:
        log_info('Run-on-start disabled. First download will wait for the next schedule.')

    while True:
        wait_seconds = _next_wait_seconds(settings)
        log_info(f'Next scheduled download in {wait_seconds} seconds ({_schedule_description(settings)}).')
        if event.wait(wait_seconds):
            break
        exit_code = _run_scheduled_download(settings)
        if run_once:
            return exit_code
        if exit_code != 0:
            return exit_code

    return 0


def load_scheduler_settings(args: argparse.Namespace) -> SchedulerSettings:
    return resolve_scheduler_settings(
        config_path=args.config,
        output_path=getattr(args, 'output', None),
        platforms=getattr(args, 'platforms', None),
        enabled=getattr(args, 'enabled', None),
        interval_seconds=getattr(args, 'interval_seconds', None),
        daily_time=getattr(args, 'daily_time', None),
        run_on_start=getattr(args, 'run_on_start', None),
    )


def run_scheduler(args: argparse.Namespace) -> int:
    return run_schedule_command(
        config_path=args.config,
        output_path=getattr(args, 'output', None),
        platforms=getattr(args, 'platforms', None),
        enabled=getattr(args, 'enabled', None),
        interval_seconds=getattr(args, 'interval_seconds', None),
        daily_time=getattr(args, 'daily_time', None),
        run_on_start=getattr(args, 'run_on_start', None),
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description='CS Demo Downloader - 下载 5E、完美世界和 Steam 官匹 CS2 Demo'
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

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

    schedule_parser = subparsers.add_parser('schedule', help='启动内部定时下载调度器')
    schedule_parser.add_argument(
        '--config', type=str,
        help='调度配置文件路径；也可使用 CS_DEMO_SCHEDULE_CONFIG'
    )
    schedule_parser.add_argument(
        '--output', type=str,
        help='下载目录；也可使用 CS_DEMO_SCHEDULE_OUTPUT'
    )
    schedule_parser.add_argument(
        '--platforms', type=str,
        help='逗号分隔的平台列表，例如 5e,pwa,steam；也可使用 CS_DEMO_SCHEDULE_PLATFORMS'
    )
    schedule_parser.add_argument(
        '--enabled', action='store_true', default=None,
        help='启用定时下载；也可使用 CS_DEMO_SCHEDULE_ENABLED=true'
    )
    schedule_parser.add_argument(
        '--interval-seconds', type=int,
        help='定时下载间隔秒数；也可使用 CS_DEMO_SCHEDULE_INTERVAL_SECONDS'
    )
    schedule_parser.add_argument(
        '--daily-time', type=str,
        help='每天运行时间，格式 HH:MM；也可使用 CS_DEMO_SCHEDULE_DAILY_TIME'
    )
    schedule_parser.add_argument(
        '--run-on-start', action='store_true', default=None,
        help='启动调度器后立即运行一次；也可使用 CS_DEMO_SCHEDULE_RUN_ON_START=true'
    )

    metadata_parser = subparsers.add_parser('metadata', help='抓取并输出 Demo metadata')
    metadata_parser.add_argument(
        '--all', action='store_true',
        help='抓取所有支持 metadata 的平台'
    )
    metadata_parser.add_argument(
        '--platform', choices=list(METADATA_PLATFORMS),
        help='只抓取指定平台的 Demo metadata'
    )
    metadata_parser.add_argument(
        '--config', type=str,
        help='配置文件路径'
    )
    metadata_parser.add_argument(
        '--limit', type=int, default=20,
        help='每个用户最多抓取的比赛数量'
    )
    metadata_parser.add_argument(
        '--pretty', action='store_true',
        help='格式化 JSON 输出'
    )
    metadata_parser.add_argument(
        '--include-raw', action='store_true',
        help='在 JSON 输出中包含平台原始字段'
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

    args = parser.parse_args(argv)

    if args.command == 'download':
        return run_download_command(args.config, args.output, args.platform, args.all)
    if args.command == 'schedule':
        return run_schedule_command(
            config_path=args.config,
            output_path=args.output,
            platforms=args.platforms,
            enabled=args.enabled,
            interval_seconds=args.interval_seconds,
            daily_time=args.daily_time,
            run_on_start=args.run_on_start,
        )
    if args.command == 'metadata':
        return run_metadata_command(
            args.config,
            args.platform,
            args.all,
            args.limit,
            args.pretty,
            args.include_raw,
        )
    if args.command == 'update-pvpalive-dll':
        try:
            dll_path = update_cached_pvp_alive_dll(
                latest_yml_url=args.latest_yml_url,
                target_path=args.target,
                timeout=args.timeout,
                force=args.force,
            )
        except PvpAliveUpdateError as e:
            log_error(f'Error updating PvpAlive.dll: {e}')
            return 1

        log_info(f'Updated PvpAlive.dll: {dll_path}')
        return 0

    parser.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
