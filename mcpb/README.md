# aiwatcher-mcp (MCPB Bundle)

AI news ingestion, distillation, and alert system — FastMCP 3.2 fleet server

## Usage

Add to \claude_desktop_config.json\:
\\\json
{
  "mcpServers": {
    "aiwatcher-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "\D:\Dev\repos", "python", "-m", "aiwatcher_mcp"],
      "env": { "PYTHONPATH": "\D:\Dev\repos/src" }
    }
  }
}
\\\

## Tools

- **poll_feeds**: poll_feeds
- **distill_pending**: distill_pending
- **check_alerts**: check_alerts
- **generate_digest**: generate_digest
- **send_digest_now**: send_digest_now
- **get_bundles_list**: get_bundles_list
- **create_bundle_from_topic**: create_bundle_from_topic
- **list_fleet_bundles**: list_fleet_bundles
- **update_fleet_bundle**: update_fleet_bundle
- **link_feed_to_bundle**: link_feed_to_bundle
- **get_top_items**: get_top_items
- **get_feeds_list**: get_feeds_list
- **search_items**: search_items
- **get_digest_history**: get_digest_history
- **expire_old_items**: expire_old_items
- **get_feed_health**: get_feed_health
- **get_tag_trends**: get_tag_trends
- **pipeline_liveness**: pipeline_liveness
- **ingest_fleet_event**: ingest_fleet_event
- **add_feed**: add_feed
- **get_bundle_health**: get_bundle_health
- **find_feeds_for_topic**: find_feeds_for_topic
- **poll_readly**: poll_readly
- **readly_watchlist**: readly_watchlist
- **import_opml**: import_opml
- **scrubber_reload**: scrubber_reload
- **aiwatcher_help**: aiwatcher_help
- **show_dashboard_card**: show_dashboard_card

## Requirements

- Python 3.12+
- uv
