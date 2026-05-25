# CS Demo Downloader 中文文档

CS Demo Downloader 是一个用于下载 Counter-Strike Demo 文件的工具，当前支持 5E 和完美世界电竞平台。项目同时提供 PyQt5 图形界面、命令行模式和 Docker 运行方式，适合桌面使用或服务器定时下载。

[English README](README.md)

## 当前支持的平台

当前代码实际实现了三个平台：

| 平台 | CLI 参数值 | 需要的账号字段 | 说明 |
| --- | --- | --- | --- |
| 5E | `5e` | `userid` | 从 5E 玩家主页 URL 中获取用户 ID。 |
| 完美世界电竞 / PWA | `pwa` | `steamid`, `access_token` | 需要有效的完美世界电竞网页登录/客户端令牌，下载链接会在本地签名。 |
| Steam 官匹 | `steam` | `steamid`, `api_key`, `steamidkey`, `knowncode` | 已实现 Steam Web API share code 迭代；真实 replay URL 仍需要 Steam Game Coordinator full match info。 |

目前没有实现其他平台。

## 功能特点

- 支持下载 5E、完美世界电竞和 Steam 官匹 Demo。
- 支持桌面 GUI 和 CLI 自动化脚本。
- 支持 Docker，方便服务器或定时任务运行。
- 自动解压下载到的 ZIP Demo 压缩包。
- 会拒绝带有路径穿越风险的 ZIP 文件条目，避免解压到目标目录之外。
- CLI 使用显式 `--config` 时，如果配置文件缺失或格式错误，会以非零状态退出，便于自动化任务发现问题。

## 项目结构

```text
.
├── pyproject.toml         # Python 包元数据
├── cli.py                 # 兼容 CLI 包装入口
├── main.py                # 兼容 GUI 包装入口
├── src/cs_demo_downloader/ # 可安装 Python 包
├── tests/                 # unittest 测试
├── Dockerfile
├── docker-compose.yml
├── config.json.example
├── requirements.txt
└── requirements-gui.txt
```

## 环境要求

- 推荐 Python 3.11+。
- CLI 依赖声明在 `pyproject.toml` 中，`requirements.txt` 仅保留兼容。
- GUI 依赖通过 `gui` optional extra 安装。
- Docker 运行需要本机安装 Docker。

在 Linux/macOS 上，如果 `python` 不是 Python 3，请使用 `python3`。

## 配置文件

复制示例配置并填写账号信息：

```bash
cp config.json.example config.json
```

配置结构示例：

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

### 获取 5E User ID

打开 5E 玩家主页 URL，取 URL 中的用户 ID。例如：

```text
https://www.5eplay.com/player/11814738gjdwn7
```

对应的 `userid` 是 `11814738gjdwn7`。

### 获取完美世界电竞 Steam ID 和 Access Token

1. 登录完美世界电竞网页版或客户端。
2. 打开浏览器开发者工具。
3. 在 Network 请求或 Cookie 中查找已登录请求。
4. 将 `steamid` 和 `access_token` 填入 `config.json`。

PWA Demo 下载链接现在会使用当前签名参数生成，并在最终文件请求中发送必要的 PWA 请求头。Access Token 可能会过期。如果 PWA 下载突然不可用，优先刷新 token。

### 获取 Steam 官匹参数

Steam 官匹下载使用 Valve 的 `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API，需要：

1. `steamid`：你的 SteamID64。
2. `api_key`：Steam Web API Key，可在 `https://steamcommunity.com/dev/apikey` 申请。
3. `steamidkey`：CS2/CS:GO 比赛分享设置中显示的认证 key。
4. `knowncode`：一个已有的官匹比赛分享代码，用作向后获取新比赛的游标。
Steam API 会基于 `knowncode` 返回下一个 share code，下载器可以本地迭代这些 share code。但 Steam Web API 本身不会返回最终 replay URL。真实 `.dem.bz2` 地址必须从 Steam Game Coordinator full match info 中读取，通常是比赛信息里的 `map` 字段。当前未配置 GC 解析器时，Steam 平台会明确提示无法解析真实 replay URL，而不会返回伪造下载地址。

### Steam Demo URL Resolver

Steam 官匹提供两个 optional resolver 后端：

- `boiler`：桌面/本机后端，调用 `akiver/boiler-writter`。要求本机 Steam 正在运行并已登录，不需要保存 Steam 密码，推荐 GUI 和本机 CLI 使用。配置 `steam_resolver.type = "boiler"`。设置 `steam_resolver.auto_download = "true"` 可自动下载最新 boiler-writter release 到本地缓存，也可以用 `steam_resolver.executable_path` 指向手动安装的 binary。
- `steam-login`：面向无头环境的后端，使用 optional `steam`/`csgo` 依赖连接 Game Coordinator。凭据只从 `STEAM_GC_USERNAME`、`STEAM_GC_PASSWORD` 等环境变量读取，不要写入 `config.json`。真实 Steam 登录仍需要可用账号，无法通过本地单元测试验证。

Docker 镜像不会内置 `boiler-writter`，也不能直接使用桌面 Steam resolver，除非你自己提供可用的 Steam 客户端环境。

按需安装 optional resolver 依赖：

```bash
pip install -e .[steam-boiler]
pip install -e .[steam-login]
```

