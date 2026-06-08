# CS Demo Downloader 中文文档

CS Demo Downloader 是一个用于下载 Counter-Strike Demo 文件的工具，当前支持 5E、完美世界电竞和 Steam 官匹。项目提供命令行模式、Python API 和 Docker 运行方式，适合本地脚本或服务器定时下载。

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
- 支持 CLI 自动化脚本，也可以直接导入 Python API。
- 支持 Docker，方便服务器或定时任务运行。
- 自动解压下载到的 ZIP Demo 压缩包。
- 会拒绝带有路径穿越风险的 ZIP 文件条目，避免解压到目标目录之外。
- CLI 使用显式 `--config` 时，如果配置文件缺失或格式错误，会以非零状态退出，便于自动化任务发现问题。

## 项目结构

```text
.
├── pyproject.toml         # Python 包元数据
├── cli.py                 # 兼容 CLI 包装入口
├── src/cs_demo_downloader/ # 可安装 Python 包
├── tests/                 # unittest 测试
├── Dockerfile
├── docker-compose.yml
├── config.jsonc.example
└── requirements.txt
```

## 环境要求

- 推荐 Python 3.11+。
- CLI 依赖声明在 `pyproject.toml` 中，`requirements.txt` 仅保留兼容。
- Docker 运行需要本机安装 Docker。

在 Linux/macOS 上，如果 `python` 不是 Python 3，请使用 `python3`。

## 配置文件

复制 JSONC 示例配置并填写账号信息：

```bash
cp config.jsonc.example config.jsonc
```

配置结构示例：

```jsonc
{
  // "." 表示下载到当前运行目录。
  "download_path": ".",
  "scheduler": {
    "enabled": false,
    "interval_seconds": 86400,
    "run_on_start": false,
    "config": "/config/config.jsonc",
    "output": "/demos",
    "platforms": "all"
  },
  "five_e": {
    "users": [
      {
        "label": "example_5e_user", // 仅用于日志显示。
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

配置加载器同时支持新的嵌套 JSONC schema 和旧版 `config.json` schema。`label` 取代 `name`，含义更明确：它只是日志里的显示名称；加载旧配置时仍兼容 `name`。

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
4. 将 `pwa.default_access_token` 和每个目标 `steamid` 填入 `config.jsonc`。

PWA Demo 下载链接现在会使用当前签名参数生成，并在最终文件请求中发送必要的 PWA 请求头。Access Token 可能会过期。如果 PWA 下载突然不可用，优先刷新 token。

PWA 签名由私有编译 wheel `cs-demo-pwa-signer` 提供。公开 downloader 仓库不包含签名算法源码。`s` 参数计算算法是由 Sisyphus 逆向得到的；为了减轻后续维护压力，现已将其打包至 wheel 包中，不会影响正常下载使用。使用 PWA 下载前需要先安装私有 wheel；wheel 的接口约定和发布前检查见 `docs/private-pwa-signer-wheel.md`。如果有其他项目希望不使用当前 pip 包实现 demo 下载功能，可以联系 `wangchudi666@gmail.com`。

如果一个 PWA access token 可以访问多个目标 Steam 账号，把它写在 `pwa.default_access_token`，然后为每个目标 `steamid` 添加一条 `pwa.users` 配置。单个目标也可以用自己的 `access_token` 覆盖默认 token。

### 获取 Steam 官匹参数

Steam 官匹下载使用 Valve 的 `ICSGOPlayers_730/GetNextMatchSharingCode/v1` Web API，需要：

1. `steamid`：你的 SteamID64。
2. `api_key`：Steam Web API Key，可在 `https://steamcommunity.com/dev/apikey` 申请。
3. `steamidkey`：CS2/CS:GO 比赛分享设置中显示的认证 key。
4. `knowncode`：一个已有的官匹比赛分享代码，用作向后获取新比赛的游标。
Steam API 会基于 `knowncode` 返回下一个 share code，下载器可以本地迭代这些 share code。但 Steam Web API 本身不会返回最终 replay URL。真实 `.dem.bz2` 地址必须从 Steam Game Coordinator full match info 中读取，通常是比赛信息里的 `map` 字段。当前未配置 GC 解析器时，Steam 平台会明确提示无法解析真实 replay URL，而不会返回伪造下载地址。

### Steam Demo URL Resolver

Steam 官匹提供两个 optional resolver 后端：

- `boiler`：本机后端，调用 `akiver/boiler-writter`。要求本机 Steam 正在运行并已登录，不需要保存 Steam 密码，推荐本机 CLI 使用。配置 `steam.resolver.type = "boiler"`。设置 `steam.resolver.auto_download = "true"` 可自动下载最新 boiler-writter release 到本地缓存，也可以用 `steam.resolver.executable_path` 指向手动安装的 binary。
- `steam-login`：面向无头环境的后端，使用 optional `steam`/`csgo` 依赖连接 Game Coordinator。凭据只从 `STEAM_GC_USERNAME`、`STEAM_GC_PASSWORD` 等环境变量读取，不要写入配置文件。真实 Steam 登录仍需要可用账号，无法通过本地单元测试验证。

