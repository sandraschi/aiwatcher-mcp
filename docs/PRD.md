# aiwatcher-mcp — Product Requirements Document

**Status**: ACTIVE — v0.2.0 shipped
**Version**: 0.2.0
**Owner**: Sandra Schipal
**Ports**: 10946 (backend) / 10947 (frontend)

---

## Problem

Sandra needs to stay on top of fast-moving AI news without spending time on
manual feed triage. Critical events (acquisitions, model releases, security
incidents affecting her tooling) must reach her immediately, even at 5am.
Brother Steve also wants a readable weekly/daily AI digest without needing
to set up any tooling himself.

## Solution

Automated ingestion pipeline: 13+ RSS feeds + Alpha Signal + ArXiv + Readly →
Claude scoring with interest bundles → prioritised news feed → daily HTML
digest email (Sandra + Steve) → TTS wake-up for critical events.

## Integrations

| System | Status | Notes |
|---|---|---|
| RSS/Atom feeds | Implemented | 13 default feeds seeded |
| Alpha Signal (Gmail) | Config required | `GMAIL_ENABLED=true` + `GMAIL_MCP_URL` |
| ArXiv papers | Config required | `ARXIV_ENABLED=true` + `ARXIV_MCP_URL` |
| Readly magazines | Config required | `READLY_ENABLED=true` + `READLY_MCP_URL` |
| OPML import | Implemented | `import_opml` MCP tool |
| Claude distillation | Config required | `ANTHROPIC_API_KEY` (supports Ollama/LM Studio too) |
| Interest bundles | Implemented | Per-topic distillation, feed discovery, bundle health |
| Cross-feed dedup | Implemented | 85% title similarity, 48h window |
| Feed URL auto-heal | Implemented | Fallback path probing on 404/410 |
| robofang alerts | Config required | `ROBOFANG_ENABLED=true` (default) |
| speechops TTS | Config required | `SPEECHOPS_HTTP_URL` |
| email-mcp digest | Config required | `EMAIL_ENABLED=true` |
| calibre-mcp archive | Config required | `CALIBRE_ENABLED=true` |
| Windows Scheduled Task | Manual setup | `scripts/install_task.ps1` |

## Scheduled Task Architecture

The 5am alert has two paths:

1. **Backend running** → `POST /api/alerts/check` (preferred)
2. **Backend offline** → `scripts/morning_alert.py` reads DB directly

This means the alert fires reliably even if the MCP server or Claude Desktop
is not running at 5am. Run `scripts/install_task.ps1` as Administrator once.

## Known Gaps (v0.2.0)

- `calibre-mcp` endpoint `POST /api/v1/books/add_from_html` is speculative —
  will need to verify against the actual calibreops REST surface and adjust.
- Gmail MCP REST API shape assumed from email-mcp conventions — confirm against
  the actual email-mcp server before enabling.
- No authentication on the REST API (fleet-internal only, not exposed externally).
- No pagination on `/api/items` beyond the limit parameter.
- readly-mcp integration requires readly-mcp v0.2.0+ (REST REST API on port 10863).

## Roadmap

- v0.2.0 Rest: `scheduler.py` unit tests, parallel feed polling, digest caching
- v0.3: readly-mcp article extraction pipeline (requires readly-mcp browser session management)
- v0.3: Trend analysis — track score patterns over time, surface emerging topics
- v0.3: Portfolio watch list — explicit ticker/company list triggers instant alert
- v0.4: Calibre RAG integration — ask questions over archived digests
- v0.4: Email reply-to-digest feedback loop for scoring adjustment
