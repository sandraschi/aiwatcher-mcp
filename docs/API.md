# aiwatcher-mcp API Reference

This document outlines the FastMCP 3.2 tools, prompts, resources, and standard endpoints provided by the `aiwatcher-mcp` server.

## MCP Tools

### `poll_feeds()`
Force a manual poll of all active RSS/Atom feeds outside the normal schedule.
- **Returns:** `{ total_new: int, by_feed: dict }`

### `distill_pending(batch_size: int = 20)`
Run the Claude distillation process on unprocessed items. 
- **Parameters:**
  - `batch_size`: Max items to process in this run (max 50).
- **Returns:** `{ items_distilled: int }`

### `check_alerts()`
Manually trigger the alert evaluation pipeline to check if any scored items breach the urgency threshold and require dispatching to robofang/speechops.
- **Returns:** `{ alerted: list[str], count: int }`

### `generate_digest(hours: int = 24)`
Generates a fresh HTML digest for the specified lookback window.
- **Parameters:**
  - `hours`: The lookback window in hours.
- **Returns:** `{ subject: str, html_preview: str, text_body: str }`

### `send_digest_now()`
Forces the delivery of the daily digest email immediately via `email-mcp` or SMTP fallback.
- **Returns:** `{ sent: bool, subject: str }`

### `get_top_items(limit: int = 10, hours: int = 24)`
Fetch the highest-scored items within a timeframe.
- **Parameters:**
  - `limit`: Number of results.
  - `hours`: Timeframe lookback.
- **Returns:** `{ items: list[dict], count: int, hours: int }`

### `get_feeds_list()`
Returns a list of all configured ingestion sources.
- **Returns:** `{ feeds: list[dict], count: int }`

### `add_feed(name: str, url: str, feed_type: str = "rss")`
Dynamically register a new feed to track.
- **Returns:** `{ id: int, name: str, url: str }` or `{ error: str }`

### `show_dashboard_card()`
*(Prefab UI App Tool)* Renders an interactive fleet status widget directly inside Claude Desktop.

---

## MCP Prompts

### `breaking_news_brief()`
Generates a quick conversational brief of any high-urgency items from the last 2 hours. Intended for TTS readouts.

### `portfolio_impact_analysis()`
A specialized prompt that injects the last 24 hours of top items and asks the LLM to assess immediate impacts on AI stocks, software subscriptions, and infrastructure decisions.

---

## MCP Resources

- **`aiwatcher://feeds/list`**: Read-only JSON list of all configured feeds and their statuses.
- **`aiwatcher://stats`**: Read-only JSON summary of current fleet statistics (total items, critical count, unread).
