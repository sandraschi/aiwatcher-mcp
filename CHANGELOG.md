
## [Unreleased] — 2026-07-29

### Added
- `web_search` tool — search web via OpenSERP for live context during distillation
- `OPENSERP_URL` config (default `http://127.0.0.1:7000`)

## [Unreleased] — 2026-07-05

### Added
- **Current AI Stack Gap Map integration** — `currentai` portmanteau tool
  - `src/aiwatcher_mcp/currentai/` module: fetcher, store, differ, watchlist
  - `currentai(operation="refresh")` — fetch upstream YAML, store versioned snapshots
  - `currentai(operation="diff")` — compare snapshots, detect added/removed/reclassified/changed
  - `currentai(operation="query")` — lookup products by name or stack layer
  - `currentai(operation="gap_report")` — per-layer openness class breakdown
  - `currentai(operation="check_dependency")` — fleet watchlist concentration risk
  - Watchlist: `data/currentai/watchlist.json` with 11 fleet-critical entries
  - Snapshot storage: `data/currentai/snapshots/{date}_{commit}.json` + `latest.json`
  - Reconnaissance doc: `docs/CURRENTAI_RECON.md`
  - Tests: 17 unit tests covering differ, store, watchlist, gap report
### Added (pre-existing)
- Tauri 2.0 native wrapper with `bundle.resources` + `std::process::Command`
- PyInstaller frozen backend embedded in NSIS installer
- CUA-NSIS smoke test (`scripts/cua-smoke.py`, `scripts/cua-nsis-config.json`)
- `just cua-nsis-test` recipe
- Tauri CORS: `tauri://localhost` origins for WebView API access
- `GET /api/v1/diagnostics` endpoint for CUA verification
# Changelog

All notable changes to **aiwatcher-mcp** are documented here.

## [0.1.8] — 2026-06-07

### Added
- **Intel Reports Hub client** — `intel_hub_client.py` publishes daily digest HTML to fleet hub (`:11027`)
- **`scripts/ensure-intel-hub.ps1`** — start hub if down before digest send
- **Digest → hub** — scheduler `daily_digest` and `POST /api/digest/send` include `intel_hub` publish result

