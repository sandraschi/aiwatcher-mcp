# CONFIGURATION — aiwatcher-mcp

All settings live in `src/aiwatcher_mcp/config.py` (`Settings`, pydantic-settings,
`.env` file). Never scatter `os.getenv()` — add a `Field` with alias instead.
`.env.example` (201 lines) is the full template; copy to `.env` and fill secrets.
Never commit `.env`.

## Server

| Var | Default | Purpose |
|-----|---------|---------|
| `BACKEND_PORT` | 10946 | Starlette + FastMCP HTTP (`/mcp`), registry-pinned |
| `FRONTEND_PORT` | 10947 | Vite dev / preview, adjacent to backend |
| `LOG_LEVEL` | INFO | Python logging level |
| `AIWATCHER_API_KEY` | (empty = disabled) | REST auth: `X-AIWatcher-Key` or `Authorization: Bearer` on `/api/*` (`/health`, `/mcp` stay public) |
| `DB_PATH` | data/aiwatcher.db | SQLite (WAL). Stdio clients proxy the HTTP daemon — see AGENTS.md "HTTP Daemon + Stdio Proxy" |
| `AIWATCHER_API_URL` | http://127.0.0.1:{BACKEND_PORT}/mcp | Override for the stdio→daemon probe |
| `MCP_BRIDGE_URLS` | (empty) | Comma-separated extra MCP providers to bridge |
| `AIWATCHER_E2E` | false | E2E mode: skip live polling + model validation |

## Pipeline

| Var | Default | Purpose |
|-----|---------|---------|
| `FEED_POLL_INTERVAL_MINUTES` | 30 | RSS/Atom poll cadence (scheduler) |
| `MAX_ITEMS_PER_FEED` | 50 | Cap per poll per feed |
| `DIGEST_CACHE_TTL_MINUTES` | 60 | Reuse last digest body window (0 = always regenerate) |
| `ITEM_RETENTION_DAYS` | 90 | `expire_old_items` retention |
| `PORTFOLIO_WATCH_TERMS` / `PORTFOLIO_WATCH_URGENCY_BOOST` | (see .env.example) / 1.0 | Keyword urgency boost during distillation |
| `ALERT_THRESHOLD` | 8.5 | Urgency ≥ threshold fires robofang + TTS |

## LLM (local-first)

| Var | Default | Purpose |
|-----|---------|---------|
| `LLM_PROVIDER` | ollama | ollama \| lmstudio \| deepseek \| anthropic |
| `LLM_BASE_URL` | http://127.0.0.1:11434/v1 | Provider base URL |
| `DISTILLATION_MODEL` / `DISTILLATION_FLASH_MODEL` | muse-glimmer-131k:latest | Pro + flash models |
| `DISTILLATION_INTERVAL_HOURS` | 4 | Scoring cadence |
| `CLOUD_PROVIDERS_ALLOWED` | (empty = local-only) | `deepseek`, `deepseek,anthropic`, ... gates ALL cloud calls |
| `DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY` | (empty) | Cloud keys (only used when allow-listed) |

## Fleet integrations (all optional, fail-soft)

robofang :10871 (breaking alerts) · speech-mcp :10909 (TTS) · email-mcp :10813
(digest delivery) · calibre-mcp :10720 (archival) · arxiv-mcp :10770 (papers) ·
INTEL_REPORTS_HUB_URL (default :11027, iPad/Tailscale hub). See ARCHITECTURE.md.
