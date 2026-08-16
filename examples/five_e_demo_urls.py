"""Fetch recent 5EPlay Demo URLs."""

from __future__ import annotations

import os

from cs_demo_downloader.core.downloader_5e import get_all_demo_urls


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set the {name} environment variable first.")
    return value


def main() -> None:
    userid = _required_env("FIVE_E_USERID")
    limit = int(os.environ.get("FIVE_E_MATCH_LIMIT", "20"))

    demo_urls = get_all_demo_urls(userid, limit=limit)
    for match_id, demo_url in demo_urls.items():
        print(f"{match_id}\t{demo_url}")


if __name__ == "__main__":
    main()
