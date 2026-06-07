# aiwatcher-mcp — Product Requirements Document

**Status:** ACTIVE  
**Package version:** **0.1.8** (`pyproject.toml`, `src/aiwatcher_mcp/_version.py`)  
**Product milestone:** **v0.2 bundle** (interest bundles, OPML, feed discovery, bundle health, dedup, feed auto-heal) + **v0.2.2 ops** (Fritz intel, Intel Hub publish, fleet ingest, pipeline liveness)  
**Owner:** Sandra Schipal  
**Ports:** **10946** (HTTP: REST + MCP at `/mcp`) / **10947** (Vite frontend)

---

## Problem

Sandra needs to stay on top of fast-moving AI news without spending time on manual feed triage. Critical events (acquisitions, model releases, security incidents affecting her tooling) must reach her immediately, even at 5am. Brother Steve also wants a readable weekly/daily AI digest without setting up tooling himself.

## Solution

Automated ingestion pipeline: **13+** RSS feeds (seeded on first run or via `just seed-feeds`) + optional Alpha Signal (Gmail) + ArXiv + Readly → scoring with interest bundles → prioritised feed → daily HTML digest (optional, with TTL cache) → TTS / fleet alerts for critical items.

**Dual transport:** stdio MCP (`python -m aiwatcher_mcp.server`) for desktop clients; combined HTTP app (`python -m aiwatcher_mcp.api`) for REST + **`/mcp`**.

**Fleet orchestration:** Registered in **mcp-federation-hub** and **fleet-agent-mcp** (`FLEET_SERVERS.aiwatcher`). Fritz **Office Day Prep** pulls `get_top_items` and creates pulse tasks for high-urgency intel.

## Integrations

| System | Status | Notes |
|---|---|---|
| RSS/Atom feeds | Implemented | Default feeds on DB init; `just seed-feeds` for curated baseline |
| Alpha Signal (Gmail) | Config required | `GMAIL_ENABLED=true` + `GMAIL_MCP_URL` |
| ArXiv papers | Config recommended | `ARXIV_ENABLED=true`, `ARXIV_MCP_URL=http://localhost:10770` |
| Readly magazines | Blocked upstream | `READLY_ENABLED` — needs readly-mcp `list_current_issue_articles` |
| OPML import | Implemented | `import_opml` MCP tool + REST |
| Distillation | Config required | Anthropic and/or OpenAI-compatible locals (`LLM_PROVIDER`) |
| Interest bundles | Implemented | Per-topic prompts, discovery, health; `sync_interests` daily job |
| Cross-feed dedup | Implemented | Title + title/summary fuzzy match (85%, 48h) |
| Feed URL auto-heal | Implemented | Fallback probing on 404/410 |
| Feed quality decay | Implemented | `quality_flag` on feed health (30d avg urgency) |
| Fleet events journal | Implemented | `ingest_fleet_event` MCP tool |
| Portfolio watch | Implemented | `PORTFOLIO_WATCH_TERMS` urgency boost |
| Tag trends | Implemented | `get_tag_trends` / `GET /api/trends` |
| robofang alerts | Config required | `ROBOFANG_ENABLED=true` (default) |
| speechops TTS | Config required | `SPEECHOPS_HTTP_URL` (default **10895**) |
| email-mcp digest | Config required | `EMAIL_ENABLED=true` |
| calibre-mcp archive | Config required | `POST /api/books/` with HTML file |
| Prometheus metrics | Implemented | `GET /metrics` |
| Fritz day prep | Implemented | fleet-agent `coworker_day_prep` |
| Fritz fleet ingest | Implemented | `POST /api/fleet/ingest` — Pulse, Day Prep, devices watch |
| Intel Reports Hub | Implemented | Digest HTML → `INTEL_REPORTS_HUB_URL` (`:11027`) |
| Windows Scheduled Task | Manual setup | `scripts/install_task.ps1` |

## Scheduled jobs (APScheduler)

| Job | Schedule | Purpose |
|---|---|---|
| `poll_feeds` | Every `FEED_POLL_INTERVAL_MINUTES` | RSS/Atom (+ optional sources) |
| `distill` | Every `DISTILLATION_INTERVAL_HOURS` | LLM scoring |
| `sync_interests` | 02:00 UTC daily | `interests.json` → bundles + feed links |
| `retention` | 03:00 UTC daily | Expire old low-urgency items |
| `alerts` | `ALERT_HOUR_UTC:ALERT_MINUTE_UTC` | robofang + speechops |
| `daily_digest` | 06:00 UTC | Email + Calibre (uses digest cache when fresh) |

Morning alert paths:

1. **Backend running** → `POST /api/alerts/check`
2. **Backend offline** → `scripts/morning_alert.py` reads DB directly

## Security

- **`GET /api/env`**: values redacted; **non-loopback** access requires **`AIWATCHER_API_KEY`**.
- **Optional REST auth**: `AIWATCHER_API_KEY` gates all `/api/*` except `/health`, `/api/health`, `/metrics`, `/mcp`.
- Do not expose **10946** to the public internet without a reverse proxy.

## Known gaps

- **`/api/items`**: offset/limit pagination (max 200); no cursor tokens.
- **readly-mcp**: blocked on upstream tool surface.
- **Calibre RAG**: planned v0.4 (semantic search over archived digests).
- **Embedding dedup**: fuzzy match only; full embeddings deferred to v0.3+.
- **Vite + API key**: webapp does not send `X-AIWatcher-Key` when auth is enabled (document or wire Settings).

## Roadmap

### Shipped in 0.1.6 (2026-06-03)

Digest caching, DB pooling, Fritz/federation wiring, feed decay flags, fleet events, trends, portfolio watch, digest audience tones, Prometheus `/metrics`, expanded test suite.

### v0.3 (next)

- Cursor pagination for `/api/items`
- readly-mcp integration when upstream tool exists
- Deeper trend / portfolio dashboards in Vite
- Optional embedding dedup behind feature flag

### v0.4

- Calibre RAG over digest archive
- Digest feedback loop (thumbs up/down per item)
- Per-user digest profiles stored in DB (beyond env tone strings)
