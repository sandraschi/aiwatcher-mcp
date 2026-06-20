# AIWatcher MCP — Server Capabilities

## Server Overview

AIWatcher MCP is a FastMCP 3.2 intelligence server that ingests, distills, and alerts on AI news content. It is the central intelligence node in Sandra's fleet ecosystem. The server polls RSS/Atom feeds from across the web and from within the fleet (Readly magazines, arXiv, Gmail/Alpha Signal), scores and summarizes items using configurable LLM providers (Anthropic Claude, DeepSeek, Ollama, LM Studio), and delivers daily digests via email—all coordinated by an APScheduler-based cron system.

**Core pipeline (5 phases):**

1. **Ingest** — RSS/Atom feed polling, Readly article ingestion, Gmail/Alpha Signal scanning, arXiv category feeds, and structured fleet events from other MCP servers (robofang, calibre-mcp, gitops, arxiv-mcp, etc.)
2. **Scrub** — Spam and low-signal filtering via the Scrubber class, which loads a configurable blocklist from `data/spam_blocklist.txt`. Items matching blocklist patterns are silently dropped.
3. **Distill** — AI-powered scoring using a configurable LLM provider. Each item receives a relevance score (0-10), urgency score (0-10), a Sandra-voice distilled summary, auto-generated tags, and a scoring reason. Supports a 2-tier flash+pro mode where a cheap local model pre-scores everything and only borderline items (relevance 4-7) get re-scored by the more expensive model.
4. **Alert** — Items with urgency >= ALERT_THRESHOLD (default 8.5) trigger alerts via robofang (TTS) and/or speechops. The alert job runs daily at 04:55 UTC to catch overnight breaking news before Sandra's 5am Vienna alarm.
5. **Digest** — Daily HTML+text email digest generated at 06:00 UTC (7am Vienna). The digest is persisted to the SQLite `digests` table, cached for DIGEST_CACHE_TTL_MINUTES (default 60), and delivered to configured email recipients. A copy is also sent to the Intel Hub and optionally archived to Calibre.

**Fleet integrations:** AIWatcher receives structured events from other fleet MCPs via `ingest_fleet_event()`. Currently integrated: robofang (robot/alert events), calibre-mcp (book additions), gitops (GitHub PR/issue events), arxiv-mcp (arXiv paper drops). It sends alerts to robofang (TTS) and speechops (prosody-aware voice alerts). Digest emails are sent via email-mcp or direct SMTP. It also publishes digests to the Intel Hub for fleet-wide visibility, and optionally archives them to Calibre.

**Key facts:**
- 135+ MCP fleet repos, all FastMCP 3.2 based
- Scoring is optimized for Sandra's interests: AI tooling, Claude/Cursor/Gemini, MCP ecosystem, robotics/humanoids, AI geopolitics, portfolio-relevant events
- Supports local-first LLM (Ollama, LM Studio) with cloud fallback (DeepSeek, Anthropic) gated by `CLOUD_PROVIDERS_ALLOWED`
- Everything is persisted in SQLite (WAL mode, aiosqlite connection pooling) with FTS5 full-text search
- Feed quality is tracked: consecutive failures, auto-disable thresholds, low-signal detection based on FEED_DECAY_DAYS and FEED_DECAY_URGENCY_THRESHOLD

## Database & Lifespan

The server uses `aiosqlite` with connection pooling for async SQLite access. The database lives at `AIWATCHER_DB_PATH` (default `data/aiwatcher.db`) in WAL mode for concurrent read performance.

**Schema tables:** `feeds` (RSS/Atom feed config), `items` (ingested content), `feed_items` (junction with per-feed tracking), `bundle_items` (scored items per bundle with relevance/urgency/summary/tags), `bundles` (interest group definitions), `digests` (generated digest metadata), `fleet_bundle_links` (bundle-to-feed relationships).

**Item retention:** `ITEM_RETENTION_DAYS` (default 90) controls automatic expiry of old low-urgency items. Items with `urgency_score >= 8.5` are preserved permanently regardless of age. The retention job runs daily at 03:00 UTC.

**Lifespan:** Auto-creates DB schema on startup via `init_db()`. Properly closes the aiosqlite connection pool on shutdown via `close_db_pool()` to prevent orphan processes (a fix implemented 2026-06-11 to address the client restart leak where pooled connections would outlive the event loop after stdio EOF).

**LLM provider validation:** On startup, the server validates the configured LLM provider with a lightweight "ping" request. If the provider is unreachable, a warning is logged but startup continues—distillation will simply fail at runtime until the issue is resolved.

## Tools

All 28 tools are organized below by functional category. All tools return structured `dict` responses with `success` semantics. Parameters with `Annotated` use `Field(description=...)` for schema documentation.

