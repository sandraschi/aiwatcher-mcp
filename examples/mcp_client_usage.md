# Calling aiwatcher-mcp from MCP Clients

## Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aiwatcher-mcp": {
      "command": "C:\\Users\\sandr\\.local\\bin\\uv.exe",
      "args": ["run", "python", "-m", "aiwatcher_mcp.server"],
      "cwd": "D:\\Dev\\repos\\aiwatcher-mcp"
    }
  }
}
```

## Available Tools

| Tool | Description | Key args |
|------|-------------|----------|
| `poll_feeds` | Poll all enabled feeds for new items | — |
| `distill_pending` | Score undistilled items with Claude | `batch_size` (default 20) |
| `check_alerts` | Fire robofang + TTS for critical items | — |
| `generate_digest` | Build HTML+text digest | `hours` (default 24) |
| `send_digest_now` | Force-send digest email | — |
| `get_top_items` | Top-scored items | `hours`, `limit` |
| `get_feeds_list` | List all configured feeds | — |
| `add_feed` | Add a new feed | `name`, `url`, `feed_type` |

## Example Conversation

```
User: What are the top AI news items from the last 48 hours?

Claude: [calls get_top_items with hours=48, limit=10]
        Returns a ranked list with urgency/relevance scores and Sandra-voice summaries.
```

```
User: Add the Hugging Face blog to my feeds.

Claude: [calls add_feed with name="Hugging Face Blog",
         url="https://huggingface.co/blog/feed.xml", feed_type="rss"]
        Feed added. Call poll_feeds to fetch items immediately.
```

## Calling via HTTP (REST API)

The Starlette backend on `:10946` exposes the same operations as REST endpoints:

```powershell
# Health check
Invoke-RestMethod http://localhost:10946/api/health

# Get top items
Invoke-RestMethod "http://localhost:10946/api/items?hours=24&limit=10"

# Get feeds list
Invoke-RestMethod http://localhost:10946/api/feeds

# Manually trigger poll (POST)
Invoke-RestMethod -Method POST http://localhost:10946/api/poll
```

See [docs/API.md](../docs/API.md) for the full REST API reference.