Docker 镜像不会内置 `boiler-writter`，也不能直接使用本机 Steam resolver，除非你自己提供可用的 Steam 客户端环境。

如果是本地源码目录，按需安装 optional resolver 依赖：

```bash
pip install -e .[steam-boiler]
pip install -e .[steam-login]
```

## 从 PyPI 安装

安装最新正式版：

```bash
pip install cs-demo-downloader
```

可选 extras：

```bash
# Steam 官匹：本机 Steam + boiler-writter parser 依赖
pip install "cs-demo-downloader[steam-boiler]"

# Steam 官匹：steam-login/csgo GC 依赖
pip install "cs-demo-downloader[steam-login]"
```

也可以直接从公开 GitHub 仓库的 main 分支安装：

```bash
pip install git+https://github.com/WangChuDi/CS-Demo-Downloader.git
```

如果是从本仓库源码本地开发，使用 editable install：

```bash
pip install "$(python scripts/select_private_signer_wheel.py wheelhouse)"
pip install -e .
```

Windows PowerShell：

```powershell
$wheel = python scripts/select_private_signer_wheel.py wheelhouse
pip install $wheel
pip install -e .
```

私有 signer wheel 只在真实 PWA 签名时需要；公开测试会 mock 这个边界。

安装后会提供这个命令：

- `cs-demo-downloader`：命令行下载器。

## CLI 使用

查看帮助：

```bash
cs-demo-downloader --help
cs-demo-downloader download --help
cs-demo-downloader schedule --help
```

下载所有已配置平台：

```bash
cs-demo-downloader download --all --config config.jsonc
```

只下载 5E Demo：

```bash
cs-demo-downloader download --platform 5e --config config.jsonc
```

只下载完美世界电竞 Demo：

```bash
cs-demo-downloader download --platform pwa --config config.jsonc
```

只下载 Steam 官匹 Demo：

```bash
cs-demo-downloader download --platform steam --config config.jsonc
```

只导出 5E/PWA metadata，不下载 demo 文件：

```bash
cs-demo-downloader metadata --all --config config.jsonc --pretty
cs-demo-downloader metadata --platform pwa --config config.jsonc --limit 5 --include-raw
```

`metadata` 命令会输出 JSON 列表。默认会脱敏 URL query 中的 PWA `access_token` 和签名参数；即使使用 `--include-raw`，原始字段里的 URL 也会继续脱敏。

每条比赛仍保留旧字段，例如 `platform`、`match_id`、`demo_url`、`demo_available`、`teams`、`players`、`round_results`、`raw_summary` 和 `raw_detail`，方便旧脚本继续读取。新版导出额外包含：

- `schema_version`：metadata 结构版本，当前为 `1.1`。
- `exported_at`：序列化导出时写入的 UTC 时间。
- `duration_seconds`：当 `started_at` 和 `ended_at` 有效时自动计算的比赛时长。
- `demo`：归组后的 demo 信息，包括脱敏后的 `url`、`available`、来源和平台 demo 状态字段。
- `rounds`：更完整的回合列表。PWA 会按回合号合并 `report.results` 和 `round_simple_list`，同时保留旧的 `round_results` 给已有消费者使用。

显式更新缓存的 PWA `PvpAlive.dll`，不会下载完整官方客户端 ZIP：

```bash
cs-demo-downloader update-pvpalive-dll --target cache/PvpAlive.dll
```

该命令会读取官方 `latest.yml`，推导对应 ZIP URL，通过 HTTP Range 只读取 ZIP 尾部、central directory、local header 和 `plugin/PvpAlive.dll` 的压缩数据，校验大小和 CRC32 后再原子替换目标缓存文件。它会在 DLL 旁边写入 `PvpAlive.dll.json` 版本元数据；如果缓存元数据已经对应最新版客户端，就不会再次下载 DLL 数据。需要强制刷新时传 `--force`。它不会修改官方客户端安装目录，也不会影响默认的纯 Python 签名流程，除非你显式调用。

覆盖配置里的下载目录：

```bash
cs-demo-downloader download --all --config config.jsonc --output ./demos
```

当显式传入 `--config` 时，如果该文件不存在或 JSON 格式错误，CLI 会输出错误并返回非零退出码。这是为了让 Docker、cron、CI 等自动化环境能及时发现配置问题。

前台运行内置 scheduler：

```bash
cs-demo-downloader schedule --config config.jsonc --enabled --interval-seconds 86400 --run-on-start
```