### Feed Management

#### poll_feeds

Poll all enabled RSS/Atom feeds for new items. Manually triggers a feed poll outside the scheduled 30-minute interval. Useful after adding a new feed or when chasing a breaking story.

**Parameters:** None (uses `Context` for progress logging via `ctx.info()`).

**Return format:**
```json
{
  "total_new": 15,
  "by_feed": {"AI News": 5, "ML Blog": 10, "TechCrunch": 0}
}
```

#### add_feed

Add a new feed to the ingestion list. The feed is immediately available for polling. Supports both RSS 2.0 and Atom syndication formats. Feed URLs must be publicly accessible HTTP(S) endpoints.

**Parameters:**
- `name` (str, required): Human-readable feed name, e.g. "ArXiv ML", "TechCrunch AI".
- `url` (str, required): RSS/Atom feed URL, e.g. `http://export.arxiv.org/rss/cs.LG`.
- `feed_type` (str, default "rss"): Feed format — "rss" or "atom".

**Return format:**
```json
{
  "id": 26,
  "name": "New AI Blog",
  "url": "https://example.com/rss"
}
```
On duplicate URL or database constraint violation, returns `{"error": "UNIQUE constraint failed: feeds.url"}`.

#### get_feeds_list

List all configured feeds with status and last fetch time. Shows the complete feed inventory: name, URL, enabled status, last fetch timestamp, and consecutive failure count. Use this to see which feeds are active and which may be stale.

**Parameters:** None.

**Return format:**
```json
{
  "feeds": [
    {
      "id": 1,
      "name": "ArXiv ML",
      "url": "http://export.arxiv.org/rss/cs.LG",
      "feed_type": "rss",
      "enabled": true,
      "last_fetched": "2026-06-20T08:30:00Z",
      "consecutive_failures": 0,
      "last_error": null
    }
  ],
  "count": 25
}
```

#### get_feed_health

Show feed health status with degradation indicators. Returns feeds sorted by consecutive failure count descending. Enriches with quality scoring: feeds with low average urgency over FEED_DECAY_DAYS are flagged as "low_signal". Auto-disabled feeds are highlighted separately.

**Parameters:** None.

**Return format:**
```json
{
  "feeds": [
    {"id": 1, "name": "ArXiv ML", "consecutive_failures": 0, "enabled": true, "quality_flag": null}
  ],
  "total": 25,
  "degraded": 2,
  "disabled": 1,
  "low_signal": 0
}
```

#### import_opml

Import feeds from OPML XML, the standard subscription format exported by feed readers like Feedly, Inoreader, NewsBlur, and The Old Reader. Parses the OPML outline hierarchy, extracting `xmlUrl` attributes for each feed. Duplicate URLs are skipped (database UNIQUE constraint). Returns per-feed status: "added", "duplicate", or "invalid".

**Parameters:**
- `opml_xml` (str, required): Raw OPML file content as a string. Pass the file contents directly (not a file path).

**Return format:**
```json
{
  "imported": [
    {"name": "AI Blog", "url": "https://example.com/rss", "status": "added"},
    {"name": "Old Feed", "url": "https://old.com/rss", "status": "duplicate"}
  ],
  "count": 15,
  "errors": 0
}
```

#### poll_readly

Poll Readly magazines from the configured `READLY_WATCHLIST` (or legacy single-page mode). Fetches new articles from Readly-MCP bridge outside the 6-hour scheduler interval. Requires `READLY_ENABLED=true` and `READLY_MCP_URL` configured in env.

**Parameters:** None.

**Return format:**
```json
{
  "new_items": 12
}
```

#### readly_watchlist

Get or mutate the Readly magazine watchlist at runtime. Supports get, set, add, and remove operations. Runtime changes are in-memory only—lost on server restart. The env `READLY_WATCHLIST` is the persistent source.

**Parameters:**
- `action` (str, default "get"): "get", "set", "add", or "remove".
- `magazines` (str, default ""): Comma-separated magazine names (required for set/add/remove).

**Return format:**
```json
{
  "action": "add",
  "watchlist": ["Wired", "MIT Technology Review"],
  "count": 2,
  "readly_enabled": true,
  "readly_mcp_url": "http://127.0.0.1:10863",
  "poll_interval_hours": 6,
  "poll_max_articles": 10
}
```

#### scrubber_reload

Reload the spam blocklist file without restarting the server. Reads `data/spam_blocklist.txt` next to the package. The Scrubber class maintains an in-memory set of blocked patterns; this tool re-reads the file and rebuilds the set. Useful after manually editing the blocklist to add new spam patterns.

