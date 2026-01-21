FROM python:3.11-slim

LABEL maintainer="WangChuDi"
LABEL description="CS Demo Downloader - 5E and PWA demo downloader"

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY core/ ./core/
COPY cli.py .

# 配置文件和下载目录通过 volume 挂载
VOLUME ["/config", "/demos"]

# 设置默认下载路径
ENV DEMO_PATH=/demos

ENTRYPOINT ["python", "cli.py", "download", "--all", "--config", "/config/config.json", "--output", "/demos"]
