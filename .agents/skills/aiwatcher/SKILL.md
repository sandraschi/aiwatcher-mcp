---
name: aiwatcher
description: AI news ingestion, distillation, and alert session starter for aiwatcher-mcp.
---

## Session Context (aiwatcher-mcp)

You have AI news ingestion, distillation, and alert tools (poll_feeds,
get_top_items, distill_pending, generate_digest, check_alerts).

**Before starting work:**
1. Check recent news: get_top_items(hours=24, limit=10)
2. Review feed status: get_feeds_list()

**At end of work:**
- Run distill_pending() to score unprocessed items
- Note any configuration changes