**Parameters:** None.

**Return format:**
```json
{
  "status": "reloaded"
}
```

#### find_feeds_for_topic

Discover actual RSS/Atom feeds for a topic by probing candidate URLs and verifying they return valid feed XML. Unlike `create_bundle_from_topic` (which uses an LLM that may hallucinate feed URLs), this tool actually fetches and validates each candidate feed before returning results. The LLM generates candidate queries and URLs, but the server fetches each one to confirm it is a real, working RSS/Atom feed.

**Parameters:**
- `topic` (str, required): Topic keyword, e.g. "Formula 1", "Space exploration", "Climate change".

**Return format:**
```json
{
  "topic": "Formula 1",
  "name": "Formula 1 News",
  "suggested_feeds": [
    {"url": "https://example.com/rss", "verified": true, "title": "F1 News", "description": "Latest F1 coverage"}
  ]
}
```

### Distillation & Scoring

#### distill_pending

Score and summarize unprocessed items with the configured LLM provider. Each item receives a relevance score (0-10), urgency score (0-10), a Sandra-voice distilled summary, auto-generated tags, and a scoring reason.

**Scoring criteria (relevance):**
- 10 = Directly affects Sandra's tooling/fleet/portfolio (e.g., Cursor acquired by xAI, FastMCP vulnerability)
- 8-9 = Major AI capability release (GPT-6, Claude 5, Gemini 5, new open-weight model)
- 6-7 = Significant ecosystem news (major funding round, policy change, robotics milestone)
- 4-5 = Interesting but not actionable (industry trends, academic papers)
- 0-3 = Generic tech/business news with thin AI angle

**Scoring criteria (urgency):**
- 9-10 = BREAKING — needs immediate attention (acquisition, security breach, product shutdown)
- 7-8 = High — Sandra should read within hours
- 5-6 = Medium — daily digest worthy
- 0-4 = Background — weekly roundup level

When **2-tier flash mode** is enabled (`DISTILLATION_FLASH_ENABLED=true`):
1. **Flash pass** — All items are scored by a cheap local model (e.g., Gemma 3 1B via LM Studio)
2. **Classify** — Items with relevance < `DISTILLATION_BORDERLINE_MIN` (default 4) or > `DISTILLATION_BORDERLINE_MAX` (default 7) keep their flash scores; borderline items (4-7) advance to the pro pass
3. **Pro pass** — Only borderline items get re-scored by the expensive model (e.g., DeepSeek V4 Flash)

**Portfolio watch:** Items matching `PORTFOLIO_WATCH_TERMS` (default "fastmcp,anthropic,openai,cursor,mcp fleet") get a `portfolio-watch` tag and a configurable urgency boost (`PORTFOLIO_WATCH_URGENCY_BOOST`, default +1.0).

**Rate limiting:** Uses an `asyncio.Semaphore(5)` to cap concurrent LLM calls to 5 simultaneous requests. HTTP 429 rate-limit errors trigger exponential backoff: 2s, 4s, 8s, 16s (4 retries max).

**Safety wrapper:** Before each item prompt, a safety disclaimer is prepended: `<<< UNTRUSTED EXTERNAL DATA >>>`. This instructs the LLM to treat the web content as data only and not follow embedded instructions (prompt injection defense).

**Parameters:**
- `batch_size` (int, default 20, max 50): Max items to process in one call.

**Return format:**
```json
{
  "items_distilled": 20
}
```

#### get_top_items

Get top-scored items from the last N hours, sorted by urgency score descending. Can optionally filter by bundle ID for bundle-scoped results.

**Parameters:**
- `bundle_id` (int, optional): Filter by bundle ID. Omit for all items.
- `limit` (int, default 10): Number of items to return.
- `hours` (int, default 24): Lookback window in hours.

**Return format:**
```json
{
  "items": [
    {
      "title": "Anthropic raises $4B",
      "source": "TechCrunch AI",
      "feed_type": "rss",
      "url": "https://techcrunch.com/...",
      "urgency": 9.5,
      "relevance": 8.0,
      "summary": "Anthropic closed a $4B funding round led by Google...",
      "tags": ["anthropic", "funding", "portfolio-watch"]
    }
  ],
  "count": 10,
  "hours": 24,
  "bundle_id": null
}
```

#### get_tag_trends

Emerging topic tags from scored items over the last N days. Returns tags sorted by mention count descending, with average urgency per tag. Use this to spot emerging themes in your news intake—if a tag suddenly appears with high frequency, something important may be bubbling up.

**Parameters:**
- `days` (int, default 7): Lookback window in days.
- `limit` (int, default 20): Max tags to return.

