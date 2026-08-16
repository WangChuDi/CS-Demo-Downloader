# Examples

These examples use environment variables for credentials so that tokens and API keys do not need to be committed to the repository.

## Public API smoke test

Run the deterministic local checks first:

```bash
python examples/public_api_smoke.py
```

This exercises the public API with explicit values for optional parameters. To also call network-backed functions, set the credentials for the platforms you want to test and add `--live`:

```bash
python examples/public_api_smoke.py --live
```

The script reports function names and status only. It does not print returned URLs, tokens, API keys, player data, or other response payloads.

Install the package first:

```bash
pip install cs-demo-downloader
```

## PWA recent matches

Set `PWA_STEAMID` and `PWA_ACCESS_TOKEN`, then run:

```bash
python examples/pwa_recent_matches.py
```

The script prints match IDs and Demo availability without printing signed URLs. By
default it queries the recent matches endpoint. Set `PWA_SEASON` (for example
`S23`) to query a specific historical season; the season list is read from PWA
first, so newly added season codes do not require a library update. Set
`PWA_MAX_SEASONS` when automatic history fallback should inspect more seasons.

## PWA Demo URLs

```bash
python examples/pwa_demo_urls.py
```

This prints signed URLs containing the access token. Treat the output as sensitive and do not commit or share it.

## 5E Demo URLs

Set `FIVE_E_USERID`, then run:

```bash
python examples/five_e_demo_urls.py
```

## Steam official matchmaking

Set `STEAM_API_KEY`, `STEAM_ID64`, `STEAM_ID_KEY`, and `STEAM_KNOWN_CODE`, then run:

```bash
python examples/steam_share_codes.py
```

The Steam Web API returns share codes. Resolving a share code to a real Demo URL requires a Steam Game Coordinator resolver.
