# Official uv image: Python 3.11 + uv (Debian bookworm slim).
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Layer 1: dependencies (cached unless pyproject/lock change).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Layer 2: application code.
COPY . .
RUN chmod +x docker/entrypoint.sh

ENV WAREHOUSE_DB=/app/data/omop.duckdb

EXPOSE 8000 8501

ENTRYPOINT ["/app/docker/entrypoint.sh"]