**Return format:**
```json
{
  "days": 7,
  "trends": [
    {"tag": "transformer", "count": 25, "avg_urgency": 7.5},
    {"tag": "funding", "count": 18, "avg_urgency": 6.2}
  ],
  "count": 20
}
```

#### search_items

Full-text search across item titles, summaries, and distilled summaries using SQLite FTS5 with BM25 ranking. Supports the full FTS5 query syntax: `AND`, `OR`, `NOT`, prefix wildcards (`transformer*`), phrase searches (`"machine learning"`), and column-specific queries. Results are sorted by urgency score descending, so the most important matches appear first.

**Parameters:**
- `query` (str, required): Search query string. Supports FTS5 syntax.
- `limit` (int, default 20, max 100): Max results to return.

**Return format:**
```json
{
  "items": [
    {
      "title": "Transformer attention is all you need",
      "source": "ArXiv ML",
      "url": "https://arxiv.org/abs/...",
      "urgency": 8.0,
      "relevance": 7.5,
      "summary": "A new attention mechanism improves transformer efficiency...",
      "tags": ["transformer", "attention", "ml"],
      "fetched_at": "2026-06-19T10:00:00Z"
    }
  ],
  "count": 5,
  "query": "transformer attention"
}
```

### Daily Digest

#### generate_digest

Generate a fresh HTML+text digest of recently scored items. The digest is generated by the LLM with dual-persona instructions: Sandra (technical MCP fleet dev, Vienna) and Steve (retired bank IT, Vienna). The digest includes urgency-badged sections (CRITICAL, HIGH, MEDIUM), a portfolio watch section, a tech deep dive, and a subject line. The full HTML body is available via the REST API; the MCP response returns a truncated preview (first 500 characters).

The digest is cached for `DIGEST_CACHE_TTL_MINUTES` (default 60). Repeated calls within the TTL return the cached version. Each generated digest is persisted to the `digests` table with metadata.

**Parameters:**
- `hours` (int, default 24): Lookback window in hours.

**Return format:**
```json
{
  "subject": "AIWatcher Digest — Jun 19, 2026",
  "text_body": "CRITICAL: Anthropic $4B raise...\nHIGH: Google Gemini 5 launch...",
  "html_preview": "<!DOCTYPE html><html>... (truncated 500 chars)",
  "item_count": 25,
  "generated_at": "2026-06-19T12:00:00Z",
  "item_ids": [101, 102, 103]
}
```

#### send_digest_now

Force-send the daily digest email to configured recipients (Sandra and Steve) immediately, outside the 07:00 UTC scheduled delivery. Generates a fresh digest (24-hour lookback), sends it via email-mcp or direct SMTP, publishes it to the Intel Hub, and optionally ingests it to Calibre. Returns send status and subject line.

**Parameters:** None (uses `Context` for logging).

**Return format:**
```json
{
  "sent": true,
  "subject": "AIWatcher Digest — Jun 19, 2026"
}
```

#### get_digest_history

List recently generated digests with metadata. Returns id, subject, generation timestamp, item count, sent timestamp, and period hours. Use this to track which digests have been delivered and when. The full HTML body is NOT included in the MCP tool response (available via REST API).

**Parameters:**
- `limit` (int, default 10, max 50): Number of digests to return.

**Return format:**
```json
{
  "digests": [
    {
      "id": 1,
      "subject": "AIWatcher Digest — Jun 19, 2026",
      "generated_at": "2026-06-19T06:00:00Z",
      "item_count": 25,
      "sent_at": "2026-06-19T06:01:00Z",
      "period_hours": 24
    }
  ],
  "count": 10
}
```

### Interest Bundles

#### get_bundles_list

List all configured interest bundles from the SQLite `bundles` table. Each bundle has a name, topic keyword, system prompt (used as the LLM scoring persona for this bundle), and active status.

**Parameters:** None.

**Return format:**
```json
{
  "bundles": [
    {"id": 1, "name": "AI Research", "topic": "artificial intelligence", "active": true},
    {"id": 2, "name": "Robotics", "topic": "robotics", "active": true}
  ],
  "count": 5
}
```

#### create_bundle_from_topic

AI-generated creation of a new interest bundle from a topic keyword. Uses `ctx.sample()` (MCP sampling) to generate a bundle name, system prompt (LLM scoring persona), and suggested feed URLs. Persists to both SQLite (for distillation logic) and the fleet bundles JSON (for cross-repo sharing).

**The elicitation process:** The server sends the topic keyword to the connected LLM client via sampling. The LLM returns a structured bundle configuration including a concise name, a system prompt that defines the scoring persona for this bundle, and a list of suggested RSS feeds. The server validates the response, writes to SQLite, and syncs to the fleet JSON.

