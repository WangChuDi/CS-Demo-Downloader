# CS Demo Downloader

CS Demo Downloader downloads Counter-Strike demo files from supported Chinese CS platforms. It provides a scriptable CLI, a Python API, and a Docker entrypoint for scheduled/server usage.

[中文文档](README_CN.md)

## Table of Contents

- [Quick Start](#quick-start)
- [Supported Platforms](#supported-platforms)
- [Configuration](#configuration)
- [Install](#install)
- [CLI Usage](#cli-usage)
- [Docker Usage](#docker-usage)
- [Python API Usage](#python-api-usage)
- [Scheduled Downloads](#scheduled-downloads)
- [Tests](#tests)
- [Notes and Limitations](#notes-and-limitations)
- [License](#license)

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

## Quick Start

Use Docker if you want the simplest scheduled/server setup:

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# Edit config/config.jsonc before running the container.

docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

Use a local Python install if you want CLI/API development from a clone:

```bash
pip install "$(python scripts/select_private_signer_wheel.py wheelhouse)"
pip install -e .
cs-demo-downloader --help
```

PWA downloads require the private compiled `cs-demo-pwa-signer` wheel. Public tests mock that boundary.

## Project Layout

<details>
<summary>Repository layout</summary>

```text
.
├── pyproject.toml         # Python package metadata
├── cli.py                 # Compatibility CLI wrapper
├── src/cs_demo_downloader/ # Installable Python package
├── tests/                 # unittest test suite
├── Dockerfile
├── docker-compose.yml
├── config.jsonc.example
└── requirements.txt
```

</details>

## Requirements

- Python 3.11+ recommended.
- CLI/runtime dependencies are declared in `pyproject.toml`. `requirements.txt` is kept for compatibility.
- Docker, if you want containerized execution.

Use `python3` on Linux/macOS if `python` is not mapped to Python 3.

## Configuration

Copy the JSONC example config and fill in your account information:

```bash
cp config.jsonc.example config.jsonc
```

The loader accepts both the new nested JSONC schema and the previous `config.json` schema for backward compatibility. `label` replaces `name` as the clearer display-only field; old `name` values are still accepted when loading legacy configs.

<details>
<summary>Full JSONC schema example</summary>

Example schema:

```jsonc
{
  // "." downloads into the current working directory.
  "download_path": ".",
  "five_e": {
    "users": [
      {
        "label": "example_5e_user", // Display-only label.
        "userid": "YOUR_5E_USERID_HERE"
      }
    ]
  },
  "pwa": {
    "default_access_token": "SHARED_PWA_ACCESS_TOKEN",
    "signature_provider": "compiled",
    "pvp_alive_dll": "cache/PvpAlive.dll",
    "pvp_alive_bridge_exe": "",
    "pvp_alive_wine_executable": "wine",
    "pvp_alive_timeout": "10",
    "users": [
      {
        "label": "pwa_target_1",
        "steamid": "TARGET_STEAM_ID_1"
      },
      {
        "label": "pwa_target_2",
        "steamid": "TARGET_STEAM_ID_2"
      },
      {
        "label": "pwa_target_with_custom_token",
        "steamid": "TARGET_STEAM_ID_3",
        "access_token": "OPTIONAL_TARGET_SPECIFIC_PWA_ACCESS_TOKEN"
      }
    ]
  },
  "steam": {
    "users": [
      {
        "label": "example_steam_user",
        "steamid": "YOUR_STEAM_ID64_HERE",
        "api_key": "YOUR_STEAM_WEB_API_KEY_HERE",
        "steamidkey": "YOUR_STEAM_ID_KEY_HERE",
        "knowncode": "CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx"
      }
    ],
    "resolver": {
      "type": "boiler",
      "executable_path": "boiler-writter",
      "auto_download": "true",
      "cache_dir": "",
      "timeout": "60"
    },
    "gc": {
      "username_env": "STEAM_GC_USERNAME",
      "password_env": "STEAM_GC_PASSWORD",
      "two_factor_secret_env": "STEAM_GC_TWO_FACTOR_SECRET",
      "auth_code_env": "STEAM_GC_AUTH_CODE",
      "sentry_dir": "",
      "timeout": "30"
    }
  }
}
```

</details>

<details>
<summary>Platform credential notes</summary>

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
4. Fill `pwa.default_access_token` and each target `steamid` in `config.jsonc`.

PWA demo download links are now generated with the current signed query parameters and the downloader sends the required PWA request headers for the final file request. Tokens can expire. If PWA downloads stop working, refresh the token first.

PWA signing is provided by the private compiled `cs-demo-pwa-signer` wheel. The public downloader repository does not include the signing algorithm source. The `s` parameter calculation was obtained through reverse-engineering work by Sisyphus; to reduce ongoing maintenance burden, it has been packaged into the wheel and does not affect normal downloader usage. Install the private wheel before using PWA downloads; see `docs/private-pwa-signer-wheel.md` for the required wheel contract and verification checklist. If another project wants to implement demo downloading without relying on this pip package, contact `wangchudi666@gmail.com`.

If one PWA access token can access multiple target Steam accounts, set it once as `pwa.default_access_token` and add one `pwa.users` entry per target `steamid`. A user-specific `access_token` can override the default for a single target.

### Steam Official Matchmaking Credentials

Steam official matchmaking support uses Valve's `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API. You need:

1. `steamid`: your SteamID64.
2. `api_key`: a Steam Web API key from `https://steamcommunity.com/dev/apikey`.
3. `steamidkey`: the match sharing authentication key shown by CS2/CS:GO.
4. `knowncode`: one existing official matchmaking share code, used as the cursor for fetching newer matches.
The API returns the next share code after `knowncode`; the downloader can iterate share codes locally. Steam does **not** expose the final replay URL through this Web API alone. A real `.dem.bz2` URL must be read from Steam Game Coordinator full match info, typically the match `map` field. Until a GC resolver is configured, the Steam platform will report that no real replay URL can be resolved instead of returning a fake download URL.

### Steam Demo URL Resolvers

Steam official matchmaking has two optional resolver backends:

- `boiler`: local-machine backend using `akiver/boiler-writter`. Steam must be running and logged in on the same machine. This avoids storing Steam passwords and is recommended for local CLI usage. Configure `steam.resolver.type = "boiler"`. Set `steam.resolver.auto_download = "true"` to download the latest boiler-writter release into the local cache automatically, or set `steam.resolver.executable_path` to a manually installed binary.
- `steam-login`: headless backend using optional `steam`/`csgo` dependencies. It reads credentials only from environment variables such as `STEAM_GC_USERNAME` and `STEAM_GC_PASSWORD`; do not store Steam credentials in your config file. Live Steam login still requires a real account and cannot be verified by local unit tests.

Docker images do not bundle `boiler-writter` and cannot use the local Steam resolver unless you provide a working Steam client environment yourself.

When working from a local clone, install optional resolver dependencies as needed:

```bash
pip install -e .[steam-boiler]
pip install -e .[steam-login]
```

</details>

## Install

Install the latest release from PyPI:

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

You can also install the current main branch directly from GitHub:

```bash
pip install git+https://github.com/WangChuDi/CS-Demo-Downloader.git
```

For local development from this repository, use editable installs instead:

```bash
pip install "$(python scripts/select_private_signer_wheel.py wheelhouse)"
pip install -e .
```

On Windows PowerShell:

```powershell
$wheel = python scripts/select_private_signer_wheel.py wheelhouse
pip install $wheel
pip install -e .
```

The private signer wheel is required only for real PWA signing. Public tests mock that boundary.

The package installs this console command:

- `cs-demo-downloader` - CLI downloader.

## CLI Usage

Common commands:

| Task | Command |
| --- | --- |
| Show help | `cs-demo-downloader --help` |
| Download all configured platforms | `cs-demo-downloader download --all --config config.jsonc` |
| Download 5EPlay only | `cs-demo-downloader download --platform 5e --config config.jsonc` |
| Download PWA only | `cs-demo-downloader download --platform pwa --config config.jsonc` |
| Download Steam only | `cs-demo-downloader download --platform steam --config config.jsonc` |
| Refresh cached PWA DLL manually | `cs-demo-downloader update-pvpalive-dll --target cache/PvpAlive.dll` |

<details>
<summary>CLI command examples and notes</summary>

Show help:

```bash
cs-demo-downloader --help
cs-demo-downloader download --help
```

Download all configured platforms:

```bash
cs-demo-downloader download --all --config config.jsonc
```

Download only 5EPlay demos:

```bash
cs-demo-downloader download --platform 5e --config config.jsonc
```

Download only Perfect World Arena demos:

```bash
cs-demo-downloader download --platform pwa --config config.jsonc
```

Download only Steam official matchmaking demos:

```bash
cs-demo-downloader download --platform steam --config config.jsonc
```

Update the cached PWA `PvpAlive.dll` explicitly without downloading the full official client ZIP:

```bash
cs-demo-downloader update-pvpalive-dll --target cache/PvpAlive.dll
```

This command reads the official `latest.yml`, derives the matching ZIP URL, uses HTTP Range requests to fetch only the ZIP tail, central directory, local header, and compressed `plugin/PvpAlive.dll` data, validates size and CRC32, then atomically replaces the target cache file. It writes version metadata next to the DLL as `PvpAlive.dll.json`; if the cached metadata already matches the latest client, the DLL data is not downloaded again. Pass `--force` to refresh anyway. It does not modify the installed Perfect World Arena client and is not used by the normal Python signing path unless you explicitly call it.

Override the configured download directory:

```bash
cs-demo-downloader download --all --config config.jsonc --output ./demos
```

When `--config` is provided explicitly, the CLI exits with a non-zero status if that file is missing or invalid. This is intentional so Docker, cron, and other automation can detect configuration problems.

</details>

## Python API Usage

You can also use the installed package from your own Python scripts. The public modules are small function wrappers around each platform downloader plus the shared download/extract helpers.

<details>
<summary>Python examples</summary>

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

To reuse the same JSONC config file as the CLI:

```python
from cs_demo_downloader.core.config import load_config

config = load_config("config.jsonc")
for user in config.get_users_pwa():
    print(user.label, user.steamid)
```

### PWA DLL cache updater

The updater is available as a Python function if you need to refresh a cached `PvpAlive.dll` for a separate integration:

```python
from cs_demo_downloader.pwa_dll_updater import update_cached_pvp_alive_dll

dll_path = update_cached_pvp_alive_dll(target_path="cache/PvpAlive.dll", force=False)
print(dll_path)
```

The current downloader uses the private compiled signer wheel by default on every platform. If you explicitly need the DLL fallback, set `pwa.signature_provider` to one of these values:

- `compiled`: default private compiled wheel signer; no DLL or Wine involved.
- `pvp_alive_native`: call the packaged 32-bit bridge directly on Windows.
- `pvp_alive_wine`: call the packaged 32-bit bridge through Wine on Linux.

The DLL is never committed or bundled. Refresh it explicitly when needed:

```bash
cs-demo-downloader update-pvpalive-dll --target cache/PvpAlive.dll
```

Python users can also call the bridge helper directly:

```python
from cs_demo_downloader.pwa_bridge import call_pvp_alive_swap_data

signature = call_pvp_alive_swap_data(
    dll_path="cache/PvpAlive.dll",
    inner_json='{"your":"payload"}',
)
```

Linux Wine usage is explicit:

```python
from cs_demo_downloader.pwa_bridge import call_pvp_alive_swap_data_wine

signature = call_pvp_alive_swap_data_wine(
    dll_path="cache/PvpAlive.dll",
    inner_json='{"your":"payload"}',
)
```

macOS users should use a macOS-compatible private signer wheel; this project does not include a macOS Wine/QEMU fallback.

</details>

## Docker Usage

Published GitHub Container Registry images:

| Image | Platforms | Notes |
| --- | --- | --- |
| `ghcr.io/wangchudi/cs-demo-downloader:latest` | `linux/amd64`, `linux/arm64` | Default image. Uses the private compiled signer wheel and does not include Wine. |
| `ghcr.io/wangchudi/cs-demo-downloader:latest-wine` | `linux/amd64` | Wine-enabled image for explicit `pvp_alive_wine` DLL bridge use. |

Pull the default image:

```bash
docker pull ghcr.io/wangchudi/cs-demo-downloader:latest
```

Images are published automatically when a `v*` Git tag is pushed or a GitHub Release is published. Release images are tagged as `latest`, the full semantic version such as `0.1.0`, and shorter version aliases such as `0.1` and `0` when applicable.

Wine-enabled images are published separately with a `-wine` suffix, for example:

```bash
docker pull ghcr.io/wangchudi/cs-demo-downloader:latest-wine
```

The Wine image is currently built for `linux/amd64` only because the packaged PWA bridge is a 32-bit Windows executable.

Run once with mounted config and output directories:

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# Edit config/config.jsonc before running the container.

docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

Because Docker uses an explicit config path, `/config/config.jsonc` must exist and be valid.

<details>
<summary>Local Docker builds, Wine image, and Compose</summary>

You can also build the image locally from this repository:

```bash
cp /path/to/cs_demo_pwa_signer-0.1.0-*.whl wheelhouse/
docker build --build-arg PYTHON_VERSION=3.12 -t cs-demo-downloader .
docker build --build-arg PYTHON_VERSION=3.12 -f Dockerfile.wine -t cs-demo-downloader:wine .
```

Prepare mounted directories and config:

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# Edit config/config.jsonc before running the container.
```

Run once:

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

The Docker entrypoint runs:

```bash
cs-demo-downloader download --all --config /config/config.jsonc --output /demos
```

The default Linux container uses the private compiled signer wheel and does not include Wine. If you want to refresh a cached DLL, mount a cache directory and run the updater explicitly:

```bash
docker run --rm \
  -v "$(pwd)/cache:/cache" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  update-pvpalive-dll --target /cache/PvpAlive.dll
```

To use the Linux Wine bridge image, switch to the `-wine` tag and set the config to `"signature_provider": "pvp_alive_wine"` with `"pvp_alive_dll": "/cache/PvpAlive.dll"`:

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  -v "$(pwd)/cache:/cache" \
  ghcr.io/wangchudi/cs-demo-downloader:latest-wine
```

### Docker Compose

```bash
docker compose run --rm cs-demo-downloader
```

`docker-compose.yml` uses `ghcr.io/wangchudi/cs-demo-downloader:latest` by default and mounts `./config`, `./demos`, and `./cache`. To run the Wine variant:

```bash
docker compose --profile wine run --rm cs-demo-downloader-wine
```

</details>

## Scheduled Downloads

Example crontab entry for a daily 03:00 run:

```cron
0 3 * * * docker run --rm -v /home/user/config:/config -v /home/user/demos:/demos ghcr.io/wangchudi/cs-demo-downloader:latest
```

Make sure `/home/user/config/config.jsonc` exists before scheduling the job.

## Tests

Run the local unittest suite:

```bash
python3 -m unittest discover
```

Run a syntax/bytecode check:

```bash
python3 -m compileall src tests cli.py
```

The tests are local and deterministic. They do not require real 5EPlay/PWA/Steam credentials or network access. The install tests create temporary virtual environments, install the package with `pip install`, and verify that the installed package contains the bundled signer manifest, loads the matching vendored signer binary from `site-packages`, and relies on pip build isolation to provide the `wheel` build dependency instead of requiring a manual wheel install.

## Notes and Limitations

- The project currently supports 5EPlay and Perfect World Arena downloads. Steam official matchmaking share-code iteration is implemented, but real Steam replay URL resolution requires a Steam GC full-match-info resolver.
- PWA access tokens may expire and must be refreshed manually.
- Demo availability depends on the upstream platform APIs.
- Downloaded files and local configs are intentionally ignored by git.
- Cached `PvpAlive.dll` files under `cache/` or `vendor/PvpAlive/` are intentionally ignored by git and must not be committed.
- PWA signing requires the private `cs-demo-pwa-signer` wheel. The public source tree must not contain the signer algorithm source or an sdist for that package. If another project wants to implement demo downloading without relying on this pip package, contact `wangchudi666@gmail.com`.
- A 32-bit Windows C++ bridge executable is packaged for explicit DLL fallback use. Linux uses the private compiled signer by default; Wine is available only through the explicit `pvp_alive_wine` provider or `*-wine` Docker image. QEMU fallback is intentionally not included.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

If you believe any content in this project infringes your rights, please contact the maintainer by opening a GitHub issue or emailing `wangchudi666@gmail.com`.
