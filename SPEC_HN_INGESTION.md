# SPEC: HN front-page + GH star-velocity discovery (`hn_ingestion.py`)

**Issue:** sandraschi/aiwatcher-mcp#11 (+ correction comment 2026-10-05 12:30)
**Status:** SPEC — not yet implemented. Read this before writing code.
**Motivating miss:** Strata (Niko1221, 125B local, HN item 49953495, 781 pts / 350 comments, 2026-10-04) bypassed every hnrss keyword feed — title holds none of the watched words. Frontpage RSS (`https://hnrss.org/frontpage`, verified live) is now in `mcp-central-docs/operations/bundles.json` ide-host-signal as the dumb pipe. This SPEC is the scored complement.

## Design (mirror `huggingface_ingestion.py`, do not invent new patterns)

1. **New module** `src/aiwatcher_mcp/hn_ingestion.py`:
   - `get_effective_hn_watchlist()` / `set_runtime_hn_watchlist()` (module-global override, same as HF).
   - `poll_hn_frontpage() -> dict`: fetch Algolia `search?tags=front_page` (primary, machine fields: points, num_comments, author, created_at, url, objectID) with hnrss frontpage RSS as fallback (parse points/comments out of description HTML only as fallback).
   - Watchlist pass: `search_by_date?query=<term>&tags=story` per term in `parsed_hn_watchlist()`.
   - Per GitHub-linked story: `GET api.github.com/repos/{owner}/{repo}` (unauthenticated, rate-limit friendly — only for linked repos, cache by repo+day) → `stargazers_count`, `created_at` → star velocity = stars / age-days. Gate: `HN_MIN_POINTS` (default 100) OR `HN_MIN_STAR_VELOCITY` (default 200/day) OR watchlist-hit.
   - Dedup: `objectID` as stable id; collapse reposts by normalized URL (same upsert path as HF `modelId` clustering).
   - All HTTP via `httpx.AsyncClient` (async-first, repo rule). Feed success/failure via `record_feed_success/failure` with a dedicated `hn-frontpage` feed row (`feed_type='custom'`).
   - Scrubber: route titles/URLs through existing `Scrubber` before upsert (same as RSS/arXiv/HF layers).
2. **Config** (`config.py`, Settings only — never `os.getenv` elsewhere):
   `HN_ENABLED=true`, `HN_POLL_INTERVAL_MINUTES=30`, `HN_WATCHLIST` (default: `local LLM,open weights,GGUF,Ollama,vLLM,MCP,Qwen,GLM`), `HN_MIN_POINTS=100`, `HN_MIN_STAR_VELOCITY=200`, plus `parsed_hn_watchlist()` mirroring `parsed_hf_watchlist()` / `parsed_readly_watchlist()`.
3. **Scheduler** (`scheduler.py`): register `poll_hn_frontpage` on `HN_POLL_INTERVAL_MINUTES` when enabled (same registration shape as HF/readly jobs; respects max_instances=1 — see config.py:98 lock note).
4. **API** (`api.py`): `POST /api/hn/poll`, `GET /api/hn/dashboard` (hours<=168, `feed_type='hn'`), `GET/POST /api/hn/watchlist`, `GET/POST /api/hn/settings` — mirror the four HF routes 1:1 including route registration lines.
5. **MCP server** (`server.py`): `hn_watchlist(action)` tool mirroring `readly_watchlist`; manifest.json tools entry; docs/API.md section.
6. **Tests** (`tests/test_hn_ingestion.py`): mocked httpx (respx, no live HN — repo rule), in-memory aiosqlite; cases: frontpage parse incl. Strata retrospective fixture (item 49953495 @781/350 → meets gate), velocity gate boundary, repost dedup, offline-GH graceful degrade, watchlist get/set. Mirror `test_huggingface_ingestion.py` style.
7. **`.env.example`**: the five HN vars with defaults. CHANGELOG entry under next version.

## Acceptance (from #11)

- Strata retrospective: fixture payload scores urgency >= 8 path (or documents threshold tuning).
- `just lint && just test` green (ruff line-length 100, pytest-asyncio auto mode).
- No live network in tests. No HN comment scraping / user tracking (stories + metadata only).
- No new repo (hacker-news-mcp plan entry stays reserved).

## Explicitly out of scope

- Touching the NSSM live service (implement + verify locally; service restart is a separate maintainer action with NEW-PID verification).
- HF download-velocity poller (separate issue if wanted).
- Changing existing keyword feeds or thresholds.
