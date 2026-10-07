# TOOLS — aiwatcher-mcp (39 MCP tools, 2 prompts, 2 resources)

Registered in `src/aiwatcher_mcp/server.py`. Every tool returns a dict;
transport is stdio (`python -m aiwatcher_mcp.server`, proxies the HTTP daemon
when alive) or streamable HTTP at `:10946/mcp`.

## Pipeline

| Tool | Purpose |
|------|---------|
| `poll_feeds` | Poll all enabled RSS/Atom feeds |
| `distill_pending` | Score unprocessed items (relevance + urgency 0–10) |
| `check_alerts` | Fire robofang + TTS above threshold |
| `generate_digest` / `send_digest_now` | Build / force-send HTML+text digest |
| `expire_old_items` | Retention cleanup |
| `pipeline_liveness` | Fleet pipeline liveness |
| `scrubber_reload` | Reload spam/scrubber rules |
| `query_logs` | Backend log ring buffer |
| `aiwatcher_help` | Pipeline, keys, integrations, scoring docs |

## Items & search

| Tool | Purpose |
|------|---------|
| `get_top_items` | Top items by urgency (optional bundle filter) |
| `search_items` | FTS5 full-text search |
| `get_digest_history` | Persisted digests |
| `get_tag_trends` | Tag frequency trends |
| `inbox_add` / `inbox_scan` / `inbox_list` | Analysis inbox (opencode-elicited) |
| `opencode_briefing` | Briefing bundle for opencode sessions |
| `web_search` | Fleet OpenSERP lane |

## Feeds & bundles

| Tool | Purpose |
|------|---------|
| `get_feeds_list` / `add_feed` / `get_feed_health` | Feed CRUD + health |
| `find_feeds_for_topic` | Discover + verify feeds for a topic |
| `import_opml` | OPML import (Feedly, Inoreader) |
| `get_bundles_list` / `create_bundle_from_topic` / `link_feed_to_bundle` / `get_bundle_health` | Interest bundles |
| `list_fleet_bundles` / `update_fleet_bundle` | Fleet registry bundles |
| `ingest_fleet_event` | Record fleet-originated events |

## Source watchlists

| Tool | Purpose |
|------|---------|
| `poll_huggingface` / `hf_watchlist` | HF author watchlist + discovery/papers/models |
| `poll_hn` / `hn_watchlist` | HN front page + terms, GH star-velocity |
| `poll_readly` / `readly_watchlist` | Readly magazine pipeline |
| `currentai` | Current AI Stack Gap Map (refresh/diff/query/gap_report/check_dependency) |
| `show_dashboard_card` | Prefab UI fleet status card (`app=True`) |

## Prompts & resources

Prompts: `breaking_news_brief`, `portfolio_impact_analysis`.
Resources: `aiwatcher://feeds/list`, `aiwatcher://stats`.
REST index: `GET /api/capabilities`. Full HTTP list: `docs/API.md`.