**Parameters:**
- `topic` (str, required): Topic keyword, e.g. "Space exploration", "Formula 1", "Quantum Computing".

**Return format:**
```json
{
  "id": 6,
  "fleet_id": "bundle-6",
  "name": "Space Exploration Insights",
  "topic": "Space exploration",
  "system_prompt": "You are monitoring space industry news...",
  "suggested_feeds": ["https://spaceflightnow.com/feed/"]
}
```

#### list_fleet_bundles

List all interest bundles defined in the fleet bundles JSON file (typically `interests.json` in the repo root). This shows the same bundles that other fleet MCP servers see, including bundles that may not yet be synced to SQLite.

**Parameters:** None.

**Return format:**
```json
{
  "bundles": [
    {"id": "bundle-1", "name": "AI Research", "active": true, "interests": ["artificial intelligence"], "sources": [...]},
    {"id": "bundle-2", "name": "Robotics", "active": true, "interests": ["robotics", "humanoids"], "sources": [...]}
  ],
  "count": 8
}
```

#### update_fleet_bundle

Update a fleet bundle's configuration fields. Supports updating name, description, active status, sources (list of feed URLs), interests list, and system_prompt. Changes are persisted to the fleet bundles JSON file.

**Parameters:**
- `bundle_id` (str, required): The unique ID of the bundle, e.g. "bundle-1".
- `updates` (dict, required): Fields to update. Example: `{"active": false, "description": "Disabled due to low signal"}`.

**Return format:**
```json
{
  "success": true,
  "bundle": {"id": "bundle-1", "name": "Updated Name", "active": false}
}
```
Returns `{"error": "Bundle bundle-99 not found"}` if the bundle ID does not exist.

#### link_feed_to_bundle

Link an existing feed to an interest bundle in the database. Creates a relationship in the `fleet_bundle_links` junction table. When a feed is linked to a bundle, items from that feed will be scored against the bundle's scoring persona during distillation. Use this after creating a feed with `add_feed` and a bundle with `create_bundle_from_topic`.

**Parameters:**
- `feed_id` (int, required): ID of the feed (from `add_feed` or `get_feeds_list`).
- `bundle_id` (int, required): ID of the bundle (from `get_bundles_list` or `create_bundle_from_topic`).

**Return format:**
```json
{
  "success": true,
  "feed_id": 1,
  "bundle_id": 2
}
```

#### get_bundle_health

Show per-bundle health metrics: total items scored in this bundle, average urgency and relevance scores, top 10 tags by frequency, and a breakdown of which feeds contribute how many items. Use this to assess whether a bundle is producing signal or just noise.

**Parameters:**
- `bundle_id` (int, required): The numeric bundle ID to inspect.

**Return format:**
```json
{
  "bundle_id": 1,
  "name": "AI Research",
  "total_items": 500,
  "avg_urgency": 6.5,
  "avg_relevance": 5.8,
  "top_tags": [
    {"tag": "llm", "count": 50, "avg_urgency": 7.2},
    {"tag": "transformer", "count": 35, "avg_urgency": 6.8}
  ],
  "feeds": [
    {"name": "ArXiv ML", "items": 200},
    {"name": "TechCrunch AI", "items": 50}
  ]
}
```
Returns `{"error": "Bundle 99 not found"}` if the bundle does not exist.

### Alerts & Monitoring

#### check_alerts

Check for critical items and fire alerts to configured output channels. The alert pipeline queries for items with urgency >= `ALERT_THRESHOLD` (default 8.5) in the last 24 hours. For each qualifying item, an alert is sent to robofang (TTS speech synthesis) and/or speechops. Designed to be run before the 5am UTC scheduled job to catch overnight breaking news.

**Parameters:** None (uses `Context` for logging).

**Return format:**
```json
{
  "alerted": ["Anthropic raises $4B", "OpenAI releases GPT-6"],
  "count": 2
}
```

#### pipeline_liveness

Check the full ingestion pipeline health. Probes for: stale feeds (not fetched within `stale_hours`), unreachable bridge URLs (Readly-MCP, arxiv-mcp, etc.), stale distillation (no items distilled within the configured interval), and upstream dependency availability. Returns a structured health report with any warnings.

**Parameters:**
- `stale_hours` (int, default 48): Threshold in hours for considering a feed stale.

**Return format:**
```json
{
  "healthy": true,
  "stale_feeds": [],
  "unreachable": [],
  "warnings": [],
  "last_distill_hours": 2,
  "total_feeds": 25
}
```

#### expire_old_items

