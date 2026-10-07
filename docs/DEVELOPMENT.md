# DEVELOPMENT — aiwatcher-mcp

## Prereqs

Python 3.11+, `uv` (`C:\Users\sandr\.local\bin\uv.exe`), Node (webapp),
`just` (installed by `start.ps1` via winget on naked PCs).

## Setup

```powershell
copy .env.example .env
just install     # uv sync --group dev + pre-commit install + webapp npm ci
just check       # smoke-test import
just serve       # full stack via start.ps1 (backend :10946, frontend :10947)
```

Or per-lane: `just backend` (Starlette debug), `just frontend` (Vite),
`just mcp` (stdio server for Claude Desktop testing).

## Gates (run before every commit)

```powershell
just gates-green   # ruff check + ruff format --check + pyright src/ + pytest -q
```

Webapp: `npm run check` (tsc --noEmit), `npm run biome:ci` from `webapp/`.
E2E: `just e2e` (Playwright, backend :10946 + Vite :10947).
Full MCPB: `just mcpb-pack` (`just pack` is an alias) — wipe + fresh-copy
`src/` → `mcpb/src/`, import/AST/pollution checks, 3-4-100 prompt report,
pack + unpack launch check. Never hand-edit `mcpb/src/`.

## Layout

- `src/aiwatcher_mcp/server.py` — FastMCP tools/prompts/resources/Prefab card
- `src/aiwatcher_mcp/api.py` — FastAPI app (`app`), REST routes, `/mcp` mount
- `src/aiwatcher_mcp/config.py` — ALL settings (add Fields here, nowhere else)
- `src/aiwatcher_mcp/database.py` — schema + CRUD (only raw-SQL module)
- `src/aiwatcher_mcp/ingestion.py`, `hn_ingestion.py`, `huggingface_ingestion.py`, `arxiv_ingestion.py`, `gmail_ingestion.py`, `readly_ingestion.py`, `wikipedia_ingestion.py` — sources
- `src/aiwatcher_mcp/distillation.py` — LLM scoring (lazy-import cloud SDKs)
- `src/aiwatcher_mcp/scheduler.py` — APScheduler jobs (poll 30m, distill 6h, alerts 04:55 UTC)
- `src/aiwatcher_mcp/skills/aiwatcher-expert/SKILL.md` — chat preprompt source
- `webapp/src/` — React + Vite + Tailwind + Zustand; same-origin `/api` (vite proxy),
  absolute backend URL only behind the Tauri gate (`utils/api.ts`)
- `tests/` — pytest-asyncio (auto mode), respx for HTTP, in-memory aiosqlite for DB

## Conventions

Line length 100, `from __future__ import annotations`, `datetime(..., tzinfo=UTC)`,
`logging.getLogger(__name__)` (no `print()` — ruff T20 enforced), DB via
`async with get_db()`, `await db.commit()` after writes, schema changes in `SCHEMA`.
New MCP tool: implement in domain module → register `@mcp.tool()` in `server.py` →
add to `manifest.json` + `mcpb/manifest.json` + `glama.json` tool lists → test →
document in `docs/TOOLS.md`.
