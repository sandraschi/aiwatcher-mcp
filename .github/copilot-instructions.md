# aiwatcher-mcp — Copilot instructions

AI news ingestion, distillation, and alert system (FastMCP fleet server,
Starlette backend :10946, React webapp :10947).

## Session Context (aiwatcher-mcp)

You have AI news ingestion, distillation, and alert tools (poll_feeds,
get_top_items, distill_pending, generate_digest, check_alerts).

**Before starting work:**
1. Check recent news: get_top_items(hours=24, limit=10)
2. Review feed status: get_feeds_list()

**At end of work:**
- Run distill_pending() to score unprocessed items
- Note any configuration changes

## Repo rules (see AGENTS.md)

- Python 3.11+, async-first, full type hints, line length 100 (ruff).
- All config via `Settings` in `src/aiwatcher_mcp/config.py` — never `os.getenv()` elsewhere.
- Logging via `logging.getLogger(__name__)` — never `print()` in production code.
- Never commit `.env`, `*.db`, `*.bak`, or secrets.