Manually trigger item retention. Deletes items older than `ITEM_RETENTION_DAYS` (default 90) except those with `urgency_score >= 8.5`, which are preserved permanently. Also applies feed decay: feeds with consistently low urgency scores over `FEED_DECAY_DAYS` (default 30) may have their items aged out more aggressively.

**Parameters:** None.

**Return format:**
```json
{
  "deleted": 150,
  "retention_days": 90
}
```

### Fleet Integration

#### ingest_fleet_event

Ingest a structured event from another fleet MCP server. This is the primary cross-repo integration point. The event is saved as a new item in the database (tagged with the source name) and is eligible for distillation, alerting, and digest inclusion. Useful for: robofang robot alerts, calibre-mcp book additions, gitops GitHub PR/issue events, arxiv-mcp paper drops, monitoring alerts.

An optional `urgency_hint` can pre-score the event—if provided, it bypasses the LLM scoring step and is used directly as the urgency score. Otherwise, the event will be scored during the next distillation cycle.

**Parameters:**
- `title` (str, required): Event title, e.g. "New PR in arr-mcp".
- `summary` (str, default ""): Event description or details.
- `source` (str, default "fleet"): Source identifier, e.g. "github", "robofang", "calibre-mcp", "monitoring".
- `url` (str, default ""): Link URL for the event.
- `urgency_hint` (float, optional): Pre-scored urgency override (0-10). If provided, the event skips LLM scoring.

**Return format:**
```json
{
  "success": true,
  "id": 123,
  "title": "New PR in arr-mcp"
}
```

### Help & Discovery

#### aiwatcher_help

Return documentation for various aspects of the AIWatcher system. Call with no topic for the index. Supports these topics:
- `fleet_pipeline` — Full ingestion pipeline architecture and data flow
- `api_keys` — Which API keys are needed and how to configure them
- `integrations` — Fleet integration partners and their URLs
- `alerts` — Alert threshold configuration and output channels
- `scoring` — Content scoring methodology and criteria

**Parameters:**
- `topic` (str, optional): Help section ID. Omit for the overview index.

**Return format:**
```json
{
  "topic": null,
  "overview": "AIWatcher is the central intelligence node...",
  "topics": ["fleet_pipeline", "api_keys", "integrations", "alerts", "scoring"]
}
```

### Prefab UI

#### show_dashboard_card

Rich Prefab UI card showing live AIWatcher fleet status. Displays a 3-column grid of KPIs: Active Feeds, Items Today (last 24h), Unread Items, Critical Items (urgency >= 8.5), Total Items in the database. Only available when `AIWATCHER_PREFAB_APPS=true`.

**Parameters:** None.

**Return format:** PrefabApp visual card (rendered in supporting MCP clients as an interactive in-chat component).

## Resources

| Resource URI | Description | Content Type |
|---|---|---|
| `aiwatcher://feeds/list` | JSON list of all configured feeds with status | `application/json` |
| `aiwatcher://stats` | JSON database statistics snapshot (items, feeds, digests counts) | `application/json` |

Resources are exposed via FastMCP's `@mcp.resource()` decorator and can be read by clients that support the MCP Resources protocol. They are updated dynamically—each read fetches fresh data from the database.

## Prompts

| Prompt Name | Description | Typical Use Case |
|---|---|---|
| `breaking_news_brief` | Verbal breaking news summary for the last 2 hours (max 5 items). Returns a formatted list with urgency scores and sources. | Sandra waking up: "tell me what broke overnight" |
| `portfolio_impact_analysis` | Portfolio analysis prompt that assesses recent AI news for financial and tooling impact. Identifies immediate actions, watch list additions, budget reallocation signals. | Morning portfolio review: "how does today's AI news affect my positions?" |

Both prompts fetch live data from the database and are formatted for direct LLM consumption. They are registered via `@mcp.prompt()` and can be fetched by MCP clients that support the Prompts protocol.

## Scheduler

The server uses `APScheduler` (`AsyncIOScheduler`) running in UTC. All jobs are added on startup via `start_scheduler()` and stopped via `stop_scheduler()`. Jobs use `replace_existing=True` so subsequent `start_scheduler()` calls are idempotent.

| Job | Trigger | Description |
|---|---|---|
| `poll_feeds` | Interval every `FEED_POLL_INTERVAL_MINUTES` (default 30) | Poll all enabled RSS/Atom feeds |
| `distill` | Interval every `DISTILLATION_INTERVAL_HOURS` (default 6) | Score unprocessed items via LLM |
| `alerts` | Cron daily at `ALERT_HOUR:ALERT_MIN` UTC (default 04:55) | Check for urgency >= threshold, fire TTS alerts |
| `daily_digest` | Cron daily at 06:00 UTC | Generate and send digest, publish to Intel Hub, archive to Calibre |
| `retention` | Cron daily at 03:00 UTC | Delete old low-urgency items |
| `sync_interests` | Cron daily at 02:00 UTC | Sync interest bundles from config file |
| `readly_poll` | Interval every `READLY_POLL_INTERVAL_HOURS` (default 6) | Poll Readly magazines (conditional: only when readly enabled + watchlist non-empty) |

