# CS Demo Downloader 中文文档

用于下载 Counter-Strike Demo 文件，支持 5E、完美世界电竞 / PWA 和 Steam 官匹。

[English README](README.md) · [详细使用 Wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki)

## pip 快速开始

```bash
pip install cs-demo-downloader
cp config.jsonc.example config.jsonc
# 先编辑 config.jsonc。

cs-demo-downloader download --all --config config.jsonc
```

常用命令：

```bash
cs-demo-downloader --help
cs-demo-downloader download --platform 5e --config config.jsonc
cs-demo-downloader download --platform pwa --config config.jsonc
cs-demo-downloader download --platform steam --config config.jsonc
cs-demo-downloader download --all --config config.jsonc --output ./demos
```

## Docker 快速开始

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# 先编辑 config/config.jsonc。

docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  download --all --config /config/config.jsonc --output /demos
```

默认镜像是 `ghcr.io/wangchudi/cs-demo-downloader:latest`。如果明确需要 DLL bridge fallback，也发布了带 Wine 的镜像：`ghcr.io/wangchudi/cs-demo-downloader:latest-wine`。

如果要运行内置定时器而不是一次性下载：

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

## 配置

最小配置结构：

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

## 平台凭据

### 5E

打开 5E 玩家主页 URL，取 URL 中的用户 ID 作为 `userid`。例如：

```text
https://www.5eplay.com/player/11814738gjdwn7
```

对应的 `userid` 是 `11814738gjdwn7`。

### 完美世界电竞 / PWA

这里参考旧项目 [`WangChuDi/pwa_demo_downloader`](https://github.com/WangChuDi/pwa_demo_downloader) 的使用方式：

1. `steamid` 填目标用户的 SteamID64，例如 `76561198159976336`。
2. 登录 `https://partner.wmpvp.com/#/login`。
3. 从登录后的浏览器 Cookie 中读取 `access_token`。
4. 将 `pwa.default_access_token` 和每个目标 `steamid` 填入 `config.jsonc`。

不要把 token 提交到仓库，也不要贴到日志或 issue 中。Token 可能过期；如果 PWA 下载不可用，优先刷新 token。

### Steam 官匹

Steam 官匹使用 Valve 的 `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API，需要：

1. `steamid`：你的 SteamID64。
2. `api_key`：Steam Web API Key，可在 `https://steamcommunity.com/dev/apikey` 申请。
3. `steamidkey`：CS2/CS:GO 比赛分享设置中显示的认证 key。
4. `knowncode`：一个已有的官匹比赛分享代码，用作向后获取新比赛的游标。

Steam Web API 可以迭代 share code，但真实 replay URL 仍需要 Steam Game Coordinator full match info。Resolver 细节请看 Wiki。

## Metadata

只导出 metadata，不下载 Demo：

```bash
cs-demo-downloader metadata --all --config config.jsonc --pretty
```

也可以在 `config.jsonc` 中开启下载时自动写入 metadata。成功下载 5E/PWA Demo 后，会在 `.dem` 同目录生成 `*.metadata.json`：

```jsonc
"save_metadata_with_demo": true
```

## 更多文档

详细配置、Steam resolver、Docker Compose、Python API、metadata 结构和开发说明请看 [项目 Wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki)。

## 许可证

MIT。详情见 [LICENSE](LICENSE)。
