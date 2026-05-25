FROM python:3.11-slim

LABEL maintainer="WangChuDi"
LABEL description="CS Demo Downloader - 5E, PWA and Steam share-code demo downloader"

WORKDIR /app

COPY pyproject.toml README.md README_CN.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

VOLUME ["/config", "/demos"]

ENV DEMO_PATH=/demos

ENTRYPOINT ["cs-demo-downloader", "download", "--all", "--config", "/config/config.json", "--output", "/demos"]
