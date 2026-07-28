# IDE Host Signal bundle

Fleet-maintained **IDE Host Signal** interest bundle — see also [mcp-central-docs/patterns/AIWATCHER_IDE_HOST_SIGNAL.md](https://github.com/sandraschi/mcp-central-docs/blob/main/patterns/AIWATCHER_IDE_HOST_SIGNAL.md).

## Code

- Feeds + distillation prompt: `src/aiwatcher_mcp/bundle_presets.py`
- Idempotent apply: `ensure_fleet_bundle_presets()` in `database.py` (runs on startup)

## Feeds (10)

Reddit r/cursor, r/CursorAI; HN cursor MCP/IDE, Zed, Windsurf; Google News; Cursor forum; Zed + opencode release atoms.

## Scoring

Bundle-specific system prompt prioritizes **host UX**, **MCP approval**, **changelog-gap** tags. Alert threshold **8.0** (vs default 8.5).

## Ops

Restart backend after upgrade → open Bundles in webapp (:10947) → confirm feeds linked → `poll_feeds` → `distill_pending`.
