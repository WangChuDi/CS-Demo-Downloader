# CS Demo Downloader

CS Demo Downloader downloads Counter-Strike demo files from supported Chinese CS platforms. It provides a scriptable CLI, a Python API, and a Docker entrypoint for scheduled/server usage.

[中文文档](README_CN.md)

## Supported Platforms

The current implementation supports three platforms:

| Platform | CLI value | Required account fields | Notes |
| --- | --- | --- | --- |
| 5EPlay | `5e` | `userid` | The user id is read from a 5E player profile URL. |
| Perfect World Arena | `pwa` | `steamid`, `access_token` | Requires a valid Perfect World Arena web/client token. Demo URLs are signed before download. |
| Steam official matchmaking | `steam` | `steamid`, `api_key`, `steamidkey`, `knowncode` | Implements Steam Web API share-code iteration. Real replay URL resolution still requires Steam Game Coordinator full match info. |

No other platforms are implemented at the moment.

## Features

- Download demos from 5EPlay, Perfect World Arena, and Steam official matchmaking.
- Use CLI automation or import the Python API directly.
- Docker image for server and scheduled downloads.
- Automatically extracts downloaded ZIP and BZ2 demo archives.
- Rejects unsafe ZIP entries that try to extract outside the target directory.
- Fails fast for explicit missing or malformed CLI config files.

## Project Layout

```text
.
├── pyproject.toml         # Python package metadata
├── cli.py                 # Compatibility CLI wrapper
├── src/cs_demo_downloader/ # Installable Python package
├── tests/                 # unittest test suite
├── Dockerfile
├── docker-compose.yml
├── config.json.example
└── requirements.txt
```

## Requirements

- Python 3.11+ recommended.
- CLI/runtime dependencies are declared in `pyproject.toml`. `requirements.txt` is kept for compatibility.
- Docker, if you want containerized execution.

Use `python3` on Linux/macOS if `python` is not mapped to Python 3.

## Configuration

Copy the example config and fill in your account information:

```bash
cp config.json.example config.json
```

Example schema:

```json
{
  "download_path": "/demos",
  "users_5e": [
    {
      "name": "example_user",
      "userid": "YOUR_5E_USERID_HERE"
    }
  ],
  "users_pwa": [
    {
      "name": "example_user",
      "steamid": "YOUR_STEAM_ID_HERE",
      "access_token": "YOUR_ACCESS_TOKEN_HERE"
    }
  ],
  "users_steam": [
    {
      "name": "example_user",
      "steamid": "YOUR_STEAM_ID64_HERE",
      "api_key": "YOUR_STEAM_WEB_API_KEY_HERE",
      "steamidkey": "YOUR_STEAM_ID_KEY_HERE",
      "knowncode": "CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
    }
  ]
}
```

### 5EPlay User ID

Open a 5E player profile URL and use the profile id segment. For example:

```text
https://www.5eplay.com/player/11814738gjdwn7
```

The `userid` value is `11814738gjdwn7`.

### Perfect World Arena Steam ID and Access Token

1. Log in to the Perfect World Arena web page or client.
2. Open browser developer tools.
3. Inspect authenticated network requests or cookies.
4. Fill `steamid` and `access_token` in `config.json`.

PWA demo download links are now generated with the current signed query parameters and the downloader sends the required PWA request headers for the final file request. Tokens can expire. If PWA downloads stop working, refresh the token first.

### Steam Official Matchmaking Credentials

Steam official matchmaking support uses Valve's `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API. You need:

1. `steamid`: your SteamID64.
2. `api_key`: a Steam Web API key from `https://steamcommunity.com/dev/apikey`.
3. `steamidkey`: the match sharing authentication key shown by CS2/CS:GO.
4. `knowncode`: one existing official matchmaking share code, used as the cursor for fetching newer matches.
The API returns the next share code after `knowncode`; the downloader can iterate share codes locally. Steam does **not** expose the final replay URL through this Web API alone. A real `.dem.bz2` URL must be read from Steam Game Coordinator full match info, typically the match `map` field. Until a GC resolver is configured, the Steam platform will report that no real replay URL can be resolved instead of returning a fake download URL.

### Steam Demo URL Resolvers

Steam official matchmaking has two optional resolver backends:

- `boiler`: local-machine backend using `akiver/boiler-writter`. Steam must be running and logged in on the same machine. This avoids storing Steam passwords and is recommended for local CLI usage. Configure `steam_resolver.type = "boiler"`. Set `steam_resolver.auto_download = "true"` to download the latest boiler-writter release into the local cache automatically, or set `steam_resolver.executable_path` to a manually installed binary.
- `steam-login`: headless backend using optional `steam`/`csgo` dependencies. It reads credentials only from environment variables such as `STEAM_GC_USERNAME` and `STEAM_GC_PASSWORD`; do not store Steam credentials in `config.json`. Live Steam login still requires a real account and cannot be verified by local unit tests.

Docker images do not bundle `boiler-writter` and cannot use the local Steam resolver unless you provide a working Steam client environment yourself.

Install optional resolver dependencies as needed:

```bash
pip install -e .[steam-boiler]
pip install -e .[steam-login]
```

