"""Fetch PWA matches without printing signed Demo URLs."""

from __future__ import annotations

import json
import os

from cs_demo_downloader.core.downloader_pwa import get_all_demo_metadata


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set the {name} environment variable first.")
    return value


def main() -> None:
    steamid = _required_env("PWA_STEAMID")
    access_token = _required_env("PWA_ACCESS_TOKEN")
    size = int(os.environ.get("PWA_MATCH_LIMIT", "20"))
    season = os.environ.get("PWA_SEASON")
    max_seasons = int(os.environ.get("PWA_MAX_SEASONS", "3"))

    matches = get_all_demo_metadata(
        steamid,
        access_token,
        size=size,
        report_fetcher=None,
        extra_fetcher=None,
        season=season,
        max_seasons=max_seasons,
    )
    output = [
        {
            "match_id": match.match_id,
            "demo_available": match.demo_available,
        }
        for match in matches
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
