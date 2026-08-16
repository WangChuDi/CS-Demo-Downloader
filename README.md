# CS Demo Downloader

Download Counter-Strike demos from 5EPlay, Perfect World Arena, and Steam official matchmaking.

[中文文档](README_CN.md) · [Detailed usage wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide)

## Table of contents

- [Quick start with pip](#quick-start-with-pip)
  - [Python API quick start](#python-api-quick-start)
- [Quick start with Docker](#quick-start-with-docker)
- [Configuration](#configuration)
- [Examples](#examples)
- [Platform credentials](#platform-credentials)
  - [5EPlay](#5eplay)
  - [Perfect World Arena / PWA](#perfect-world-arena--pwa)
  - [Steam official matchmaking](#steam-official-matchmaking)
- [Metadata](#metadata)
- [More documentation](#more-documentation)
- [License](#license)

## Quick start with pip

Full pip install and CLI details: [wiki install guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#2-install) and [wiki CLI guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#5-cli-usage).

```bash
pip install cs-demo-downloader
cp config.jsonc.example config.jsonc
# Edit config.jsonc first.

cs-demo-downloader download --all --config config.jsonc
```

Useful commands:

```bash
cs-demo-downloader --help
cs-demo-downloader download --platform 5e --config config.jsonc
cs-demo-downloader download --platform pwa --config config.jsonc
cs-demo-downloader download --platform steam --config config.jsonc
cs-demo-downloader download --all --config config.jsonc --output ./demos
```

### Python API quick start

Full Python examples: [wiki Python API guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#8-python-api).

5EPlay demo URLs:

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_urls

demo_urls = get_all_demo_urls("YOUR_5E_USERID")
```

PWA demo URLs need both the signed URL and PWA download headers. Generated URLs contain `access_token` and are returned as-is.

```python
from cs_demo_downloader.core.downloader_pwa import build_download_headers, get_all_demo_urls

steamid = "YOUR_STEAM_ID64"
access_token = "YOUR_PWA_ACCESS_TOKEN"

headers = build_download_headers(steamid)
demo_urls = get_all_demo_urls(steamid, access_token, size=20)
```

Normalized metadata:

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_metadata as get_5e_metadata
from cs_demo_downloader.core.metadata import metadata_list_to_dicts

matches = get_5e_metadata("YOUR_5E_USERID", limit=10)
payload = metadata_list_to_dicts(matches, include_raw=False)
```

## Quick start with Docker

Full Docker details, scheduler behavior, and image variants: [wiki Docker guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#7-docker).

```bash
mkdir -p config demos cache
docker compose up -d cs-demo-downloader
```

The Compose example mounts `./config` to `/config`, creates `/config/config.jsonc` on first start, and uses the app's built-in `schedule` command. The generated Docker config enables automatic downloads every day at `08:00` in the container's local timezone; this is not cron. Edit `config/config.jsonc` to add accounts or change `scheduler.daily_time`.

The default image is `ghcr.io/wangchudi/cs-demo-downloader:latest`. A Wine-enabled fallback image is also published as `ghcr.io/wangchudi/cs-demo-downloader:latest-wine` for explicit DLL bridge usage.

Manual one-shot download with Docker:

```bash
docker run --rm \
  -e CS_DEMO_CREATE_DEFAULT_CONFIG=true \
  -e CS_DEMO_SCHEDULE_CONFIG=/config/config.jsonc \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  -v "$(pwd)/cache:/cache" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  download --all --config /config/config.jsonc --output /demos
```

For container logs, progress defaults to coarse 10% updates outside a TTY. Set `CS_DEMO_PROGRESS=bar` to force an interactive progress bar or `CS_DEMO_PROGRESS=none` to hide progress lines.

## Configuration

Full JSONC schema and compatibility notes: [wiki configuration guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#3-configuration).

Minimal config shape:

```jsonc
{
  "download_path": "./demos",
  "save_metadata_with_demo": false,
  "five_e": {
    "users": [
      {"label": "my_5e", "userid": "YOUR_5E_USERID"}
    ]
  },
  "pwa": {
    "default_access_token": "YOUR_PWA_ACCESS_TOKEN",
    "users": [
      {"label": "my_pwa", "steamid": "YOUR_STEAM_ID64"}
    ]
  },
  "steam": {
    "users": [
      {
        "label": "my_steam",
        "steamid": "YOUR_STEAM_ID64",
        "api_key": "YOUR_STEAM_WEB_API_KEY",
        "steamidkey": "YOUR_MATCH_SHARING_AUTH_KEY",
        "knowncode": "CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
      }
    ]
  }
}
```

## Examples

Runnable Python examples for PWA, 5EPlay, and Steam are available in the [`examples/`](examples/README.md) directory.

## Platform credentials

Full platform credential notes: [wiki credentials guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#4-credentials).

### 5EPlay

Open a 5E player profile URL and use the profile id segment as `userid`. For example:

```text
https://www.5eplay.com/player/11814738gjdwn7
```

The `userid` value is `11814738gjdwn7`.

### Perfect World Arena / PWA

This follows the same convention as the legacy [`WangChuDi/pwa_demo_downloader`](https://github.com/WangChuDi/pwa_demo_downloader) project:

1. `steamid` is the target user's SteamID64, for example `76561198159976336`.
2. Open `https://partner.wmpvp.com/#/login` and use one of these two login methods:

   1. **Phone-number login**: after logging in, read `access_token` from the browser cookies.
   2. **Steam login**: after completing the login, copy the `token` value from the browser address bar. The URL should look like:

      ```text
      https://partner.wmpvp.com/#/login?state=appAdmin&token=YOUR_ACCESS_TOKEN
      ```

      The token is in the URL fragment and may not be present in the browser cookies.
3. Fill `pwa.default_access_token` with the token and each target `steamid` in `config.jsonc`.

Do not commit tokens or paste them into logs/issues. Tokens can expire; refresh the token first if PWA downloads stop working.

To query a historical PWA season, pass its season code through the library's `season` parameter or set `PWA_SEASON` when using [`examples/pwa_recent_matches.py`](examples/pwa_recent_matches.py). The library reads the available season codes from PWA first, so adding a new season does not require updating a hard-coded season list. The bundled date table is retained only as a compatibility fallback for older responses.

### Steam official matchmaking

Steam official matchmaking uses Valve's `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API. You need:

1. `steamid`: your SteamID64.
2. `api_key`: a Steam Web API key from `https://steamcommunity.com/dev/apikey`.
3. `steamidkey`: the match sharing authentication key shown by CS2/CS:GO.
4. `knowncode`: one existing official matchmaking share code, used as the cursor for fetching newer matches.

Steam Web API can iterate share codes, but the real replay URL requires Steam Game Coordinator full match info. Use the wiki for resolver details.

## Metadata

Full metadata command and schema details: [wiki metadata guide](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide#6-metadata).

Export metadata without downloading demos:

```bash
cs-demo-downloader metadata --all --config config.jsonc --pretty
```

Or set this in `config.jsonc` to write `*.metadata.json` next to each successfully downloaded 5E/PWA demo:

```jsonc
"save_metadata_with_demo": true
```

## More documentation

Detailed Steam resolvers, Docker Compose, PWA DLL updater, tests, and limitations live in the [project wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/Usage-Guide).

## License

MIT. See [LICENSE](LICENSE).