## Install from pip

Install the default CLI/runtime package:

```bash
pip install cs-demo-downloader
```

Optional extras:

```bash
# Steam official matchmaking resolver using local Steam + boiler-writter parser deps
pip install "cs-demo-downloader[steam-boiler]"

# Steam official matchmaking resolver using steam-login/csgo GC deps
pip install "cs-demo-downloader[steam-login]"
```

For local development from this repository, use editable installs instead:

```bash
pip install -e .
```

The package installs this console command:

- `cs-demo-downloader` - CLI downloader.

## CLI Usage

Show help:

```bash
cs-demo-downloader --help
cs-demo-downloader download --help
```

Download all configured platforms:

```bash
cs-demo-downloader download --all --config config.json
```

Download only 5EPlay demos:

```bash
cs-demo-downloader download --platform 5e --config config.json
```

Download only Perfect World Arena demos:

```bash
cs-demo-downloader download --platform pwa --config config.json
```

Download only Steam official matchmaking demos:

```bash
cs-demo-downloader download --platform steam --config config.json
```

Override the configured download directory:

```bash
cs-demo-downloader download --all --config config.json --output ./demos
```

When `--config` is provided explicitly, the CLI exits with a non-zero status if that file is missing or invalid. This is intentional so Docker, cron, and other automation can detect configuration problems.

## Python API Usage

You can also use the installed package from your own Python scripts. The public modules are small function wrappers around each platform downloader plus the shared download/extract helpers.

### 5EPlay

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_urls
from cs_demo_downloader.core.utils import download_and_extract

demo_urls = get_all_demo_urls("YOUR_5E_USERID")

for match_id, demo_url in demo_urls.items():
    print("downloading", match_id)
    download_and_extract(demo_url, "./demos")
```

### Perfect World Arena / PWA

PWA downloads need both the signed URL and the PWA download headers. Do not print or persist generated URLs because they contain `access_token`.

```python
from cs_demo_downloader.core.downloader_pwa import (
    build_download_headers,
    get_all_demo_urls,
)
from cs_demo_downloader.core.utils import download_and_extract

steamid = "YOUR_STEAM_ID64"
access_token = "YOUR_PWA_ACCESS_TOKEN"

headers = build_download_headers(steamid)
demo_urls = get_all_demo_urls(steamid, access_token, size=20)

for match_id, demo_url in demo_urls.items():
    print("downloading", match_id)
    download_and_extract(demo_url, "./demos", headers=headers)
```

If you only need the signed URL for integration with another downloader:

```python
from cs_demo_downloader.core.downloader_pwa import get_demo_url

demo_url = get_demo_url("MATCH_ID", "YOUR_PWA_ACCESS_TOKEN")
```

### Steam Official Matchmaking

Steam Web API share-code iteration is available through `downloader_steam`. A real replay URL still requires a Steam GC resolver such as the built-in boiler-writter resolver.

```python
from cs_demo_downloader.core.downloader_steam import get_all_demo_urls
from cs_demo_downloader.steam.boiler_resolver import BoilerWritterResolver

resolver = BoilerWritterResolver(auto_download=True)

demo_urls = get_all_demo_urls(
    api_key="YOUR_STEAM_WEB_API_KEY",
    steamid="YOUR_STEAM_ID64",
    steamidkey="YOUR_MATCH_SHARING_AUTH_KEY",
    knowncode="CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx",
    demo_url_resolver=resolver.resolve_demo_url,
)
```

### Config helpers

To reuse the same JSON config file as the CLI:

```python
from cs_demo_downloader.core.config import load_config

config = load_config("config.json")
for user in config.get_users_pwa():
    print(user.name, user.steamid)
```

## Docker Usage

Build the image:

```bash
docker build -t cs-demo-downloader .
```

Prepare mounted directories and config:

```bash
mkdir -p config demos
cp config.json.example config/config.json
# Edit config/config.json before running the container.
```

Run once:

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  cs-demo-downloader
```

The Docker entrypoint runs:

```bash
cs-demo-downloader download --all --config /config/config.json --output /demos
```

Because Docker uses an explicit config path, `/config/config.json` must exist and be valid.

### Docker Compose

```bash
docker compose run --rm cs-demo-downloader
```

## Scheduled Downloads

Example crontab entry for a daily 03:00 run:

```cron
0 3 * * * docker run --rm -v /home/user/config:/config -v /home/user/demos:/demos cs-demo-downloader
```

Make sure `/home/user/config/config.json` exists before scheduling the job.

## Tests

Run the local unittest suite:

```bash
python3 -m unittest discover
```

Run a syntax/bytecode check:

```bash
python3 -m compileall src tests cli.py
```

The tests are local and deterministic. They do not require real 5EPlay/PWA/Steam credentials or network access.

## Notes and Limitations

- The project currently supports 5EPlay and Perfect World Arena downloads. Steam official matchmaking share-code iteration is implemented, but real Steam replay URL resolution requires a Steam GC full-match-info resolver.
- PWA access tokens may expire and must be refreshed manually.
- Demo availability depends on the upstream platform APIs.
- Downloaded files and local configs are intentionally ignored by git.

## License

MIT
