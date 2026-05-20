# aiwatcher-mcp — Assessment & TODO

**Date:** 2026-05-01  
**Assessed by:** Claude (Sonnet 4.6)  
**Supersedes:** previous ASSESSMENT.md (opencode, 2026-04-29)  
**Version at assessment:** 0.1.0 (pyproject) / 0.2.0 (ASSESSMENT/TODO)  
**FastMCP:** 3.2.x (pyproject pin ≥3.2.0)

---

## What It Is

AI news ingestion, distillation, and alerting system — a personal intelligence feed for Sandra and Steve. Polls RSS/Atom feeds + arXiv + Gmail (Alpha Signal) + Readly magazines, scores items with Claude (or local LLMs), fires TTS wake-ups via speechops for urgency ≥ 8.5, and delivers a daily HTML digest by email. Dual-transport: FastMCP MCP server + Starlette REST backend on port 10946, Vite/React frontend on 10947.

---

## Strategic Context

This is the fleet's situational awareness layer. With 135+ repos and fast-moving AI tooling, staying on top of what matters (Cursor updates, Claude capability changes, DeepSeek releases, MCP ecosystem moves) is genuinely time-consuming. aiwatcher-mcp compresses that to a daily digest + voice interrupts for breaking items.

The multi-provider distillation design (Anthropic / Ollama / LM Studio) is intentional: use Claude for high-fidelity scoring when needed, but the pipeline can run entirely local on Goliath with Qwen3.5 27B at ~40 tok/s for routine ingestion. This makes it cheap to run continuously.

Interest bundles are the key design win — different scoring personas mean Sandra's AI infra feed and Steve's more general tech digest can share the same ingestion pipeline but get independently tuned summaries.

---

## Current Status: Production-Capable

The opencode assessment (2026-04-29) is accurate and thorough — all P0/P1 code bugs resolved, 55 tests passing, ruff clean. What follows covers remaining gaps and adds strategic framing.

---

## Architecture

```
APScheduler (5 jobs)
  ├── poll_all_feeds()     — every 30m, parallelised (asyncio.Semaphore(4))
  ├── distill_items()      — every 6h, Claude/local LLM scoring
  ├── process_alerts()     — 04:55 UTC, robofang + speechops TTS
  ├── generate_digest()    — 06:00 UTC, email to Sandra + Steve
  └── expire_old_items()   — 03:00 UTC, retention cleanup

Ingestion sources
  ├── RSS/Atom (feedparser)
  ├── arXiv (arxiv-mcp REST)
  ├── Gmail Alpha Signal (gmail-mcp)
  └── Readly magazines (readly-mcp)

Distillation
  ├── Per-item: relevance + urgency (0-10) + Sandra-voice summary + tags
  ├── Per-bundle: same pipeline with bundle-specific system prompt
  └── Providers: Anthropic | Ollama | LM Studio (OpenAI-compat)

Alerting
  ├── robofang Council bridge (POST /api/v1/events)
  ├── speechops TTS HTTP (POST /api/v1/tts)
  └── Windows SAPI5 fallback (asyncio subprocess, correct)

Storage: SQLite + FTS5 (BM25), WAL journal, cross-feed dedup (difflib 0.85/48h)
```

---

## What's Good

**Code quality is high.** `from __future__ import annotations` throughout, async-first, no blocking I/O on the event loop, `pydantic-settings` single config class, proper graceful degradation on all integrations.

**Feed resilience is well-thought-out.** `consecutive_failures` counter + auto-disable + `_try_fallback_feed()` on 404/410 with domain path probing — this handles the real-world problem of feeds moving without notice.

**`poll_all_feeds()` is correctly parallelised** with `asyncio.gather` + `Semaphore(4)`. The previous sequential version (noted in TODO as P2) is already fixed — the current code does concurrent polling. TODO.md is stale on this point.

**Distillation semaphore + exponential backoff** on 429s is correct. `_strip_fences()` for local model JSON wrapping is practical. Fallback digest builder when LLM is unavailable is sensible.

**`api.py` hot-reload endpoint** (`POST /api/config/reload`) resets the `_settings` singleton without restart. Useful for tuning thresholds live.

**`fleet.py`** reads from `webapp-registry.json` and `fleet-registry.json` at runtime rather than hardcoding — contrast with opencode-cli-mcp's hardcoded port list. This is the right pattern.

---

## Issues

### P1 — Should Fix