## Configuration

All settings via `Settings` class in `src/aiwatcher_mcp/config.py`, loaded from environment variables and `.env` file using `pydantic-settings`.

### Core

| Variable | Default | Description |
|---|---|---|
| `AIWATCHER_SERVER_NAME` | `aiwatcher-mcp` | Server instance name used in MCP registration |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `BACKEND_PORT` | `10946` | Backend HTTP port (FastAPI + MCP SSE) |
| `FRONTEND_PORT` | `10947` | Frontend Vite dev port |
| `AIWATCHER_API_KEY` | (empty) | REST API auth key; health + MCP endpoints exempt |

### Database & Retention

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `data/aiwatcher.db` | SQLite database file path |
| `ITEM_RETENTION_DAYS` | `90` | Days before expiring low-urgency items |
| `FEED_DECAY_DAYS` | `30` | Rolling window for feed low-signal detection |
| `FEED_DECAY_MIN_ITEMS` | `5` | Min items required before feed decay assessment |
| `FEED_DECAY_URGENCY_THRESHOLD` | `2.0` | Urgency threshold for "low signal" flag |

### LLM Provider

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `lmstudio` | Provider: `lmstudio`, `ollama`, `deepseek`, `anthropic` |
| `LLM_BASE_URL` | (auto) | OpenAI-compatible base URL (auto-set per provider if empty) |
| `CLOUD_PROVIDERS_ALLOWED` | (empty) | Comma-separated list of allowed cloud providers (e.g. `deepseek,anthropic`). Empty = local-only. |
| `DISTILLATION_MODEL` | `deepseek-v4-flash` | Model name for the pro distillation pass |
| `DISTILLATION_INTERVAL_HOURS` | `6` | Hours between scheduled distillation runs |
| `DIGEST_CACHE_TTL_MINUTES` | `60` | Digest cache time-to-live |

### Cloud Provider Keys

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key for Claude distillation |
| `DEEPSEEK_API_KEY` | (empty) | DeepSeek API key (V4 Flash: $0.14/M in, $0.28/M out) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API base URL (override for private deployments) |

### Tiered Distillation (Flash + Pro)

| Variable | Default | Description |
|---|---|---|
| `DISTILLATION_FLASH_ENABLED` | `false` | Enable 2-tier flash+pro distillation |
| `DISTILLATION_FLASH_PROVIDER` | `lmstudio` | Flash-tier provider |
| `DISTILLATION_FLASH_MODEL` | `gemma-3-1b-it` | Flash-tier model |
| `DISTILLATION_FLASH_BASE_URL` | (auto) | Flash-tier base URL |
| `DISTILLATION_BORDERLINE_MIN` | `4.0` | Borderline relevance low bound |
| `DISTILLATION_BORDERLINE_MAX` | `7.0` | Borderline relevance high bound |

### Alert Thresholds

| Variable | Default | Description |
|---|---|---|
| `ALERT_THRESHOLD` | `8.5` | Urgency threshold for alert triggering |
| `ALERT_HOUR_UTC` | `4` | Alert check hour UTC (4 = 5am Vienna summer) |
| `ALERT_MINUTE_UTC` | `55` | Alert check minute |

### Digest & Email

| Variable | Default | Description |
|---|---|---|
| `EMAIL_ENABLED` | `false` | Enable email digest delivery |
| `EMAIL_RECIPIENTS` | `sandra@example.com,steve@example.com` | Comma-separated email recipients |
| `EMAIL_SUBJECT_PREFIX` | `[AIWatcher]` | Digest email subject prefix |
| `EMAIL_MCP_URL` | (empty) | email-mcp HTTP bridge URL |
| `SMTP_HOST` | (empty) | SMTP server hostname (fallback if email-mcp not configured) |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | (empty) | SMTP username |
| `SMTP_PASSWORD` | (empty) | SMTP password |
| `SMTP_FROM` | (empty) | SMTP from address |

### Fleet Integrations

