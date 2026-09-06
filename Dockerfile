FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.3@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM builder AS test
RUN uv sync --frozen
COPY tests ./tests
COPY data/calendar ./data/calendar
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["/app/.venv/bin/pytest", "-q"]

FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285 AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/calendar \
    DATABASE_URL=sqlite+aiosqlite:////app/data/olymping.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 10001 olymping
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY data/calendar ./calendar
RUN mkdir -p /app/data && chown -R olymping:olymping /app
USER olymping
VOLUME ["/app/data"]
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD ["olymping", "healthcheck"]
CMD ["olymping", "bot"]
