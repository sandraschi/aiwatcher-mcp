# aiwatcher-mcp — TODO / Action Items

**Priority**: P0 (critical, must fix now) → P1 (should fix this sprint) → P2 (nice to have)

---

## v0.2.0 — Implemented 2026-04-29

- [x] **F1: Interest bundle health** (`get_bundle_health` MCP tool, `GET /api/bundles/{id}/health`, `get_bundle_stats()`)
- [x] **F2: Actual feed discovery** (`find_feeds_for_topic`, URL probing with `_verify_feed_url`, domain fallback path search)
- [x] **F3: Cross-feed near-dedup** (`_find_similar_item` with `difflib.SequenceMatcher` at 0.85 threshold, 48h window)
- [x] **F4: Stale feed fallback** (`_try_fallback_feed` on 404/410, auto-heals feed URL in DB)
- [x] **F5: OPML import** (`import_opml` MCP tool, `POST /api/opml/import`)
- [x] **Manifest / Glama / README tool lists** — refreshed 2026-05-24; authoritative runtime list is **`GET /api/capabilities`** (`tool_surface.atomic_tools`).

**Metrics:** 80+ pytest files in `tests/` (full `pytest tests` ~3 min including subprocess startup test); `uv run ruff check src/ tests/` expected clean.

---

## P0 — Critical (break production)

- [x] **Bundles.py missing imports**: Add `import logging` and `import json` to `src/aiwatcher_mcp/bundles.py`. Current code will crash on any bundle operation.
- [x] **Test distillation.py**: Add `from unittest.mock import MagicMock` to `tests/test_distillation.py` — fixes 3 failing tests.
- [ ] **Remove `.env` from git tracking**: Add `.env` to `.gitignore`. If it's already committed, `git rm --cached .env`. Never commit secrets.

---

## P1 — Should fix this sprint

### Code Fixes
- [x] **Fix all 54 ruff errors**: Run `ruff check --fix src/ tests/` (35 auto-fixable). Then manually fix the remaining 19 (F821 undefined names, B007 unused loop var, etc.)
- [x] **Remove duplicate imports in distillation.py**: `get_undistilled_bundle_items` and `update_bundle_item_scores` are imported at module level but never used there — the function body re-imports them. Clean up.
- [x] **Remove dead imports**: `hashlib`/`datetime` in `arxiv_ingestion.py`, `tempfile` in `conftest.py`, `os` in `test_alerting.py`, `json` in `test_api.py`, `pytest` in `test_startup.py`, `get_db` in `ingestion.py`, `Any` in `fleet.py`.
- [x] **Fix collapsed if-statements in api.py:236-237**: Split `if provider == "ollama": base_url = ...` onto separate lines.
- [x] **Modernize fleet.py typing**: Replace `typing.List` → `list`, `typing.Dict` → `dict`, `typing.Optional[X]` → `X | None`.

### Test Gaps (HIGH priority)
- [x] **Add `MagicMock` import** to `test_distillation.py` — already identified above.
- [x] **Add `test_gmail_ingestion.py`**: File exists under `tests/` (extend coverage as needed).
- [x] **Add `test_scheduler.py`**: File exists under `tests/` (extend coverage as needed).

### Repo Hygiene
- [ ] **Delete all 15 `.bak` files**: They're auto-generated backups from editing sessions. Shouldn't be in version control.
- [x] **Add `*.bak` to `.gitignore`**: Prevent future backup files from being committed. (already present at line 33)

### Security
- [x] **Spam scrubber (`scrubber.py`)**: 3-layer classifier (regex, URL blocklist, user blocklist) wired at all 4 ingest boundaries (RSS, Gmail, ArXiv, Readly). Spam items tagged `["spam"]`, excluded from distillation via `json_each` filter.
- [x] **Safety boundary wrapping**: `distillation.py::ITEM_PROMPT` now prepends `_SAFETY_WRAP` preamble to all untrusted item content before Claude sees it. Analogous to arxiv-mcp `wrap_untrusted()` pattern.
- [x] **Hot-reloadable blocklist**: `data/spam_blocklist.txt` + `scrubber_reload` MCP tool — no restart needed.
- [ ] **Add authentication (or remove) `GET /api/env`** — values are **redacted** since 2026-05-24; token/header auth still recommended if the API is exposed beyond loopback.
- [ ] **Verify `.env.example` doesn't contain real secrets** (it doesn't currently, but double-check).

---

## P2 — Should fix this sprint or next

### Performance
- [x] **Parallelize feed polling**: `poll_all_feeds()` uses `asyncio.gather` + `Semaphore(4)` (`ingestion.py`).
- [ ] **Add digest caching**: Cache generated digests in-memory (e.g., `{hours: result}` with TTL) to avoid repeat LLM calls for the same window.
- [ ] **Add DB connection pooling**: `get_db()` opens a new connection each time — consider a connection pool or at least a module-level connection cache.

### Features / Hardening
- [ ] **REST API pagination**: Add `offset` parameter to `/api/items` for cursor-style pagination.
- [ ] **Remove `sent_calibre` column**: `sent_calibre` in items table is populated but never checked in any query — dead field.
- [ ] **Add frontend health check**: `start.ps1` should verify the Vite dev server is actually responding before declaring success.
- [ ] **Add `sync_interests` to scheduler**: `update_interests.py` requires manual invocation — should run on startup or via a scheduler trigger.
- [ ] **Verify calibreops REST endpoint**: The endpoint `POST /api/v1/books/add_from_html` in `calibre_integration.py` is speculative — confirm against actual calibre-mcp server.
- [x] **Add `from __future__ import annotations`** to all files that lack it: auto-fixed by ruff.

### Test Coverage (medium priority)
- [ ] **Add `test_arxiv_ingestion.py`**: Mock arxiv-mcp HTTP responses.
- [ ] **Add `test_calibre_integration.py`**: Test `ingest_digest_to_calibre` with mocked HTTP.
- [ ] **Add `test_bundles.py`**: Test `elicit_bundle_config`, `load_fleet_bundles`, `save_fleet_bundles`.
- [ ] **Add `test_email_delivery.py`**: Test SMTP and email-mcp paths with mocked transports.
- [ ] **Add `test_fleet.py`**: Test `discover_fleet_from_docs` with mock registry files.
- [ ] **Add `test_logging_utils.py`**: Test `UIHandler` and `get_logs()`.

---

## P3 — Backlog / Future

- [ ] **readly-mcp integration**: Spec written in `SPEC_0.2.md` F6 — blocked on readly-mcp needing article-listing tool
- [ ] **Trend analysis**: Track score patterns over time, surface emerging topics (PRD v0.3)
- [ ] **Portfolio watch list**: Explicit ticker/company list triggers instant alert (PRD v0.3)
- [ ] **Per-user digest profiles**: Different depth/tone for Sandra vs Steve (PRD v0.2)
- [ ] **Gmail OAuth direct**: bypass email-mcp for Alpha Signal ingestion (PRD v0.2)
- [ ] **Calibre RAG**: Ask questions over archived digests via semantic search (PRD v0.4)
- [ ] **API rate limiting**: Protect against accidental or malicious abuse
- [ ] **Prometheus metrics**: Export for fleet monitoring

---

## Summary Count

| Status | Count |
|--------|-------|
| Completed | 14 |
| Remaining | 20 |
| **Total** | **34** |
