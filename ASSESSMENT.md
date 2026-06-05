# aiwatcher-mcp — Assessment & TODO

**Date:** 2026-06-03  
**Version:** `0.1.6` (`pyproject.toml`, `_version.py`, `server_version`)  
**FastMCP:** 3.2.x

---

## What it is

AI news ingestion, distillation, and alerting — fleet situational awareness. Polls RSS/Atom plus optional Gmail, arXiv, and fleet events; scores with LLM bundles; delivers digests and cross-fleet alerts. **Dual surface:** stdio MCP + HTTP **10946** (`/api/*`, `/mcp`) + Vite **10947**.

---

## Current status: Production-capable

- **Tests:** 100+ pytest targets (`uv run pytest tests`); `test_backend_only_startup` marked slow.
- **Lint:** `uv run ruff check src/ tests/` expected green.
- **Fleet:** Registered in federation hub + Fritz `FLEET_SERVERS`; Day Prep intel wired.
- **Monitoring:** `/metrics` + extended `/health` JSON.

---

## Architecture (summary)

```
APScheduler: poll → distill → sync_interests → retention → alerts → daily_digest
Ingestion: RSS, Gmail, ArXiv, fleet events (Readly blocked upstream)
Storage: SQLite pooled connection, FTS5, digest cache table
Security: env redaction, optional API key, remote /api/env gated
```

---

## What's solid

- Async Starlette + httpx; pydantic-settings.
- Feed resilience, OPML, bundle health, decay flags.
- Digest TTL cache; Calibre via real `/api/books/` path.
- Fritz morning intel; Prometheus metrics.
- Comprehensive test modules (ingestion, distillation, P4 features).

---

## Remaining gaps (roadmap)

| Priority | Item |
|----------|------|
| v0.3 | Cursor pagination; readly when upstream ready; Vite API key header |
| v0.4 | Calibre RAG; digest feedback; DB digest profiles |
| ops | manifest icon path |

---

## Resolved since 2026-05-24

| Item | Resolution |
|------|------------|
| No Fritz bridge | `aiwatcher` in `fleet_bridge.py` + Day Prep |
| Minimal `/health` | Full fleet contract fields |
| Fictional calibre endpoint | `POST /api/books/` + temp HTML |
| `sent_calibre` unused | Set after ingest |
| No digest cache | `DIGEST_CACHE_TTL_MINUTES` |
| Per-connection SQLite | Pooled connection |
| 15 `.bak` files | Removed; `*.bak` in gitignore |
| P3 test gaps | Six+ new test modules |
| P4 backlog | Metrics, decay, fleet events, trends, portfolio, tones |

---

*See [TODO.md](TODO.md) for roadmap-only items.*