默认情况下，scheduler 不会自动下载，只会打印空闲提示并等待 `SIGINT` 或 `SIGTERM`。只有在 CLI 参数、环境变量或可选的 `scheduler` 配置段里显式启用后，才会自动下载。

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

### 在 Python 中导出 metadata

从 pip 包安装后，也可以直接在 Python 中抓取规范化 metadata。写 JSON 前建议调用 `metadata_list_to_dicts()`，这样会和 CLI 一样处理 schema 字段、导出时间、URL 脱敏以及是否包含 raw 字段。

```python
import json

from cs_demo_downloader.core.downloader_5e import get_all_demo_metadata as get_5e_metadata
from cs_demo_downloader.core.downloader_pwa import get_all_demo_metadata as get_pwa_metadata
from cs_demo_downloader.core.metadata import metadata_list_to_dicts

matches = []
matches.extend(get_5e_metadata("YOUR_5E_USERID", limit=10))
matches.extend(get_pwa_metadata("YOUR_STEAM_ID64", "YOUR_PWA_ACCESS_TOKEN", size=10))

payload = metadata_list_to_dicts(matches, redact_sensitive_urls=True, include_raw=False)
print(json.dumps(payload, ensure_ascii=False, indent=2))
```

真实 PWA metadata 需要安装私有 `cs-demo-pwa-signer` wheel，因为 PWA match-list fallback 解密和 demo URL 签名依赖这个编译边界。5E metadata 不需要该 wheel。

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

如果想复用 CLI 的 JSONC 配置文件：

```python
from cs_demo_downloader.core.config import load_config

config = load_config("config.jsonc")
for user in config.get_users_pwa():
    print(user.label, user.steamid)
```

### PWA DLL 缓存更新

也可以在 Python 代码中显式调用更新函数：

```python
from cs_demo_downloader.pwa_dll_updater import update_cached_pvp_alive_dll

dll_path = update_cached_pvp_alive_dll(target_path="cache/PvpAlive.dll", force=False)
print(dll_path)
```

当前下载器在所有平台默认使用私有编译 signer wheel。如果明确需要 DLL fallback，可以把 `pwa.signature_provider` 设置为以下值之一：

- `compiled`：默认私有编译 wheel 签名，不使用 DLL 或 Wine。
- `pvp_alive_native`：Windows 上直接调用包内 32 位 bridge。
- `pvp_alive_wine`：Linux 上通过 Wine 调用包内 32 位 bridge。

DLL 不会提交到仓库或打进包内；需要时请显式刷新缓存：

```bash
cs-demo-downloader update-pvpalive-dll --target cache/PvpAlive.dll
```

Python 用户也可以直接调用 bridge helper：

```python
from cs_demo_downloader.pwa_bridge import call_pvp_alive_swap_data

signature = call_pvp_alive_swap_data(
    dll_path="cache/PvpAlive.dll",
    inner_json='{"your":"payload"}',
)
```

Linux Wine 用法必须显式调用：

```python
from cs_demo_downloader.pwa_bridge import call_pvp_alive_swap_data_wine

signature = call_pvp_alive_swap_data_wine(
    dll_path="cache/PvpAlive.dll",
    inner_json='{"your":"payload"}',
)
```

macOS 用户应直接调用纯 Python 签名函数；本项目不会内置 macOS Wine/QEMU fallback。

## Docker 使用

使用已发布到 GitHub Container Registry 的无 Wine 默认镜像：

```bash
docker pull ghcr.io/wangchudi/cs-demo-downloader:latest
```

当推送 `v*` Git tag 或发布 GitHub Release 时，GitHub Actions 会自动构建并发布镜像。Release 镜像会带有 `latest`、完整语义化版本号（例如 `0.1.0`）以及较短版本别名（例如 `0.1`、`0`，如适用）。

带 Wine 的镜像会使用单独的 `-wine` 后缀发布，例如：

```bash
docker pull ghcr.io/wangchudi/cs-demo-downloader:latest-wine
```

Wine 镜像目前只构建 `linux/amd64`，因为包内 PWA bridge 是 32 位 Windows exe。

也可以从本仓库本地构建镜像：

```bash
cp /path/to/cs_demo_pwa_signer-0.1.0-*.whl wheelhouse/
docker build --build-arg PYTHON_VERSION=3.12 -t cs-demo-downloader .
docker build --build-arg PYTHON_VERSION=3.12 -f Dockerfile.wine -t cs-demo-downloader:wine .
```

准备挂载目录和配置文件：

```bash
mkdir -p config demos
cp config.jsonc.example config/config.jsonc
# 运行前请编辑 config/config.jsonc。
```

默认启动容器：

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

默认镜像现在执行 `cs-demo-downloader schedule`，启动后保持空闲，除非显式启用内部调度。因为禁用状态下不会读取 `/config/config.jsonc`，所以它可以只作为一个装好依赖的运行环境启动。

