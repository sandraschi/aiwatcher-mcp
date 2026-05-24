# AGENTS.md — aiwatcher-mcp

Rules for AI coding agents (Claude, Cursor, Windsurf, Goose) working on this repo.

## Project Identity

- **Name**: aiwatcher-mcp
- **Purpose**: AI news ingestion, distillation, and alert system — FastMCP 3.2 fleet server
- **Owner**: Sandra Schipal, Vienna
- **Fleet role**: Central intelligence node — polls, scores, and alerts on AI news

## Architecture Quick Reference

```
FastMCP stdio server  <──>  Claude Desktop / MCP clients (python -m aiwatcher_mcp.server)
       │
Starlette :10946  <──>  React/Vite frontend :10947
  ├── REST /api/*
  └── MCP streamable HTTP at /mcp   (python -m aiwatcher_mcp.api)
       │
APScheduler (background jobs)
  ├── poll feeds every 30 min
  ├── distill items every 6h
  └── check alerts at 04:55 UTC
       │
SQLite (aiosqlite WAL)  ←  data/aiwatcher.db
       │
Fleet integrations (HTTP)
  ├── robofang  :10871  (breaking alerts)
  ├── speechops :10895  (TTS wake-up)
  ├── email-mcp :10812  (digest delivery)
  └── calibre-mcp :10720 (archival)
```

## Code Rules

### Python

- **Python 3.11+** — use `from __future__ import annotations`, `match/case`, `datetime(..., tzinfo=UTC)`
- **Async-first**: all I/O must be `async`/`await` — no blocking calls on the event loop
- **Type annotations**: all public functions must have full type hints
- **pydantic-settings**: all config via `Settings` in `config.py` — never `os.getenv()` elsewhere
- **Line length**: 100 chars (ruff enforces)
- **No global state** except `_settings` singleton in `config.py`
- **Logging**: use `logging.getLogger(__name__)` — never `print()` in production code

### Database

- All DB access via helpers in `database.py` — never raw SQL outside that module
- Use `async with get_db() as db:` pattern
- Always `await db.commit()` after writes
- Schema changes go in `SCHEMA` constant — re-runnable `CREATE TABLE IF NOT EXISTS`

### Error Handling

- Catch specific exceptions; log with context (item id, feed name, etc.)
- Never silently swallow errors
- Fleet integrations (robofang, speechops) must fail gracefully — log warning, don't crash

### Testing

- All tests in `tests/`
- Use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock external HTTP with `respx`
- Mock DB with in-memory aiosqlite (`:memory:` path)
- Test file: `tests/test_<module_name>.py`

## Forbidden Actions

- **Never commit** `.env`, `*.db`, `*.bak`, secrets of any kind
- **Never use ports** 3000, 5000, 5173, 8000, 8080 — fleet-reserved
- **Never call** `os.getenv()` outside `config.py`
- **Never block** the event loop with synchronous I/O
- **Never** install packages globally — use `uv add` to add to `pyproject.toml`
- **Never** import `anthropic` at module top level — lazy-import inside functions

## Workflow

Follow the **Explore → Plan → Implement → Commit** loop from fleet standards:

1. **Explore**: read affected files before touching anything
2. **Plan**: write a `SPEC.md` or inline plan for non-trivial changes
3. **Implement**: make changes, run `just lint && just test`
4. **Commit**: conventional commit message, no `.bak` files included

## Key Files

| File | Purpose |
|------|---------|
| `src/aiwatcher_mcp/config.py` | All settings — start here |
| `src/aiwatcher_mcp/database.py` | Schema + CRUD — modify carefully |
| `src/aiwatcher_mcp/server.py` | MCP tool registrations |
| `src/aiwatcher_mcp/api.py` | Starlette REST routes |
| `src/aiwatcher_mcp/distillation.py` | Claude scoring logic — Sandra's persona |
| `src/aiwatcher_mcp/scrubber.py` | Spam filter (regex blocklist + URL blocklist) — Layer 1 defense |
| `src/aiwatcher_mcp/ingestion.py` | RSS/Atom feed polling — scrubber wired here |
| `src/aiwatcher_mcp/gmail_ingestion.py` | Alpha Signal email ingestion — scrubber wired |
| `src/aiwatcher_mcp/arxiv_ingestion.py` | ArXiv paper ingestion — scrubber wired |
| `src/aiwatcher_mcp/readly_ingestion.py` | Readly magazine ingestion — scrubber wired |
| `src/aiwatcher_mcp/data/spam_blocklist.txt` | User-editable spam domain blocklist |
| `justfile` | All dev commands |
| `.env.example` | All available env vars |

## Adding a New MCP Tool

1. Implement async function in appropriate module (`ingestion.py`, `alerting.py`, etc.)
2. Register in `server.py` with `@mcp.tool()` decorator
3. Add entry to `manifest.json` `tools` array
4. Add test in `tests/test_server.py`
5. Document in `docs/API.md`

## Adding a New Feed Source

Use the `add_feed` MCP tool or insert directly:
```python
await db.execute(
    "INSERT OR IGNORE INTO feeds(name, url, feed_type) VALUES (?,?,?)",
    ("Feed Name", "https://example.com/rss", "rss")
)
```
