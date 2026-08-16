"""Fetch and decode the next Steam official matchmaking share code."""

from __future__ import annotations

import json
import os

from cs_demo_downloader.core.downloader_steam import decode_share_code, get_next_share_code


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set the {name} environment variable first.")
    return value


def main() -> None:
    next_code = get_next_share_code(
        api_key=_required_env("STEAM_API_KEY"),
        steamid=_required_env("STEAM_ID64"),
        steamidkey=_required_env("STEAM_ID_KEY"),
        knowncode=_required_env("STEAM_KNOWN_CODE"),
    )
    if not next_code:
        raise SystemExit("No newer share code was returned.")

    print(next_code)
    print(json.dumps(decode_share_code(next_code), indent=2))


if __name__ == "__main__":
    main()