### Integration
- [fleet-agent-mcp](https://github.com/sandraschi/fleet-agent-mcp) — Fritz auto-ingests Pulse/Day Prep via `POST /api/fleet/ingest`
- MCD: [patterns/intel-reports-hub](https://github.com/sandraschi/mcp-central-docs/blob/main/patterns/intel-reports-hub.md)

### Documentation
- README, API.md, PRD, help_content, HelpPage — Intel Hub publish path documented

---

## [0.1.7] — 2026-06-05

### Added
- **Pipeline liveness** (`pipeline_liveness.py`, `GET /api/pipeline/liveness`) — detects stale arXiv pull loops, wrong `ARXIV_MCP_URL` port (**10719** vs fleet **10770**), and upstream arxiv-mcp health.
- **Webapp `PipelineHealthCard`** — dashboard surface for pipeline probes (arxiv / fleet ingest).
- **`docs/FLEET_PIPELINE.md`** — producer contract for `POST /api/fleet/ingest`, API-key matrix, interest bundles, readly poll path.

### Fleet integration (P5 / P2 gap closure)
- **WF-001 `morning_brief`** — `fleet-agent-mcp` workflow step calls `get_top_items` (glance → aiwatcher → vienna-life → memops).
- **`mcp-test-suite` golden tier** — `aiwatcher-mcp` in `core` smoke list (health + registry trust layer).
- **`fleet-registry.json`** — active entry on **10946** / **10947** after 2026-06-05 merge (143-ship catalog).
- **Readly longform routing** — Fritz `intel_briefing` uses relevance threshold for `feed_type=readly` items (pairs with readly-mcp + arxiv code-hunt media lane).

### Documentation
- Cross-links to `mcp-central-docs/operations/planning/` (fleet gap roadmap, FLEET_NAMING ViLife vs vla-robotics).

---

## [0.1.6] — 2026-06-03

### Added
- **Fritz / fleet integration**: `aiwatcher` in `fleet-agent-mcp` `FLEET_SERVERS`; Office Day Prep calls `get_top_items` and creates pulse tasks for urgency ≥ 8.0.
- **Federation hub**: `aiwatcher-mcp` entry in `mcp-federation-hub/federation-config.json` (ports **10946** / **10947**).
- **Baseline feeds**: `scripts/seed_feeds.py` + `just seed-feeds`.
- **Digest cache**: `DIGEST_CACHE_TTL_MINUTES` skips repeat LLM digest generation when a recent digest exists.
- **SQLite pooling**: shared `aiosqlite` connection with `close_db_pool()` for tests.
- **Scheduler**: daily `sync_interests` job (02:00 UTC, `INTERESTS_JSON_PATH`).
- **Prometheus**: `GET /metrics` text exposition (`aiwatcher_*` gauges).
- **Feed quality decay**: `quality_flag` on `/api/feeds/health` and `get_feed_health` (`healthy` / `low_signal` / `insufficient_data`).
- **Semantic-lite dedup**: cross-feed match uses title **and** title+summary (`difflib`, 85%, 48h).
- **Fleet events**: MCP `ingest_fleet_event` + `fleet://` feed for bidirectional fleet journal items.
- **Trends**: MCP `get_tag_trends` + `GET /api/trends`.
- **Portfolio watch**: `PORTFOLIO_WATCH_TERMS` boosts urgency on keyword hits during distillation.
- **Per-recipient digest tone**: `DIGEST_TONE_SANDRA` / `DIGEST_TONE_STEVE` in digest LLM prompt.
- **Tests**: arxiv, calibre, bundles, email, fleet, logging, digest cache, P4 feature tests (**100+** pytest targets).
- **Playwright e2e**: `webapp/playwright.config.ts`, `webapp/e2e/*.spec.ts`, `just e2e` (ports **10946**/**10947**); fleet audit moved to `just e2e-fleet-audit`.

### Changed
- **Health contract**: `/health` and `/api/health` include `items_total`, `items_last_24h`, `last_poll_at`, `scheduler_running`.
- **`/api/env`**: non-loopback access requires `AIWATCHER_API_KEY` (loopback still allowed without a key).
- **Calibre ingest**: `POST {CALIBRE_MCP_URL}/api/books/` with temp `.html` (matches calibre-mcp webapp).
- **`sent_calibre`**: set on digest items after successful Calibre ingest.
- **`start.ps1`**: fails if Vite is not healthy within 60s (no longer warn-only).
- **Default `ARXIV_MCP_URL`**: **10770** (arxiv-mcp backend).
- **Package version**: **0.1.6** (`pyproject.toml`, `_version.py`, `server_version`).

### Documentation
- **PRD**, **API.md**, **ARCHITECTURE.md**, **README.md**, **ASSESSMENT.md**, **TODO.md** aligned with shipped behavior and v0.3/v0.4 roadmap.

### Deferred (documented in PRD)
- **readly-mcp** article pipeline (blocked on upstream `list_current_issue_articles`).
- **Calibre RAG** over archived digests (v0.4).
- Full embedding-based semantic dedup (current: fuzzy title+summary).

---

## [0.1.5] — 2026-05-24

### Added
- **Optional REST auth**: set `AIWATCHER_API_KEY`; middleware accepts `X-AIWatcher-Key` or `Authorization: Bearer` on `/api/*` (`/health`, `/mcp` exempt).
- **`/api/items` pagination**: `offset`, `limit` (max 200), and `has_more` in the JSON response.
- **Shared OPML import**: `aiwatcher_mcp.opml.import_feeds_from_opml` used by MCP tool and REST.
- **`start.ps1`**: polls Vite on the frontend port before declaring the stack ready.

### Changed
- **MCP HTTP lifespan** nested under Starlette again; **`init_db()`** is idempotent to avoid WAL double-init hangs.
- **CI**: `pytest -m "not slow"`; **`test_backend_only_startup`** marked `@pytest.mark.slow` and Windows-only.

### Fixed
- **`api_auth`**: compare provided key to settings value (not a missing `self.api_key`).
- **`server.import_opml`**: delegates to shared OPML helper; scrubber docstring no longer hardcodes a machine path.

---

## [0.1.4] — 2026-05-24

### Security
- **`GET /api/env`**: responses are passed through **`redact_env_dict()`** so typical secret env names and `sk-` / `Bearer ` values are returned as **`***REDACTED***`**, not cleartext.

### Changed
- **`/api/capabilities`**: `tool_surface` is built from **`await mcp.list_tools()`** so tool names and counts stay accurate as the server grows (including optional bridge tools when configured).
- **`/api/health`**: **`version`** comes from **`cfg.server_version`** instead of a hard-coded string.
- **`Settings.speechops_backend_url`**: default now **`http://localhost:10895`** (speechops), not this service’s own backend port.
- **`justfile`**: **`REPO := justfile_directory()`**, **`UV := env_var_or_default("UV_EXE", "uv")`**, sibling path for the Playwright audit script; **`poll` / `distill` / `alerts` / `scrubber-reload` / `stats`** use **`Invoke-RestMethod`** with correct HTTP methods and routes (PowerShell shell).

### Documentation
- **`README.md`**, **`INSTALL.md`**, **`ASSESSMENT.md`**, **`examples/README.md`**, **`manifest.json`**, **`glama.json`**: refreshed for current commands, ports, and tool surface.

### Fixed
- **`tests/test_startup.py`**: use **`Process.net_connections()`** instead of deprecated **`connections()`** (removes thousands of `DeprecationWarning`s on Windows).

---

## [0.1.3] — 2026-04-27

### Added
- **Interest Bundles**:
    - Custom AI "Personas" that filter global news feeds through specific niche lenses (e.g. "Dogs", "Yachts", "Travel").
    - Bundle-specific scoring for Relevance and Urgency.
    - Dedicated "Bundles" page in the UI for managing personas and viewing filtered insights.
- **AI-Driven Source Elicitation**:
    - "Bundle Wizard" that takes a simple topic and generates a comprehensive Persona (System Prompt).
    - AI-suggested high-quality RSS/Atom feeds and blogs for new topics.
    - One-click adding and linking of suggested sources to the new bundle.
- **Bundle Feed Management**:
    - Ability to link/unlink global feeds to specific bundles.
    - Visual indicators for source connectivity.

## [0.1.2] — 2026-04-26

### Added
- **Industrialized `start.ps1`**:
    - `-Headless`: Re-launches the script in a hidden window using `Start-Process pwsh -WindowStyle Hidden`.
    - `-BackendOnly`: Starts the Python backend without the Vite frontend (essential for integration testing).
    - `-NoBrowser`: Prevents the script from automatically opening the browser.
- **`SKIP_SYNC` Environment Variable**: Support for bypassing `uv sync` to avoid file-lock errors during automated testing.
- **Integration Tests**: Added `tests/test_startup.py` to verify backend/frontend port availability and headless behavior.

## [0.1.1] — 2026-04-25

### Fixed

**Backend startup hang (health-check timeout race)**
- Root cause: `api.py` lifespan nested `async with http_app.router.lifespan_context(http_app)`,
  which ran FastMCP's `_mcp_db_lifespan` (calling `init_db()`), then the Starlette lifespan
  immediately called `init_db()` a second time. The competing aiosqlite WAL locks caused the
  lifespan to never yield — uvicorn bound the port (causing `test_port` to return reachable)
  but Starlette kept returning 503 on all routes. Health-check polled for 90 s then bailed.
- Fix: removed the nested FastMCP lifespan context from `api.py`. FastMCP manages its own
  internals; Starlette lifespan now owns DB init + scheduler start/stop only, once.

**Frontend never started**
- Root cause: `start.ps1` used `cmd.exe /c "$npmForCmd"` with a hand-rolled double-quote
  escape. `cmd.exe /c "path\npm.cmd" run dev` interprets the quoted first token as a window
  title and discards the remaining args — npm process exited immediately, port 10947 never
  opened, browser poller spun indefinitely.
- Fix: replaced with `Start-Process -FilePath $npmCmd -ArgumentList "run", "dev"`.

**Health-check timeout too tight**
- `Invoke-WebRequest -TimeoutSec 2` on a local uvicorn that takes ~2.4 s to respond caused
  every poll to throw a timeout exception. The loop ran all 90 iterations and reported
  "backend did not start" even though it had.
- Fix: bumped health-check timeout to 5 s.

**Startup error visibility**
- Backend errors were invisible (spawned in a detached window, no log).
- Fix: `start.ps1` now redirects backend stdout+stderr to `backend.log`; on health-check
  timeout it tails the last 30 lines before exiting.

---

## [0.1.0] — 2026-04-24 (initial)

- FastMCP 3.2 server: `poll_feeds`, `distill_pending`, `check_alerts`, `generate_digest`,
  `send_digest_now`, `get_top_items`, `get_feeds_list`, `add_feed`, `show_dashboard_card`
- Starlette REST backend on :10946, Vite/React frontend on :10947, MCP HTTP at /mcp
- APScheduler: poll every 30 min, distill every 6 h, alert check at 04:55 UTC, daily digest
- 10 default AI news feeds seeded on first run
- Fleet integrations: robofang (:10871), speechops (:10895), email-mcp (:10812),
  calibre-mcp (:10720), Gmail MCP
- `start.bat` / `start.ps1`: zero-dependency launcher (winget installs uv + Node if absent)
