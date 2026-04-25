# Changelog — aiwatcher-mcp

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