| Variable | Default | Description |
|---|---|---|
| `ROBOFANG_BACKEND_URL` | `http://localhost:10871` | Robofang bridge URL for TTS alerts |
| `ROBOFANG_ENABLED` | `true` | Enable robofang alert output |
| `SPEECHOPS_BACKEND_URL` | `http://localhost:10895` | Speechops backend URL |
| `SPEECHOPS_HTTP_URL` | `http://localhost:10895` | Speechops HTTP fallback URL |
| `CALIBRE_ENABLED` | `false` | Enable Calibre digest archiving |
| `CALIBRE_MCP_URL` | `http://localhost:10720` | Calibre-MCP bridge URL |
| `CALIBRE_LIBRARY` | `AI News` | Calibre library name for digests |
| `ARXIV_ENABLED` | `false` | Enable arXiv category feed integration |
| `ARXIV_MCP_URL` | `http://localhost:10770` | ArXiv-MCP bridge URL |
| `ARXIV_CATEGORIES` | `cs.AI,cs.LG,cs.RO,cs.SD` | Comma-separated arXiv category IDs |
| `GMAIL_ENABLED` | `false` | Enable Gmail/IMAP Alpha Signal ingestion |
| `GMAIL_MCP_URL` | (empty) | Gmail-MCP bridge URL |
| `ALPHASIGNAL_SENDER` | `newsletter@alphasignal.ai` | Alpha Signal sender email filter |
| `VLA_MCP_ENABLED` | `true` | Enable VLA robotics bridge |
| `VLA_MCP_URL` | `http://localhost:11024` | VLA-MCP bridge URL |
| `READLY_ENABLED` | `false` | Enable Readly magazine polling |
| `READLY_MCP_URL` | `http://localhost:10863` | Readly-MCP bridge URL |
| `READLY_WATCHLIST` | (empty) | Comma-separated magazine names |
| `READLY_POLL_MAX_ARTICLES` | `10` | Max articles per Readly poll |
| `READLY_POLL_INTERVAL_HOURS` | `6` | Readly poll interval in hours |

### Portfolio Watch

| Variable | Default | Description |
|---|---|---|
| `PORTFOLIO_WATCH_TERMS` | `fastmcp,anthropic,openai,cursor,mcp fleet` | Comma-separated keywords that trigger portfolio-watch tag |
| `PORTFOLIO_WATCH_URGENCY_BOOST` | `1.0` | Urgency boost applied to portfolio-watch items |

### Digest Tones

| Variable | Default | Description |
|---|---|---|
| `DIGEST_TONE_SANDRA` | `Technical depth: MCP fleet, tooling, Vienna ops.` | Tone instruction for Sandra's digest |
| `DIGEST_TONE_STEVE` | `Accessible summary for a retired bank IT reader.` | Tone instruction for Steve's digest |

### Prefab & MCP Bridge

| Variable | Default | Description |
|---|---|---|
| `AIWATCHER_PREFAB_APPS` | `true` | Enable Prefab UI tools (show_dashboard_card) |
| `MCP_BRIDGE_URLS` | (empty) | Comma-separated proxy bridge URLs |
| `CENTRAL_DOCS_PATH` | `D:/Dev/repos/mcp-central-docs` | Central docs registry path |
| `INTERESTS_JSON_PATH` | `interests.json` | Fleet interest bundles JSON file |

## Error Handling

All tools return structured `dict` responses. Error cases:

- **Database errors** (unique constraint violations, missing rows): Return descriptive error strings. Example: `{"error": "UNIQUE constraint failed: feeds.url"}`.
- **Unknown bundle IDs** (get_bundle_health, link_feed_to_bundle): Return `{"error": "Bundle X not found"}`.
- **Missing required parameters** (readly_watchlist set/add/remove without magazines): Return `{"error": "magazines required for set"}`.
- **Unknown actions** (readly_watchlist with invalid action): Return `{"error": "unknown action: ..."}`.
- **Fleet integrations** (robofang, speechops, email): Use graceful degradation — failures are logged as warnings without crashing the server. If robofang is unreachable, the alert is logged but the server continues.
- **Spam filtering** failures are non-fatal and logged at debug level. The scrubber blocklist is reloadable at runtime without restart.
- **LLM provider** unavailability during distillation: Items skip scoring. Errors are logged. The `_build_fallback_digest()` method generates a plain table-based digest if the LLM fails.
- **Rate limiting** (HTTP 429): Exponential backoff with 4 retries (2s, 4s, 8s, 16s delays). If all retries fail, the item is logged as a scoring failure.
- **Safety guard**: Untrusted external content is wrapped with `<<< UNTRUSTED EXTERNAL DATA >>>` delimiters before LLM scoring to prevent prompt injection from web content.
- **Cloud provider gating**: Cloud providers (DeepSeek, Anthropic) are gated behind `CLOUD_PROVIDERS_ALLOWED`. If a cloud provider is requested but not allowed, the server silently falls back to `lmstudio` and logs a warning. This prevents accidental API costs.