手动执行一次下载：

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  download --all --config /config/config.jsonc --output /demos
```

Docker 默认入口命令等价于：

```bash
cs-demo-downloader schedule
```

通过环境变量启用自动定时下载：

```bash
docker run --rm \
  -e CS_DEMO_SCHEDULE_ENABLED=true \
  -e CS_DEMO_SCHEDULE_CONFIG=/config/config.jsonc \
  -e CS_DEMO_SCHEDULE_OUTPUT=/demos \
  -e CS_DEMO_SCHEDULE_INTERVAL_SECONDS=86400 \
  -e CS_DEMO_SCHEDULE_RUN_ON_START=false \
  -e CS_DEMO_SCHEDULE_PLATFORMS=all \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  ghcr.io/wangchudi/cs-demo-downloader:latest
```

同样的调度设置也可以写在 `config.jsonc` 的可选 `scheduler` 段中，环境变量优先级更高。

默认 Linux 容器使用私有编译 signer wheel，不包含 Wine。如果你只是想刷新缓存 DLL，可以挂载 cache 目录并显式运行 updater：

```bash
docker run --rm \
  -v "$(pwd)/cache:/cache" \
  ghcr.io/wangchudi/cs-demo-downloader:latest \
  update-pvpalive-dll --target /cache/PvpAlive.dll
```

如果要使用 Linux Wine bridge 镜像，请切换到 `-wine` tag，并在配置中设置 `"signature_provider": "pvp_alive_wine"` 和 `"pvp_alive_dll": "/cache/PvpAlive.dll"`：

```bash
docker run --rm \
  -v "$(pwd)/config:/config" \
  -v "$(pwd)/demos:/demos" \
  -v "$(pwd)/cache:/cache" \
  ghcr.io/wangchudi/cs-demo-downloader:latest-wine
```

### Docker Compose

```bash
docker compose up -d cs-demo-downloader
```

`docker-compose.yml` 默认使用 `ghcr.io/wangchudi/cs-demo-downloader:latest`，并挂载 `./config`、`./demos` 和 `./cache`。Compose 默认也是空闲 scheduler 模式。需要自动下载时，取消注释 compose 文件中的示例环境变量即可。

手动执行一次下载：

```bash
docker compose run --rm cs-demo-downloader download --all --config /config/config.jsonc --output /demos
```

启动 Wine 变体：

```bash
docker compose --profile wine up -d cs-demo-downloader-wine
```

## 定时自动下载

你可以使用内置 scheduler，也可以继续使用 cron 等外部调度。下面是每天凌晨 3 点执行一次性下载的 crontab 示例：

```cron
0 3 * * * docker run --rm -v /home/user/config:/config -v /home/user/demos:/demos ghcr.io/wangchudi/cs-demo-downloader:latest download --all --config /config/config.jsonc --output /demos
```

请确认 `/home/user/config/config.jsonc` 已存在。

## 测试

运行本地 unittest：

```bash
python3 -m unittest discover
```

运行语法/字节码检查：

```bash
python3 -m compileall src tests cli.py
```

测试不需要真实 5E/完美世界电竞/Steam 账号，也不会访问真实网络。安装测试会创建临时虚拟环境，通过 `pip install` 安装当前包，并验证安装后的包里包含 bundled signer manifest、会从 `site-packages` 加载匹配的 vendored signer 二进制，同时确认 `wheel` 构建依赖由 pip build isolation 自动提供，不需要手动安装 wheel。

## 注意事项和限制

- 当前支持 5E 和完美世界电竞 / PWA 下载。Steam 官匹已实现 share code 迭代，但真实 replay URL 解析还需要 Steam GC full-match-info resolver。
- PWA access token 可能过期，需要手动刷新。
- Demo 是否可下载取决于上游平台接口和账号权限。
- 本地配置、Demo 文件和下载产物不会提交到 git。
- `cache/` 或 `vendor/PvpAlive/` 下缓存的 `PvpAlive.dll` 会被 git 忽略，不应提交到仓库。
- PWA 签名需要私有 `cs-demo-pwa-signer` wheel。公开源码树不能包含 signer 算法源码，也不能发布该包的 sdist。如果有其他项目希望不使用当前 pip 包实现 demo 下载功能，可以联系 `wangchudi666@gmail.com`。
- pip 包内包含 32 位 Windows C++ bridge exe，供显式 DLL fallback 使用。Linux 默认使用私有编译 signer；只有显式使用 `pvp_alive_wine` provider 或 `*-wine` Docker 镜像时才会走 Wine。项目不会内置 QEMU fallback。

## 许可证

本项目使用 MIT 许可证。详情见 [LICENSE](LICENSE)。

如果你认为本项目中的任何内容侵犯了你的权益，请通过 GitHub issue 或邮件 `wangchudi666@gmail.com` 联系维护者。
