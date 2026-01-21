# CS Demo Downloader

合并 5E 和完美世界电竞平台的 Demo 下载工具，支持 GUI 界面和命令行模式。

## 功能特点

- 🎮 支持 5E 和完美世界两个平台
- 🖥️ 现代化 GUI 界面（支持打包为 Windows EXE）
- 🐳 Docker 支持，方便服务器自动化下载
- 📦 自动解压 Demo 文件

## 安装

### GUI 版本

```bash
# 安装依赖
pip install -r requirements-gui.txt

# 运行
python main.py
```

### CLI 版本

```bash
# 安装依赖
pip install -r requirements.txt

# 下载所有 Demo
python cli.py download --all

# 只下载 5E Demo
python cli.py download --platform 5e

# 只下载完美世界 Demo
python cli.py download --platform pwa
```

### Docker 版本

```bash
# 构建镜像
docker build -t cs-demo-downloader .

# 准备配置文件
cp config.json.example config/config.json
# 编辑 config/config.json 添加你的用户信息

# 运行下载
docker run --rm \
  -v $(pwd)/config:/config \
  -v /path/to/demos:/demos \
  cs-demo-downloader
```

## 配置文件

参考 `config.json.example`:

```json
{
  "download_path": "/demos",
  "users_5e": [
    {
      "name": "我的账号",
      "userid": "YOUR_5E_USERID"
    }
  ],
  "users_pwa": [
    {
      "name": "我的账号",
      "steamid": "YOUR_STEAM_ID",
      "access_token": "YOUR_ACCESS_TOKEN"
    }
  ]
}
```

### 获取用户信息

#### 5E User ID
在 5E 个人主页 URL 中可以找到，例如 `https://www.5eplay.com/player/11814738gjdwn7`

#### Steam ID 和 Access Token
1. 登录完美世界电竞平台网页版
2. 打开浏览器开发者工具 (F12)
3. 在 Network 标签页中找到相关请求，获取 Steam ID 和 Access Token

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="CS_Demo_Downloader" main.py
```

打包后的 EXE 文件在 `dist/` 目录下。

## 定时自动下载

使用 crontab 配合 Docker：

```bash
# 每天凌晨 3 点自动下载
0 3 * * * docker run --rm -v /home/user/config:/config -v /home/user/demos:/demos cs-demo-downloader
```

## License

MIT
