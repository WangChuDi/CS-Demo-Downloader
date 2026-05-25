"""Steam login based resolver for headless Steam GC access."""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


class SteamLoginResolverError(RuntimeError):
    """Raised when Steam login resolver is unavailable or fails."""


def extract_demo_url_from_match_list(message: object) -> Optional[str]:
    """Extract the first `.dem.bz2` URL from a Steam GC match-list message."""
    matches = getattr(message, 'matches', [])
    for match in matches:
        round_stats = getattr(match, 'roundstatsall', [])
        for stats in round_stats:
            demo_url = getattr(stats, 'map', '')
            if isinstance(demo_url, str) and demo_url.endswith('.dem.bz2'):
                return demo_url
    return None


def generate_two_factor_code(shared_secret: str) -> Optional[str]:
    if not shared_secret:
        return None
    try:
        steam_guard = importlib.import_module('steam.guard')
    except ImportError as e:
        raise SteamLoginResolverError(
            "steam-login resolver requires the optional 'steam' package for two-factor code generation."
        ) from e
    return steam_guard.generate_twofactor_code(shared_secret)


@dataclass
class SteamLoginResolver:
    """Resolve Steam share codes through ValvePython steam/csgo GC login."""

    username_env: str = "STEAM_GC_USERNAME"
    password_env: str = "STEAM_GC_PASSWORD"
    two_factor_secret_env: str = "STEAM_GC_TWO_FACTOR_SECRET"
    auth_code_env: str = "STEAM_GC_AUTH_CODE"
    sentry_dir: Optional[str] = None
    timeout: int = 30

    def resolve_demo_url(self, share_code: str, decoded: Dict[str, int]) -> Optional[str]:
        username = os.getenv(self.username_env)
        password = os.getenv(self.password_env)
        if not username or not password:
            raise SteamLoginResolverError(
                "Steam login resolver requires environment variables "
                f"{self.username_env} and {self.password_env}."
            )

        required = ("matchid", "outcomeid", "token")
        missing = [key for key in required if key not in decoded]
        if missing:
            raise SteamLoginResolverError(f"Missing decoded share-code fields: {', '.join(missing)}")

        try:
            steam_client_module = importlib.import_module('steam.client')
            csgo_client_module = importlib.import_module('csgo.client')
        except ImportError as e:
            raise SteamLoginResolverError(
                "Steam login resolver requires optional dependencies. "
                "Install with cs-demo-downloader[steam-login]."
            ) from e

        steam_client = steam_client_module.SteamClient()
        if self.sentry_dir:
            Path(self.sentry_dir).mkdir(parents=True, exist_ok=True)
            steam_client.set_credential_location(self.sentry_dir)

        two_factor_secret = os.getenv(self.two_factor_secret_env, '')
        auth_code = os.getenv(self.auth_code_env)
        two_factor_code = generate_two_factor_code(two_factor_secret) if two_factor_secret else None

        csgo_client = None
        try:
            result = steam_client.login(
                username,
                password,
                auth_code=auth_code,
                two_factor_code=two_factor_code,
            )
            if str(result) != 'OK' and getattr(result, 'name', '') != 'OK':
                raise SteamLoginResolverError(f"Steam login failed: {result}")

            csgo_client = csgo_client_module.CSGOClient(steam_client)
            csgo_client.launch()
            csgo_client.wait_event('ready', timeout=self.timeout, raises=True)
            csgo_client.request_full_match_info(
                decoded['matchid'],
                decoded['outcomeid'],
                decoded['token'],
            )
            message = csgo_client.wait_event('full_match_info', timeout=self.timeout, raises=True)[0]
            demo_url = extract_demo_url_from_match_list(message)
            if not demo_url:
                raise SteamLoginResolverError("Steam GC match info did not contain a demo URL")
            return demo_url
        finally:
            try:
                if csgo_client is not None:
                    csgo_client.exit()
            finally:
                try:
                    steam_client.logout()
                except Exception:
                    steam_client.disconnect()
