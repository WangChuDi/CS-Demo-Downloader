"""Fetch signed PWA Demo URLs.

The generated URLs contain the PWA access token. Keep the output private.
"""

from __future__ import annotations

import os

from cs_demo_downloader.core.downloader_pwa import get_all_demo_urls


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set the {name} environment variable first.")
    return value


def main() -> None:
    steamid = _required_env("PWA_STEAMID")
    access_token = _required_env("PWA_ACCESS_TOKEN")
    size = int(os.environ.get("PWA_MATCH_LIMIT", "20"))

    demo_urls = get_all_demo_urls(steamid, access_token, size=size)
    for match_id, demo_url in demo_urls.items():
        print(f"{match_id}\t{demo_url}")


if __name__ == "__main__":
    main()
