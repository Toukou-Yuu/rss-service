FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:/root/.local/bin:${PATH}"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config

RUN uv sync --frozen --no-dev

RUN useradd --create-home --shell /usr/sbin/nologin rss-service \
    && mkdir -p /var/lib/rss-service /reports \
    && chown -R rss-service:rss-service /var/lib/rss-service /reports /app

USER rss-service

ENV RSS_DB_PATH=/var/lib/rss-service/rss.sqlite3 \
    RSS_REPORTS_DIR=/reports \
    RSS_CONFIG_DIR=/app/config \
    RSS_SERVICE_HOST=0.0.0.0 \
    RSS_SERVICE_PORT=8787

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -m rss_service healthcheck

EXPOSE 8787

CMD ["rss-service", "serve"]
