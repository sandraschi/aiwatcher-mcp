# aiwatcher-mcp — Product Requirements Document

**Status:** ACTIVE  
**Package version:** **0.1.0** (`pyproject.toml`, `src/aiwatcher_mcp/_version.py`) — use this for releases and dependencies.  
**Product milestone:** **v0.2 bundle** (interest bundles, OPML, feed discovery, bundle health, dedup, feed auto-heal, etc.) — shipped in repo history **2026-04**; PRD describes that capability level, not the semver digit alone.  
**Owner:** Sandra Schipal  
**Ports:** **10946** (HTTP: REST + MCP at `/mcp`) / **10947** (Vite frontend)

---

## Problem

Sandra needs to stay on top of fast-moving AI news without spending time on
manual feed triage. Critical events (acquisitions, model releases, security
incidents affecting her tooling) must reach her immediately, even at 5am.
Brother Steve also wants a readable weekly/daily AI digest without needing
to set up any tooling himself.

## Solution

Automated ingestion pipeline: **13+** RSS feeds + optional Alpha Signal (Gmail) + ArXiv + Readly →
scoring with interest bundles → prioritised feed → daily HTML digest (optional) → TTS / fleet alerts for critical items.

**Dual transport:** stdio MCP (`python -m aiwatcher_mcp.server`) for desktop clients; combined HTTP app (`python -m aiwatcher_mcp.api`) for REST + **`/mcp`**.

## Integrations

| System | Status | Notes |
|---|---|---|
| RSS/Atom feeds | Implemented | Default feeds seeded on first DB init |
| Alpha Signal (Gmail) | Config required | `GMAIL_ENABLED=true` + Gmail/MCP wiring per `.env` |
| ArXiv papers | Config required | `ARXIV_ENABLED=true` + `ARXIV_MCP_URL` |
| Readly magazines | Config required | `READLY_ENABLED=true` + `READLY_MCP_URL` |
| OPML import | Implemented | `import_opml` MCP tool + REST |
| Distillation | Config required | Anthropic and/or OpenAI-compatible locals (`LLM_PROVIDER`) |
| Interest bundles | Implemented | Per-topic prompts, discovery, health |
| Cross-feed dedup | Implemented | High title similarity, 48h window |
| Feed URL auto-heal | Implemented | Fallback probing on 404/410 |
| robofang alerts | Config required | `ROBOFANG_ENABLED=true` (default) |
| speechops TTS | Config required | `SPEECHOPS_HTTP_URL` (default fleet port **10895**) |
| email-mcp digest | Config required | `EMAIL_ENABLED=true` |
| calibre-mcp archive | Config required | `CALIBRE_ENABLED=true` |
| Windows Scheduled Task | Manual setup | `scripts/install_task.ps1` |

## Scheduled task architecture

The morning alert has two paths:

1. **Backend running** → `POST /api/alerts/check` (preferred)
2. **Backend offline** → `scripts/morning_alert.py` reads DB directly

Run `scripts/install_task.ps1` elevated once if you rely on the Windows task.

## Known gaps

- `calibre-mcp` / `POST /api/v1/books/add_from_html` — confirm against real **calibre-mcp** HTTP surface before production archival.
- Gmail / Alpha Signal — confirm REST shapes against the actual integration you run.
- **No authentication** on the REST API by design for loopback / fleet LAN; do not expose **10946** to the public internet without a reverse proxy + auth.
- **`/api/items`** — capped list, no cursor pagination yet.
- **readly-mcp** — depends on readly-mcp REST on port **10863** and feature set available in your deployment.

## Roadmap (high level)

- **Near term:** `/api/items` pagination; optional auth for **`GET /api/env`**; digest caching where it saves LLM cost.
- **v0.3:** Readly article pipeline depth; trend analysis; portfolio watch list (see TODO / SPEC).
- **v0.4:** Calibre RAG over archives; digest feedback loop.

**Done since earlier PRD drafts:** parallel feed polling (`asyncio.gather` + semaphore), scheduler tests in tree, **`GET /api/env` value redaction**, live **`/api/capabilities`** tool enumeration.
