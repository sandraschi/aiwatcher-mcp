## Session Context (aiwatcher-mcp)

You have access to AI news ingestion, distillation, and alert tools.
Your awareness of configured feeds and alert thresholds persists across sessions.

**Before starting work:**
1. Check recent news: get_top_items(hours=24, limit=10)
2. Review feed status: get_feeds_list()

**At end of work:**
- Run distill_pending() to score any unprocessed items
- Note any configuration changes
