# aiwatcher-mcp — Dockerfile
# Runs the Starlette REST backend + FastMCP stdio server on :10946.
# The Vite frontend (dist/) is served as static files via Starlette.
#
# Build:  docker build -t aiwatcher-mcp .
# Run:    docker run -p 10946:10946 --env-file .env -v ./data:/app/data aiwatcher-mcp

FROM python:3.11-slim AS base

# System deps: lxml needs libxml2, feedparser needs nothing extra
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# --- Dependencies layer (cached unless pyproject.toml changes) ---
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# --- Application source ---
COPY src/ ./src/
COPY dist/ ./dist/

# Data directory (override with -v ./data:/app/data for persistence)
RUN mkdir -p /app/data

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# --- Runtime ---
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/aiwatcher.db
ENV BACKEND_PORT=10946

EXPOSE 10946

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:10946/api/health || exit 1

CMD ["/app/.venv/bin/python", "-m", "aiwatcher_mcp.api"]
