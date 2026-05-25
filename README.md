# CS Demo Downloader

CS Demo Downloader downloads Counter-Strike demo files from supported Chinese CS platforms. It provides a PyQt5 desktop GUI, a scriptable CLI, and a Docker entrypoint for scheduled/server usage.

[中文文档](README_CN.md)

## Supported Platforms

The current implementation supports three platforms:

| Platform | CLI value | Required account fields | Notes |
| --- | --- | --- | --- |
| 5EPlay | `5e` | `userid` | The user id is read from a 5E player profile URL. |
| Perfect World Arena | `pwa` | `steamid`, `access_token` | Requires a valid Perfect World Arena web/client token. |
| Steam official matchmaking | `steam` | `steamid`, `api_key`, `steamidkey`, `knowncode` | Implements Steam Web API share-code iteration. Real replay URL resolution still requires Steam Game Coordinator full match info. |

No other platforms are implemented at the moment.

## Features

- Download demos from 5EPlay, Perfect World Arena, and Steam official matchmaking.
- Use either the desktop GUI or CLI automation.
- Docker image for server and scheduled downloads.
- Automatically extracts downloaded ZIP demo archives.
- Rejects unsafe ZIP entries that try to extract outside the target directory.
- Fails fast for explicit missing or malformed CLI config files.

## Project Layout

```text
.
├── pyproject.toml         # Python package metadata
├── cli.py                 # Compatibility CLI wrapper
├── main.py                # Compatibility GUI wrapper
├── src/cs_demo_downloader/ # Installable Python package
├── tests/                 # unittest test suite
├── Dockerfile
├── docker-compose.yml
├── config.json.example
├── requirements.txt
└── requirements-gui.txt
```

## Requirements

- Python 3.11+ recommended.
- CLI/runtime dependencies are declared in `pyproject.toml`. `requirements.txt` is kept for compatibility.
- GUI dependencies are available through the `gui` optional extra.
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
3. Inspect authenticated network requests.
4. Fill `steamid` and `access_token` in `config.json`.

Tokens can expire. If PWA downloads stop working, refresh the token first.

### Steam Official Matchmaking Credentials

Steam official matchmaking support uses Valve's `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API. You need:

1. `steamid`: your SteamID64.
2. `api_key`: a Steam Web API key from `https://steamcommunity.com/dev/apikey`.
3. `steamidkey`: the match sharing authentication key shown by CS2/CS:GO.
4. `knowncode`: one existing official matchmaking share code, used as the cursor for fetching newer matches.
The API returns the next share code after `knowncode`; the downloader can iterate share codes locally. Steam does **not** expose the final replay URL through this Web API alone. A real `.dem.bz2` URL must be read from Steam Game Coordinator full match info, typically the match `map` field. Until a GC resolver is configured, the Steam platform will report that no real replay URL can be resolved instead of returning a fake download URL.

### Steam Demo URL Resolvers

Steam official matchmaking has two optional resolver backends:

- `boiler`: desktop/local backend using `akiver/boiler-writter`. Steam must be running and logged in on the same machine. This avoids storing Steam passwords and is recommended for GUI/local CLI usage. Configure `steam_resolver.type = "boiler"`. Set `steam_resolver.auto_download = "true"` to download the latest boiler-writter release into the local cache automatically, or set `steam_resolver.executable_path` to a manually installed binary.
- `steam-login`: headless backend using optional `steam`/`csgo` dependencies. It reads credentials only from environment variables such as `STEAM_GC_USERNAME` and `STEAM_GC_PASSWORD`; do not store Steam credentials in `config.json`. Live Steam login still requires a real account and cannot be verified by local unit tests.

Docker images do not bundle `boiler-writter` and cannot use the desktop Steam resolver unless you provide a working Steam client environment yourself.

Install optional resolver dependencies as needed:

```bash
pip install -e .[steam-boiler]
pip install -e .[steam-login]
```

## CLI Usage

Install the CLI dependencies:

```bash
pip install -e .
```

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

## GUI Usage

Install GUI dependencies and start the desktop app:

```bash
pip install -e .[gui]
cs-demo-downloader-gui
```

The GUI lets you:

- choose a download directory;
- add/remove 5EPlay, PWA, and Steam official matchmaking users;
- refresh demo lists;
- download selected demos.

The GUI uses the default config lookup path. If no config exists, it starts with an empty configuration so you can create one from the app.

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

## Build Desktop Binaries

Install GUI dependencies plus PyInstaller:

```bash
pip install -e .[gui]
pip install pyinstaller
```

Build a single-file desktop executable:

```bash
pyinstaller --onefile --windowed --name="CS_Demo_Downloader" main.py
```

The artifact is written to `dist/`.

## Tests

Run the local unittest suite:

```bash
python3 -m unittest discover
```

Run a syntax/bytecode check:

```bash
python3 -m compileall .
```

The tests are local and deterministic. They do not require real 5EPlay/PWA/Steam credentials or network access.

## Notes and Limitations

- The project currently supports 5EPlay and Perfect World Arena downloads. Steam official matchmaking share-code iteration is implemented, but real Steam replay URL resolution requires a Steam GC full-match-info resolver.
- PWA access tokens may expire and must be refreshed manually.
- Demo availability depends on the upstream platform APIs.
- Downloaded files and local configs are intentionally ignored by git.

## License

MIT
