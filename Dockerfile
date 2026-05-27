FROM python:3.11-slim

LABEL maintainer="WangChuDi"
LABEL description="CS Demo Downloader - 5E, PWA and Steam share-code demo downloader"
LABEL org.opencontainers.image.source="https://github.com/WangChuDi/CS-Demo-Downloader"
LABEL org.opencontainers.image.description="CLI Docker image for scheduled Counter-Strike demo downloads"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY pyproject.toml README.md README_CN.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /config /demos /cache \
    && chown -R appuser:appuser /config /demos /cache

VOLUME ["/config", "/demos", "/cache"]

ENV DEMO_PATH=/demos

USER appuser

ENTRYPOINT ["cs-demo-downloader"]
CMD ["download", "--all", "--config", "/config/config.jsonc", "--output", "/demos"]