**`.env` in git tracking (SECURITY — CRITICAL)**  
`.env` file is in the working tree and possibly tracked. If committed, `ANTHROPIC_API_KEY` and SMTP credentials are in git history. Run `git rm --cached .env` immediately if not already done. `.gitignore` has `*.env` but not `.env` specifically — verify.

**`GET /api/env` returns secrets in cleartext**  
`api_get_env()` reads `.env` and returns it as JSON — including `ANTHROPIC_API_KEY`, `SMTP_PASSWORD`, etc. No authentication guard. Fleet-internal is not a sufficient excuse for this; a misconfigured browser proxy or XSS in the frontend would expose all credentials. At minimum add a `?redact=1` mode that masks key-pattern values, or remove the endpoint entirely and use `POST /api/env` write-only.

**`/api/capabilities` tool count is hardcoded as 11**  
The server has 20 tools registered (counting `get_bundle_health`, `find_feeds_for_topic`, `import_opml`, `show_dashboard_card`, etc.). The `total: 11` and `atomic_tools` list in `capabilities()` are stale from an earlier version. Not critical but misleading for anything consuming the capabilities endpoint.

**15 `.bak` files still committed**  
Carried over from previous assessment. `*.bak` is in `.gitignore` but the existing ones are already tracked. `git rm --cached *.bak` across the tree.

### P2 — Should Fix Soon

**Global singleton pattern for `_settings`, `_scheduler`, `_DISTILL_SEMAPHORE`**  
Three module-level singletons initialised lazily. Fine for single-process deployment, fragile under any test parallelism or multi-worker uvicorn. The scheduler singleton in particular is `None`-guarded but not thread-safe. In practice, `reload=False` in uvicorn and single-worker keeps this safe.

**No pagination on `/api/items`**  
High-urgency items accumulate. 200-item cap in the route handler is a hard stop, not cursor pagination. For long-running deployments with 90-day retention this will become a problem.

**`sent_calibre` column is dead**  
Populated during ingestion/digest but never queried. Adds noise to the schema. Remove or wire up.

**`opml_import` code is duplicated**  
The OPML import XML-parsing logic is copy-pasted identically between `server.py` (`import_opml` tool) and `api.py` (`api_opml_import`). Should be a single function in `ingestion.py` or `bundles.py`.

### P3 — Backlog

**Missing test coverage** (per existing TODO.md): `test_gmail_ingestion`, `test_arxiv_ingestion`, `test_calibre_integration`, `test_bundles`, `test_email_delivery`, `test_fleet`, `test_readly_ingestion`.

**`speechops_backend_url` config default is wrong**  
`Settings.speechops_backend_url` defaults to `http://localhost:10946` — that's aiwatcher's own port, not speechops. Should be speechops backend port (10895 per `speechops_http_url`). The `speechops_http_url` field is what's actually used in `alerting.py`, so this is dormant but confusing.

**`validate_distillation_model()` fires a real API call on every startup**  
A 1-token `ping` to Anthropic on every boot. Fine in production but will burn tokens (and possibly fail) in dev/CI environments where the key isn't set. Should be gated on `cfg.anthropic_api_key` being non-empty before attempting.

---

## TODO (fresh, consolidated)

- [ ] **P1-SEC** `git rm --cached .env` — verify not tracked
- [ ] **P1-SEC** Redact or remove `GET /api/env` — never return raw secrets over HTTP
- [ ] **P1** Fix `/api/capabilities` tool count (11 → 20, update tool list)
- [ ] **P1** `git rm --cached` the 15 `.bak` files
- [ ] **P2** Add cursor pagination to `/api/items` (offset/limit)
- [ ] **P2** Remove `sent_calibre` dead column
- [ ] **P2** Deduplicate OPML import logic (server.py + api.py → shared function)
- [ ] **P2** Fix `speechops_backend_url` default (currently points at own port)
- [ ] **P2** Gate `validate_distillation_model()` on key being present
- [ ] **P3** Add missing test files (gmail, arxiv, calibre, bundles, email, fleet, readly)
- [ ] **P3** `start.ps1` frontend health check (verify Vite responding before declaring success)

---

## What's Already Done (from previous TODO.md)

Per opencode's 2026-04-29 pass — all P0 bugs, all 54 ruff errors, dedup, OPML, bundle health, feed discovery, fallback URL healing, parallel polling, test isolation fixes. 55 tests passing.
