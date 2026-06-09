# CS Demo Downloader

Download Counter-Strike demos from 5EPlay, Perfect World Arena, and Steam official matchmaking.

[中文文档](README_CN.md) · [Detailed usage wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki)

## Quick start with pip

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

## Quick start with Docker

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# Edit config/config.jsonc first.

docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  download --all --config /config/config.jsonc --output /demos
```

The default image is `ghcr.io/wangchudi/cs-demo-downloader:latest`. A Wine-enabled fallback image is also published as `ghcr.io/wangchudi/cs-demo-downloader:latest-wine` for explicit DLL bridge usage.

To run the built-in scheduler instead of a one-shot download:

```bash
docker run --rm \
  -e CS_DEMO_SCHEDULE_ENABLED=true \
  -e CS_DEMO_SCHEDULE_CONFIG=/config/config.jsonc \
  -e CS_DEMO_SCHEDULE_OUTPUT=/demos \
  -e CS_DEMO_SCHEDULE_INTERVAL_SECONDS=86400 \
  -e CS_DEMO_SCHEDULE_PLATFORMS=all \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

## Configuration

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

## Platform credentials

### 5EPlay

Open a 5E player profile URL and use the profile id segment as `userid`. For example:

```text
https://www.5eplay.com/player/11814738gjdwn7
```

The `userid` value is `11814738gjdwn7`.

### Perfect World Arena / PWA

This follows the same convention as the legacy [`WangChuDi/pwa_demo_downloader`](https://github.com/WangChuDi/pwa_demo_downloader) project:

1. `steamid` is the target user's SteamID64, for example `76561198159976336`.
2. Log in at `https://partner.wmpvp.com/#/login`.
3. Read `access_token` from the logged-in browser cookie.
4. Fill `pwa.default_access_token` and each target `steamid` in `config.jsonc`.

Do not commit tokens or paste them into logs/issues. Tokens can expire; refresh the token first if PWA downloads stop working.

### Steam official matchmaking

Steam official matchmaking uses Valve's `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API. You need:

1. `steamid`: your SteamID64.
2. `api_key`: a Steam Web API key from `https://steamcommunity.com/dev/apikey`.
3. `steamidkey`: the match sharing authentication key shown by CS2/CS:GO.
4. `knowncode`: one existing official matchmaking share code, used as the cursor for fetching newer matches.

Steam Web API can iterate share codes, but the real replay URL requires Steam Game Coordinator full match info. Use the wiki for resolver details.

## Metadata

Export metadata without downloading demos:

```bash
cs-demo-downloader metadata --all --config config.jsonc --pretty
```

Or set this in `config.jsonc` to write `*.metadata.json` next to each successfully downloaded 5E/PWA demo:

```jsonc
"save_metadata_with_demo": true
```

## More documentation

Detailed configuration, Steam resolvers, Docker Compose, Python API examples, metadata schema, and development notes live in the [project wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki).

## License

MIT. See [LICENSE](LICENSE).