## 通过 pip 安装

安装默认 CLI/运行时包：

```bash
pip install cs-demo-downloader
```

可选 extras：

```bash
# 桌面 GUI
pip install "cs-demo-downloader[gui]"

# Steam 官匹：本机 Steam + boiler-writter parser 依赖
pip install "cs-demo-downloader[steam-boiler]"

# Steam 官匹：steam-login/csgo GC 依赖
pip install "cs-demo-downloader[steam-login]"
```

如果是从本仓库源码本地开发，使用 editable install：

```bash
pip install -e .
pip install -e ".[gui]"
```

安装后会提供两个命令：

- `cs-demo-downloader`：命令行下载器。
- `cs-demo-downloader-gui`：PyQt5 桌面 GUI，需要安装 `gui` extra。

## CLI 使用

查看帮助：

```bash
cs-demo-downloader --help
cs-demo-downloader download --help
```

下载所有已配置平台：

```bash
cs-demo-downloader download --all --config config.json
```

只下载 5E Demo：

```bash
cs-demo-downloader download --platform 5e --config config.json
```

只下载完美世界电竞 Demo：

```bash
cs-demo-downloader download --platform pwa --config config.json
```

只下载 Steam 官匹 Demo：

```bash
cs-demo-downloader download --platform steam --config config.json
```

覆盖配置里的下载目录：

```bash
cs-demo-downloader download --all --config config.json --output ./demos
```

当显式传入 `--config` 时，如果该文件不存在或 JSON 格式错误，CLI 会输出错误并返回非零退出码。这是为了让 Docker、cron、CI 等自动化环境能及时发现配置问题。

## Python API 使用

安装后也可以在你自己的 Python 脚本中直接导入内置函数。公开模块主要包括各平台 downloader 和通用下载/解压 helper。

### 5E

```python
from cs_demo_downloader.core.downloader_5e import get_all_demo_urls
from cs_demo_downloader.core.utils import download_and_extract

demo_urls = get_all_demo_urls("YOUR_5E_USERID")

for match_id, demo_url in demo_urls.items():
    print("downloading", match_id)
    download_and_extract(demo_url, "./demos")
```

### 完美世界电竞 / PWA

PWA 下载需要 signed URL 和 PWA 下载请求头。生成的 URL 包含 `access_token`，不要打印或持久化保存。

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

如果只想拿 signed URL 给其他下载器使用：

```python
from cs_demo_downloader.core.downloader_pwa import get_demo_url

demo_url = get_demo_url("MATCH_ID", "YOUR_PWA_ACCESS_TOKEN")
```

### Steam 官匹

Steam Web API share-code 迭代在 `downloader_steam` 中提供。真实 replay URL 仍需要 Steam GC resolver，例如内置的 boiler-writter resolver。

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

### 配置文件 helper

如果想复用 CLI 的 JSON 配置文件：

```python
from cs_demo_downloader.core.config import load_config

config = load_config("config.json")
for user in config.get_users_pwa():
    print(user.name, user.steamid)
```

## GUI 使用

安装 GUI 依赖并启动：

```bash
pip install -e .[gui]
cs-demo-downloader-gui
```

GUI 支持：

- 选择下载目录；
- 添加/删除 5E、完美世界电竞和 Steam 官匹用户；
- 刷新 Demo 列表；
- 下载选中的 Demo。

GUI 使用默认配置查找路径。如果没有配置文件，会以空配置启动，方便你在界面中添加账号。

## Docker 使用

构建镜像：

```bash
docker build -t cs-demo-downloader .
```

准备挂载目录和配置文件：

```bash
mkdir -p config demos
cp config.json.example config/config.json
# 运行前请编辑 config/config.json。
```

运行一次下载：

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  cs-demo-downloader
```

Docker 默认入口命令等价于：

```bash
cs-demo-downloader download --all --config /config/config.json --output /demos
```

因为 Docker 使用显式配置路径，所以 `/config/config.json` 必须存在且格式正确。

### Docker Compose

```bash
docker compose run --rm cs-demo-downloader
```

## 定时自动下载

每天凌晨 3 点运行的 crontab 示例：

```cron
0 3 * * * docker run --rm -v /home/user/config:/config -v /home/user/demos:/demos cs-demo-downloader
```

请确认 `/home/user/config/config.json` 已存在。

## 打包桌面程序

安装 GUI 依赖和 PyInstaller：

```bash
pip install -e .[gui]
pip install pyinstaller
```

打包为单文件程序：

```bash
pyinstaller --onefile --windowed --name="CS_Demo_Downloader" main.py
```

产物会输出到 `dist/` 目录。

## 测试

运行本地 unittest：

```bash
python3 -m unittest discover
```

运行语法/字节码检查：

```bash
python3 -m compileall .
```

测试不需要真实 5E/完美世界电竞/Steam 账号，也不会访问真实网络。

## 注意事项和限制

- 当前支持 5E 和完美世界电竞 / PWA 下载。Steam 官匹已实现 share code 迭代，但真实 replay URL 解析还需要 Steam GC full-match-info resolver。
- PWA access token 可能过期，需要手动刷新。
- Demo 是否可下载取决于上游平台接口和账号权限。
- 本地配置、Demo 文件和下载产物不会提交到 git。

## License

MIT
