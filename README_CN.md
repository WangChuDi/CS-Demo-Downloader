# CS Demo Downloader 中文文档

用于下载 Counter-Strike Demo 文件，支持 5E、完美世界电竞 / PWA 和 Steam 官匹。

[English README](README.md) · [中文详细使用 Wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南)

## 目录

- [pip 快速开始](#pip-快速开始)
  - [Python API 快速开始](#python-api-快速开始)
- [Docker 快速开始](#docker-快速开始)
- [配置](#配置)
- [平台凭据](#平台凭据)
  - [5E](#5e)
  - [完美世界电竞 / PWA](#完美世界电竞--pwa)
  - [Steam 官匹](#steam-官匹)
- [Metadata](#metadata)
- [更多文档](#更多文档)
- [许可证](#许可证)

## pip 快速开始

完整 pip 安装和 CLI 说明：[Wiki 安装说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#2-安装) 与 [Wiki CLI 说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#5-cli-使用)。

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

### Python API 快速开始

完整 Python 示例：[Wiki Python API 说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#8-python-api)。

5E Demo URL：

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_urls

demo_urls = get_all_demo_urls("YOUR_5E_USERID")
```

PWA Demo URL 需要 signed URL 和 PWA 下载请求头。生成的 URL 包含 `access_token`，不要打印或持久化保存。

```python
from cs_demo_downloader.core.downloader_pwa import build_download_headers, get_all_demo_urls

steamid = "YOUR_STEAM_ID64"
access_token = "YOUR_PWA_ACCESS_TOKEN"

headers = build_download_headers(steamid)
demo_urls = get_all_demo_urls(steamid, access_token, size=20)
```

规范化 metadata：

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_metadata as get_5e_metadata
from cs_demo_downloader.core.metadata import metadata_list_to_dicts

matches = get_5e_metadata("YOUR_5E_USERID", limit=10)
payload = metadata_list_to_dicts(matches, redact_sensitive_urls=True, include_raw=False)
```

## Docker 快速开始

完整 Docker 说明、scheduler 行为和镜像变体：[Wiki Docker 说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#7-docker-使用)。

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

完整 JSONC schema 和兼容性说明：[Wiki 配置说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#3-配置文件)。

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

完整平台凭据说明：[Wiki 平台凭据说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#4-平台凭据)。

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

完整 metadata 命令和 schema 说明：[Wiki Metadata 说明](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南#6-metadata)。

只导出 metadata，不下载 Demo：

```bash
cs-demo-downloader metadata --all --config config.jsonc --pretty
```

也可以在 `config.jsonc` 中开启下载时自动写入 metadata。成功下载 5E/PWA Demo 后，会在 `.dem` 同目录生成 `*.metadata.json`：

```jsonc
"save_metadata_with_demo": true
```

## 更多文档

详细 Steam resolver、Docker Compose、PWA DLL 更新器、测试和限制说明请看 [中文详细使用 Wiki](https://github.com/WangChuDi/CS-Demo-Downloader/wiki/使用指南)。

## 许可证

MIT。详情见 [LICENSE](LICENSE)。
