"""Exercise the public API surface with explicit parameter values.

Run without ``--live`` for deterministic local checks. Add ``--live`` and
the platform environment variables to exercise network-backed functions.
The script reports function names and status only; it never prints results
that may contain access tokens or API keys.
"""

from __future__ import annotations

import argparse
import bz2
import datetime as dt
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from cs_demo_downloader.core import config, downloader_5e, downloader_pwa, downloader_steam, logging, metadata, utils


def _run(name: str, function: Callable[[], Any]) -> Any:
    try:
        result = function()
    except Exception as error:
        print(f"ERROR {name}: {type(error).__name__}")
        return None
    print(f"OK    {name}")
    return result


def _skip(name: str, reason: str) -> None:
    print(f"SKIP  {name}: {reason}")


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


def run_local_examples() -> None:
    _run("config.default_docker_config_data", config.default_docker_config_data)
    _run("config.get_config_path", config.get_config_path)
    _run(
        "config.strip_jsonc_comments",
        lambda: config.strip_jsonc_comments('{"value": 1} // comment\n'),
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        config_path = str(Path(temporary_directory) / "config.jsonc")
        _run("config.write_default_docker_config", lambda: config.write_default_docker_config(config_path))
        loaded_config = _run("config.load_config", lambda: config.load_config(config_path))
        if loaded_config is not None:
            _run("config.save_config", lambda: config.save_config(loaded_config, config_path))

        zip_path = Path(temporary_directory) / "sample.zip"
        extract_path = Path(temporary_directory) / "unzipped"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("sample.txt", "demo")
        _run("utils.unzip_file", lambda: utils.unzip_file(str(zip_path), str(extract_path)))

        bz2_path = Path(temporary_directory) / "sample.dem.bz2"
        dem_path = Path(temporary_directory) / "sample.dem"
        bz2_path.write_bytes(bz2.compress(b"demo"))
        _run("utils.extract_bz2_file", lambda: utils.extract_bz2_file(str(bz2_path), str(dem_path)))

    download_url = _env("EXAMPLE_DOWNLOAD_URL")
    if download_url:
        with tempfile.TemporaryDirectory() as temporary_directory:
            download_path = str(Path(temporary_directory) / "downloaded.bin")
            progress = lambda _downloaded, _total: None
            _run(
                "utils.download_file",
                lambda: utils.download_file(
                    download_url,
                    download_path,
                    progress_callback=progress,
                    headers={"User-Agent": "cs-demo-downloader-example"},
                ),
            )
            _run(
                "utils.download_and_extract",
                lambda: utils.download_and_extract(
                    download_url,
                    str(Path(temporary_directory) / "downloaded.dem"),
                    progress_callback=progress,
                    headers={"User-Agent": "cs-demo-downloader-example"},
                ),
            )
    else:
        _skip("utils.download_file/download_and_extract", "set EXAMPLE_DOWNLOAD_URL to enable network download checks")

    _run("metadata.json_object", lambda: metadata.json_object({"key": "value"}))
    _run("metadata.to_json_value", lambda: metadata.to_json_value({"key": 1}))
    _run("metadata.optional_str", lambda: metadata.optional_str(123))
    _run("metadata.optional_int", lambda: metadata.optional_int("123"))
    _run("metadata.optional_float", lambda: metadata.optional_float("1.5"))
    _run("metadata.metadata_list_to_dicts", lambda: metadata.metadata_list_to_dicts([], include_raw=False))

    stream = io.StringIO()
    _run("logging.log_info", lambda: logging.log_info("example", stream=stream))
    _run("logging.log_error", lambda: logging.log_error("example error"))

    _run("utils.redact_url", lambda: utils.redact_url("https://example.test/demo?access_token=secret"))
    _run("utils.get_end_of_day_timestamp", lambda: utils.get_end_of_day_timestamp(dt.date(2026, 1, 1)))
    _run("utils.get_timestamp_days_ago", lambda: utils.get_timestamp_days_ago(1))
    _run("utils.get_demo_filename_from_url", lambda: utils.get_demo_filename_from_url("https://example.test/a.dem"))


def run_pwa_examples(live: bool) -> None:
    configured_credentials = bool(_env("PWA_STEAMID") and _env("PWA_ACCESS_TOKEN"))
    steamid = _env("PWA_STEAMID") or "76561198159976336"
    access_token = _env("PWA_ACCESS_TOKEN") or "EXAMPLE_PWA_ACCESS_TOKEN"
    season = _env("PWA_SEASON")
    acw_tc = _env("PWA_ACW_TC")
    decryptor_exe = _env("PWA_RESPONSE_DECRYPTOR_EXE")
    decryptor_timeout = int(os.environ.get("PWA_RESPONSE_DECRYPTOR_TIMEOUT", "10"))
    signer = downloader_pwa.sign_demo_request
    decryptor = lambda _encrypted, _token: {"example": True}

    _run("pwa.sign_demo_request", lambda: downloader_pwa.sign_demo_request("123456", "1700000000", "a=1"))
    _run("pwa.build_x_pwa_signature", lambda: downloader_pwa.build_x_pwa_signature(steamid, 1700000000, "127.0.0.1"))
    _run(
        "pwa.build_download_headers",
        lambda: downloader_pwa.build_download_headers(steamid, public_ip="127.0.0.1", timestamp=1700000000),
    )
    _run("pwa.build_pwa_list_headers", lambda: downloader_pwa.build_pwa_list_headers(steamid, access_token, acw_tc=acw_tc))
    _run(
        "pwa.decrypt_pwa_et_payload",
        lambda: downloader_pwa.decrypt_pwa_et_payload(
            "encrypted", "token", decryptor=decryptor, decryptor_exe=decryptor_exe, decryptor_timeout=decryptor_timeout
        ),
    )
    if decryptor_exe:
        _run(
            "pwa.call_pwa_et_decryptor_exe",
            lambda: downloader_pwa.call_pwa_et_decryptor_exe("encrypted", "token", decryptor_exe, timeout=1),
        )
    else:
        _skip("pwa.call_pwa_et_decryptor_exe", "set PWA_RESPONSE_DECRYPTOR_EXE to test the executable boundary")
    _run(
        "pwa.get_demo_url",
        lambda: downloader_pwa.get_demo_url("example-match", access_token, cup_id=0, signer=signer),
    )
    _run(
        "pwa.build_match_metadata",
        lambda: downloader_pwa.build_match_metadata({"match": "example-match"}, "https://example.test/demo", report_data=None),
    )

    if not live:
        _skip("PWA network API", "pass --live to call external endpoints")
        return
    if not configured_credentials:
        _skip("PWA network API", "set PWA_STEAMID and PWA_ACCESS_TOKEN")
        return

    _run(
        "pwa.get_current_season",
        lambda: downloader_pwa.get_current_season(steamid, access_token, acw_tc=acw_tc),
    )
    _run("pwa.get_public_ip", downloader_pwa.get_public_ip)
    _run(
        "pwa.get_season_ladder_records",
        lambda: downloader_pwa.get_season_ladder_records(steamid, access_token, ignore_season=season, acw_tc=acw_tc),
    )
    _run(
        "pwa.get_candidate_season_records",
        lambda: downloader_pwa.get_candidate_season_records(steamid, access_token, max_seasons=3, acw_tc=acw_tc),
    )
    _run(
        "pwa.get_match_list",
        lambda: downloader_pwa.get_match_list(
            steamid,
            access_token,
            size=3,
            signer=signer,
            season=season,
            max_seasons=3,
            et_decryptor=decryptor,
            et_decryptor_exe=decryptor_exe,
            et_decryptor_timeout=decryptor_timeout,
        ),
    )
    records = _run(
        "pwa.get_match_list_records",
        lambda: downloader_pwa.get_match_list_records(
            steamid,
            access_token,
            size=3,
            signer=signer,
            acw_tc=acw_tc,
            season=season,
            max_seasons=3,
            et_decryptor=decryptor,
            et_decryptor_exe=decryptor_exe,
            et_decryptor_timeout=decryptor_timeout,
        ),
    )
    _run(
        "pwa.get_all_demo_urls",
        lambda: downloader_pwa.get_all_demo_urls(
            steamid,
            access_token,
            size=3,
            signer=signer,
            season=season,
            max_seasons=3,
            et_decryptor=decryptor,
            et_decryptor_exe=decryptor_exe,
            et_decryptor_timeout=decryptor_timeout,
        ),
    )
    _run(
        "pwa.get_all_demo_metadata",
        lambda: downloader_pwa.get_all_demo_metadata(
            steamid,
            access_token,
            size=3,
            signer=signer,
            report_fetcher=lambda _match_id, _steamid, _token: None,
            extra_fetcher=lambda _match_id, _steamid, _token: {},
            season=season,
            max_seasons=3,
            et_decryptor=decryptor,
            et_decryptor_exe=decryptor_exe,
            et_decryptor_timeout=decryptor_timeout,
        ),
    )

    match_id = records[0].get("match") if isinstance(records, list) and records else None
    if not isinstance(match_id, str):
        _skip("pwa.fetch_* functions", "no match was returned")
        return
    _run("pwa.fetch_match_report", lambda: downloader_pwa.fetch_match_report(match_id, steamid, access_token))
    _run("pwa.fetch_perfect_moment", lambda: downloader_pwa.fetch_perfect_moment(match_id))
    _run(
        "pwa.fetch_match_round_simple_list",
        lambda: downloader_pwa.fetch_match_round_simple_list(match_id, steamid, access_token),
    )
    _run("pwa.fetch_match_extra_data", lambda: downloader_pwa.fetch_match_extra_data(match_id, steamid, access_token))


def run_five_e_examples(live: bool) -> None:
    userid = _env("FIVE_E_USERID")
    _run(
        "5e.build_match_metadata",
        lambda: downloader_5e.build_match_metadata({"match_id": "example"}, {"match_id": "example"}),
    )
    if not live:
        _skip("5E network API", "pass --live to call external endpoints")
        return
    if not userid:
        _skip("5E network API", "set FIVE_E_USERID")
        return

    limit = int(os.environ.get("FIVE_E_MATCH_LIMIT", "3"))
    start_time = int(os.environ.get("FIVE_E_START_TIMESTAMP", "0"))
    end_time = int(os.environ.get("FIVE_E_END_TIMESTAMP", "4102444800"))

    uuid = _run("5e.get_uuid", lambda: downloader_5e.get_uuid(userid))
    if not isinstance(uuid, str):
        _skip("5E match API", "the user ID did not resolve to a UUID")
        return
    records = _run(
        "5e.get_match_list_records",
        lambda: downloader_5e.get_match_list_records(uuid, start_time=start_time, end_time=end_time, limit=limit),
    )
    _run(
        "5e.get_match_list",
        lambda: downloader_5e.get_match_list(uuid, start_time=start_time, end_time=end_time, limit=limit),
    )
    _run("5e.get_all_demo_urls", lambda: downloader_5e.get_all_demo_urls(userid, limit=limit))
    _run("5e.get_all_demo_metadata", lambda: downloader_5e.get_all_demo_metadata(userid, limit=limit))

    match_id = records[0].get("match_id") if isinstance(records, list) and records else None
    if not isinstance(match_id, str):
        _skip("5E detail API", "no match was returned")
        return
    _run("5e.get_demo_url", lambda: downloader_5e.get_demo_url(match_id))
    _run("5e.get_match_detail", lambda: downloader_5e.get_match_detail(match_id))
    _run("5e.get_match_advanced_data", lambda: downloader_5e.get_match_advanced_data(match_id))
    _run("5e.get_match_leetify_rating", lambda: downloader_5e.get_match_leetify_rating(match_id))
    _run("5e.get_match_vip_plus_data", lambda: downloader_5e.get_match_vip_plus_data(match_id))
    _run("5e.get_match_extra_data", lambda: downloader_5e.get_match_extra_data(match_id))


def run_steam_examples(live: bool) -> None:
    known_code = _env("STEAM_KNOWN_CODE") or "CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
    _run("steam.decode_share_code", lambda: downloader_steam.decode_share_code(known_code))
    _run(
        "steam.resolve_demo_url_from_share_code",
        lambda: downloader_steam.resolve_demo_url_from_share_code(
            known_code,
            demo_url_resolver=lambda _code, decoded: f"https://example.test/{decoded['matchid']}.dem",
        ),
    )
    if not live:
        _skip("Steam network API", "pass --live to call external endpoints")
        return

    if not _env("STEAM_KNOWN_CODE"):
        _skip("Steam network API", "set STEAM_KNOWN_CODE")
        return

    api_key = _env("STEAM_API_KEY")
    steamid = _env("STEAM_ID64")
    steamidkey = _env("STEAM_ID_KEY")
    if not api_key or not steamid or not steamidkey:
        _skip("Steam network API", "set STEAM_API_KEY, STEAM_ID64, and STEAM_ID_KEY")
        return
    _run(
        "steam.get_next_share_code",
        lambda: downloader_steam.get_next_share_code(api_key, steamid, steamidkey, known_code),
    )
    _run(
        "steam.get_all_demo_urls",
        lambda: downloader_steam.get_all_demo_urls(
            api_key,
            steamid,
            steamidkey,
            known_code,
            limit=3,
            demo_url_resolver=lambda _code, decoded: f"https://example.test/{decoded['matchid']}.dem",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="call network-backed APIs using environment variables")
    args = parser.parse_args()

    run_local_examples()
    run_pwa_examples(args.live)
    run_five_e_examples(args.live)
    run_steam_examples(args.live)


if __name__ == "__main__":
    main()
