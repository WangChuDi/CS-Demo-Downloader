"""
Steam official matchmaking demo downloader.
"""
import re
from typing import Callable, Dict, Optional

import requests

from .logging import log_error, log_info


SHARE_CODE_CHARS = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
BITMASK64 = 2**64 - 1
GET_NEXT_MATCH_SHARING_CODE_URL = (
    "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1/"
)


def _swap_endianness(number: int) -> int:
    result = 0
    for n in range(0, 144, 8):
        result = (result << 8) + ((number >> n) & 0xFF)
    return result


def decode_share_code(code: str) -> Dict[str, int]:
    """Decode a CS official matchmaking share code."""
    if not re.match(r"^(CSGO)?(-?[%s]{5}){5}$" % SHARE_CODE_CHARS, code):
        raise ValueError("Invalid Steam match share code")

    compact_code = re.sub(r"CSGO\-|\-", "", code)[::-1]
    value = 0
    for character in compact_code:
        value = value * len(SHARE_CODE_CHARS) + SHARE_CODE_CHARS.index(character)

    value = _swap_endianness(value)
    return {
        "matchid": value & BITMASK64,
        "outcomeid": (value >> 64) & BITMASK64,
        "token": (value >> 128) & 0xFFFF,
    }


def get_next_share_code(
    api_key: str,
    steamid: str,
    steamidkey: str,
    knowncode: str,
) -> Optional[str]:
    """Fetch the next Steam official matchmaking share code."""
    params = {
        "key": api_key,
        "steamid": steamid,
        "steamidkey": steamidkey,
        "knowncode": knowncode,
    }

    try:
        response = requests.get(GET_NEXT_MATCH_SHARING_CODE_URL, params=params, timeout=10)
        if response.status_code != 200:
            log_error(f"Failed to get Steam share code, status: {response.status_code}")
            return None

        data = response.json()
        return data.get("result", {}).get("nextcode")
    except requests.RequestException as e:
        log_error(f"Error getting Steam share code: {e}")
        return None


SteamDemoUrlResolver = Callable[[str, Dict[str, int]], Optional[str]]


def resolve_demo_url_from_share_code(
    share_code: str,
    demo_url_resolver: Optional[SteamDemoUrlResolver] = None,
) -> Optional[str]:
    """Resolve a Steam share code to a real Valve replay URL.

    `GetNextMatchSharingCode` only returns share codes. A share code decodes to
    `matchid`, `outcomeid`, and `token`, but those values are not enough to
    synthesize a valid replay URL. The real `.dem.bz2` URL must come from Steam
    Game Coordinator full match info, usually the match `map` field.
    """
    try:
        decoded = decode_share_code(share_code)
    except ValueError as e:
        log_error(f"Error decoding Steam share code: {e}")
        return None

    if demo_url_resolver is None:
        log_info(
            'Steam share code resolved, but Steam GC match-info resolver is not configured. '
            'Cannot get a real replay URL from Web API data alone.'
        )
        return None

    return demo_url_resolver(share_code, decoded)


def get_all_demo_urls(
    api_key: str,
    steamid: str,
    steamidkey: str,
    knowncode: str,
    limit: int = 20,
    demo_url_resolver: Optional[SteamDemoUrlResolver] = None,
) -> Dict[str, str]:
    """Fetch recent Steam official matchmaking demo URLs.

    Steam exposes match history as a cursor-style Web API where `knowncode` is
    the starting share code and each response returns the next share code. Real
    replay URLs still require Steam Game Coordinator full match info, supplied
    here through `demo_url_resolver`.
    """
    demo_urls: Dict[str, str] = {}
    current_code = knowncode

    for _ in range(limit):
        next_code = get_next_share_code(api_key, steamid, steamidkey, current_code)
        if not next_code or next_code == "n/a" or next_code in demo_urls:
            break

        demo_url = resolve_demo_url_from_share_code(next_code, demo_url_resolver)
        if demo_url:
            demo_urls[next_code] = demo_url

        current_code = next_code

    return demo_urls
