# aiwatcher-mcp — Assessment & TODO

**Date:** 2026-05-24  
**Assessed by:** Cursor / fleet maintenance pass  
**Supersedes:** ASSESSMENT.md (2026-05-01)  
**Version:** `0.1.0` in `pyproject.toml` and `src/aiwatcher_mcp/_version.py` (release marketing may still say “v0.2” for the feature bundle — align naming when you tag).  
**FastMCP:** 3.2.x (`fastmcp>=3.2.0` in pyproject)

---

## What It Is

AI news ingestion, distillation, and alerting — a fleet “situational awareness” node. Polls RSS/Atom plus optional Gmail, arXiv, and Readly; scores with Claude or OpenAI-compatible local providers; delivers digests and cross-fleet alerts (robofang, speechops). **Dual surface:** `python -m aiwatcher_mcp.server` (stdio MCP for clients) and **`python -m aiwatcher_mcp.api`** (Starlette on **10946** with REST + **HTTP MCP at `/mcp`**) plus Vite on **10947**.

---

## Current Status: Production-capable

- **Tests:** 80+ pytest targets across `tests/` (including `test_startup.py` subprocess smoke); run `pytest tests` for full signal. `test_backend_only_startup` is intentionally slow (~2 min).
- **Lint:** Ruff configured; keep `uv run ruff check src/ tests/` green before merge.
- **Docs / metadata:** README, INSTALL, CHANGELOG, `manifest.json`, and `glama.json` refreshed 2026-05-24 for commands, security behavior, and tool lists.

---

## Architecture (summary)

```
APScheduler (jobs)
  ├── poll_all_feeds      (interval)
  ├── distill_items       (interval)
  ├── process_alerts      (cron, UTC)
  ├── daily digest        (cron)
  └── retention / expiry  (cron)

Ingestion: RSS/Atom, optional Gmail, arXiv, Readly (feature-flagged)
Distillation: per-item + bundles; Anthropic | Ollama | LM Studio (OpenAI-compat)
Storage: SQLite (+ FTS where used), WAL; dedup and feed health logic in codebase
```

---

## What’s Solid

- **Async-first** Starlette + httpx patterns; settings centralized in **`pydantic-settings`**.
- **Feed resilience:** failure counters, fallbacks, and discovery helpers (`find_feeds_for_topic`, OPML).
- **`/api/capabilities`** now reflects **live** MCP tool registration (`list_tools`), so UIs and fleet registries are not stuck on stale counts.
- **`GET /api/env`** returns **redacted** values for secret-shaped keys (still no auth — see P2).
- **`fleet.py`** discovers related services from fleet doc registries instead of hardcoding every port.
- **`start.ps1`:** headless / backend-only / npm path resolution / optional `SKIP_SYNC`.

---

## Issues

### P1 — Should fix

**`GET /api/env` still has no authentication**  
Values are **redacted**, but anyone who can reach the backend can still read **keys** and non-secret values. For internet-exposed deployments, add auth (API key header, mTLS, or remove the route and use file edit only).

**`.env` accidentally committed**  
If `.env` ever lands in git history, rotate keys. `.gitignore` includes `.env`; verify with `git check-ignore -v .env` and `git ls-files .env` (should be empty).

**Tracked `*.bak` files**  
If any remain tracked, `git rm --cached` them; `*.bak` is ignored for new files.

### P2 — Should fix soon

- **Pagination** on high-volume list endpoints (e.g. `/api/items`) beyond a fixed cap.
- **Deduplicate OPML import** between `server.py` and `api.py` into one helper.
- **`sent_calibre` (or similar) schema noise:** either wire it into queries or drop it in a migration.
- **Singletons** (`_settings`, scheduler, semaphores): acceptable single-worker; document “no multi-worker uvicorn” or refactor for workers.

### P3 — Backlog

- Broader integration tests for optional sources (Readly, arXiv edge cases, calibre) where not already covered.
- **`manifest.json` `icon`:** points at `assets/icon.png`; ship a real icon or adjust path for MCP bundle packers.
- **Optional:** mark `test_backend_only_startup` as `@pytest.mark.slow` and exclude from default CI.

---

## Resolved since 2026-05-01 assessment

| Item | Resolution |
|------|------------|
| `GET /api/env` cleartext secrets | **`redact_env_dict()`** masks sensitive names and `sk-` / Bearer values. |
| Hardcoded `/api/capabilities` tool list | Built from **`mcp.list_tools()`**. |
| `speechops_backend_url` default on wrong port | Default aligned to **10895**. |
| `validate_distillation_model` / Anthropic | Already **skips** network ping when **`ANTHROPIC_API_KEY`** is unset (anthropic branch returns early). |
| Hardcoded machine paths in `justfile` | **`justfile_directory()`** + **`UV_EXE`** env override. |
| Broken `just` HTTP one-liners (`curl` + `; \` under PowerShell) | **`Invoke-RestMethod`** recipes with correct routes. |
| psutil deprecation spam in startup test | **`net_connections()`** instead of **`connections()`**. |

---

## TODO (rolling)

- [ ] **P1** Gate or authenticate **`GET /api/env`** for any non-loopback deployment.
- [ ] **P1** Confirm **`.env`** is not tracked; rotate if it was ever committed.
- [ ] **P2** Cursor / offset pagination for **`/api/items`** (and similar list APIs).
- [ ] **P2** Single shared **OPML** import implementation.
- [ ] **P3** **`@pytest.mark.slow`** + CI profile excluding subprocess startup test by default.
- [ ] **P3** Real **`assets/icon.png`** (or manifest tweak) for `.mcpb` packaging.

---

## Test layout (2026-05-24)

| File | Focus |
|------|--------|
| `test_api.py` | REST + capabilities + env redaction |
| `test_server.py` | MCP / server surface |
| `test_database.py`, `test_ingestion.py`, `test_distillation.py`, `test_alerting.py`, `test_scheduler.py` | Core pipelines |
| `test_gmail_ingestion.py` | Gmail path |
| `test_startup.py` | Full `start.ps1` / port integration (slow) |
