# AIWatcher MCP — User Guide

## Quick Start

### Prerequisites

- Python 3.11+ and `uv` (Astral's package manager)
- An LLM provider for distillation: LM Studio (local, default), Ollama (local), DeepSeek API (cloud, $0.14/M tokens), or Anthropic API (cloud, quality-critical)
- Optional: email-mcp or SMTP credentials for digest email delivery
- Optional: robofang-mcp for TTS alerts
- Optional: Readly-MCP bridge for magazine article ingestion

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sandraschi/aiwatcher-mcp.git
   cd aiwatcher-mcp
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```
   This creates a virtual environment with all dependencies: fastmcp, aiosqlite, APScheduler, openai (for Ollama/LM Studio/DeepSeek), anthropic (for Claude), httpx, feedparser (for RSS/Atom), and prefab-ui (for dashboard cards).

3. **Create a `.env` file:**
   ```env
   LOG_LEVEL=INFO
   DB_PATH=data/aiwatcher.db
   LLM_PROVIDER=lmstudio
   LLM_BASE_URL=http://localhost:1234/v1
   DISTILLATION_MODEL=gemma-3-1b-it

   # Optional: enable cloud providers (requires API key)
   # CLOUD_PROVIDERS_ALLOWED=deepseek
   # DEEPSEEK_API_KEY=sk-ds-...
   # ANTHROPIC_API_KEY=sk-ant-...

   # Optional: email delivery
   # EMAIL_ENABLED=true
   # EMAIL_RECIPIENTS=sandra@example.com,steve@example.com
   # SMTP_HOST=smtp.gmail.com
   # SMTP_USER=your-email@gmail.com
   # SMTP_PASSWORD=app-password
   # SMTP_FROM=aiwatcher@example.com
   ```

4. **Initialize the database:**
   The server auto-creates the database schema on first startup. No manual migration steps needed.

5. **Run the server:**
   ```bash
   uv run run_server.py
   ```
   This starts the MCP stdio server (for Claude Desktop, Cursor, Windsurf). For HTTP mode:
   ```bash
   uv run python -m aiwatcher_mcp.api
   ```
   The HTTP server starts on port 10946 with both REST API and MCP SSE endpoints.

6. **Add to Claude Desktop:**
   ```json
   {
     "mcpServers": {
       "aiwatcher-mcp": {
         "command": "uv",
         "args": ["run", "--directory", "C:\\path\\to\\aiwatcher-mcp", "run_server.py"]
       }
     }
   }
   ```

7. **Add your first feeds:**
   Use `add_feed()` to add RSS/Atom feeds, then `poll_feeds()` to start the ingestion pipeline. Feeds are automatically polled every 30 minutes by the scheduler, but you can trigger an immediate poll at any time.

## Tutorials

### Tutorial 1: Check Your Morning Digest

Start your day by checking what was delivered in the latest digest, or generate a fresh preview.

```python
# See what digests have been generated recently
history = get_digest_history(limit=5)
for digest in history['digests']:
    sent = digest.get('sent_at', 'not sent yet')
    print(f"[{digest['generated_at']}] {digest['subject']}")
    print(f"  {digest['item_count']} items | sent: {sent}")

# Generate a fresh preview without sending
digest = generate_digest(hours=24)
print(f"Subject: {digest['subject']}")
print(f"Items: {digest['item_count']}")
print(f"Preview: {digest['text_body'][:300]}...")

# If you like it, send it immediately
result = send_digest_now()
print(f"Sent: {result['sent']} — {result.get('subject', '')}")
```

**What happens:** The server queries the SQLite database for scored items from the last 24 hours, sends them to the LLM for digest composition with dual-persona instructions (Sandra: technical fleet dev; Steve: retired bank IT), and returns a formatted HTML+text digest.

### Tutorial 2: Add a New RSS Feed

Add a new RSS feed to your monitoring list and trigger an immediate poll to ingest its content.

```python
# Add a feed
feed = add_feed(
    name="VentureBeat AI",
    url="https://venturebeat.com/category/ai/feed/",
    feed_type="rss"
)
print(f"Added feed ID: {feed['id']}")

# Manually poll all feeds to ingest immediately
result = poll_feeds()
print(f"New items: {result['total_new']}")
for feed_name, count in result['by_feed'].items():
    print(f"  {feed_name}: {count} new items")
```

**Tips:**
- Use `feed_type="atom"` for Atom feeds (the server handles both formats transparently)
- After adding multiple feeds, call `poll_feeds()` once — it polls all feeds in sequence
- Check `get_feeds_list()` to see if your feed was added correctly

### Tutorial 3: Create an Interest Bundle for AI Research

Interest bundles are named groups with their own scoring persona. Create one for a specific research area.

```python
# Create a bundle for quantum computing research
bundle = create_bundle_from_topic(topic="Quantum Computing")
print(f"Bundle '{bundle['name']}' created (ID: {bundle['id']})")
print(f"System prompt: {bundle['system_prompt']}")
print(f"Suggested feeds: {bundle['suggested_feeds']}")

# Add the suggested feeds
for feed_url in bundle['suggested_feeds']:
    feed = add_feed(
        name=f"Quantum - {feed_url.split('/')[2]}",
        url=feed_url,
        feed_type="rss"
    )
    print(f"  Added feed: {feed['name']}")

# Link feeds to the bundle
# After adding feeds, link them to the bundle for scoring
link_feed_to_bundle(feed_id=feed['id'], bundle_id=bundle['id'])

# Verify the bundle was created
bundles = get_bundles_list()
print(f"Total bundles: {bundles['count']}")
```

**How sampling works:** The `create_bundle_from_topic` tool uses MCP sampling to call back to the connected LLM (Claude in Desktop, or your configured provider). The LLM generates a bundle name, a system prompt defining the scoring persona, and a list of suggested RSS feed URLs. This is why the bundle appears "AI-elicited."

### Tutorial 4: Score Unprocessed Items with the LLM

Manually trigger the distillation pipeline to score and summarize unprocessed items outside the scheduled 6-hour interval.

```python
# Before distilling, check what's pending by looking at top items
# (if empty, items haven't been scored yet)
top = get_top_items(limit=5, hours=48)
if top['count'] == 0:
    print("No scored items yet — running distillation...")

# Run distillation (default batch size: 20 items)
result = distill_pending(batch_size=20)
print(f"Distilled {result['items_distilled']} items")

# Now check the scored items
top = get_top_items(limit=10, hours=24)
print(f"\nTop 10 items (sorted by urgency):")
for item in top['items']:
    urgency_display = "!" * int(item['urgency'] // 2)
    print(f"  [{item['urgency']}/10] {urgency_display} {item['title']}")
    print(f"    Source: {item['source']} | Tags: {', '.join(item['tags'])}")
    print(f"    Summary: {item['summary'][:120]}...")
```

**What the LLM does:** For each item, the LLM receives the title, source, URL, and content text (first 2000 chars). It returns a JSON object with relevance_score (0-10), urgency_score (0-10), tags (3-6 keywords), a distilled summary in Sandra's technical voice, and a reason explaining the scores. Items matching portfolio watch terms get a `portfolio-watch` tag and an urgency boost.

### Tutorial 5: Find Feeds About a Specific Topic

Discover real, validated RSS feeds for any topic. This tool actually fetches and validates each candidate feed URL — unlike `create_bundle_from_topic`, which may hallucinate feed URLs.

```python
feeds = find_feeds_for_topic(topic="Formula 1")
print(f"Bundle name: {feeds['name']}")
print(f"\nSuggested feeds ({len(feeds['suggested_feeds'])} found):")
for feed in feeds['suggested_feeds']:
    verified = "VERIFIED" if feed.get('verified') else "UNVERIFIED"
    title = feed.get('title', feed['url'])
    print(f"  [{verified}] {title}")
    print(f"    URL: {feed['url']}")

# Add the verified feeds to your ingestion pipeline
for feed in feeds['suggested_feeds']:
    if feed.get('verified'):
        add_feed(
            name=feed.get('title', 'Untitled Feed'),
            url=feed['url'],
            feed_type="rss"
        )
```

### Tutorial 6: Import an OPML Subscription List

If you already have a feed reader like Feedly, Inoreader, or NewsBlur, export your subscriptions as OPML and import them in bulk.

```python
# Option A: Read from a local file
with open("C:\\Users\\sandr\\feeds.opml", "r", encoding="utf-8") as f:
    opml_content = f.read()

# Option B: Read from the uploads directory
# with open("data/feeds.opml", "r", encoding="utf-8") as f:
#     opml_content = f.read()

result = import_opml(opml_xml=opml_content)

print(f"Imported {result['count']} feeds ({result.get('errors', 0)} errors)")
for feed in result['imported']:
    status_icon = "+" if feed['status'] == 'added' else "=" if feed['status'] == 'duplicate' else "?"
    print(f"  {status_icon} {feed['status']}: {feed['name']}")

# Poll the newly imported feeds
poll_result = poll_feeds()
print(f"\nGot {poll_result['total_new']} new items from imported feeds")
```

**OPML structure:** The parser handles nested `<outline>` elements, extracting `xmlUrl` attributes for RSS/Atom feeds. Duplicate URLs (already present in the database) are reported as "duplicate" status. The `text` attribute is used as the feed name.

### Tutorial 7: Check Alert State for Urgent Items

Manually trigger the alert pipeline to check if any items need immediate attention. This is especially useful first thing in the morning before the scheduled 04:55 UTC alert job.

```python
alerts = check_alerts()
if alerts['count'] > 0:
    print("ALERTS TRIGGERED:")
    for title in alerts['alerted']:
        print(f"  !!! {title}")
    print(f"\nTotal: {alerts['count']} critical items")
else:
    print("No critical items found — overnight was quiet")

# Check what the alert threshold is
# Items with urgency >= 8.5 trigger alerts
night_items = get_top_items(limit=5, hours=12)
if night_items['count'] > 0:
    print(f"\nHighest urgency in last 12 hours: {night_items['items'][0]['urgency']}/10")
```

### Tutorial 8: Search Past Items by Keyword

Search across your entire ingested corpus using SQLite FTS5 full-text search with BM25 ranking. Supports advanced query syntax.

```python
# Simple keyword search
results = search_items(query="transformer AI", limit=10)
for item in results['items']:
    print(f"[{item['urgency']}/10] {item['title']}")
    print(f"  {item['source']} | Tags: {', '.join(item['tags'])}")
    print(f"  {item['summary'][:100]}...")

# Boolean search with AND
results = search_items(query="AI AND (ethics OR safety)", limit=10)
print(f"\nAI ethics/safety articles: {results['count']}")

# Exclusion search
results = search_items(query="NOT survey OR review", limit=10)
print(f"Non-survey articles: {results['count']}")

# Prefix wildcard search
results = search_items(query="GPU* OR TPU*", limit=20)
for item in results['items']:
    print(f"  Hardware news: {item['title']} ({item['source']})")

# Phrase search
results = search_items(query='\"reinforcement learning\"', limit=10)
print(f"\nPhrase match count: {results['count']}")
```

**FTS5 syntax:**
- `AND` — both terms must appear (default operator)
- `OR` — either term may appear
- `NOT` — exclude term
- `"phrase"` — exact phrase match
- `prefix*` — prefix wildcard (matches "transformer", "transformers", etc.)
- Column-specific: `title:attention` searches only the title field

### Tutorial 9: View Bundle Health and Tag Trends

Assess whether your interest bundles are producing useful signal, and spot emerging topics.

```python
# Check health of a specific bundle
health = get_bundle_health(bundle_id=1)
if 'error' not in health:
    print(f"Bundle: {health['name']}")
    print(f"Total items: {health['total_items']}")
    print(f"Avg urgency: {health['avg_urgency']:.1f}/10")
    print(f"Avg relevance: {health['avg_relevance']:.1f}/10")

    print("\nTop tags:")
    for tag in health.get('top_tags', []):
        print(f"  #{tag['tag']}: {tag['count']} mentions, avg urgency {tag.get('avg_urgency', 0):.1f}")

    print("\nFeed contributions:")
    for feed in health.get('feeds', []):
        print(f"  {feed['name']}: {feed['items']} items")

# View emerging tag trends across all bundles
trends = get_tag_trends(days=7, limit=20)
print(f"\n=== Tag Trends (last {trends['days']} days) ===")
for trend in trends['trends']:
    bar = "#" * (trend['count'] // 5)
    print(f"  #{trend['tag']:20s} {bar} {trend['count']:3d} items | urgency {trend.get('avg_urgency', 0):.1f}")

# Weekly vs daily comparison
weekly = get_tag_trends(days=7, limit=20)
daily = get_tag_trends(days=1, limit=10)
print(f"\nTag breadth: {weekly['count']} weekly vs {daily['count']} daily")
```

### Tutorial 10: Monitor the Feed Pipeline for Staleness

Check whether your ingestion pipeline is healthy and all feeds are being polled regularly.

```python
# Check pipeline health
liveness = pipeline_liveness(stale_hours=48)
print(f"Pipeline healthy: {liveness.get('healthy')}")
if not liveness['healthy']:
    print(f"Issues found:")
    for warning in liveness.get('warnings', []):
        print(f"  WARNING: {warning}")
    for feed_name in liveness.get('stale_feeds', []):
        print(f"  STALE: {feed_name}")
else:
    print("All feeds healthy and up to date")

# Get detailed feed health
health = get_feed_health()
print(f"\nFeed health summary:")
print(f"  Total: {health['total']}")
print(f"  Degraded (failing): {health['degraded']}")
print(f"  Disabled: {health['disabled']}")
print(f"  Low signal: {health['low_signal']}")

# Inspect failing feeds
for feed in health['feeds']:
    if feed['consecutive_failures'] > 0:
        print(f"\n  Failing feed: {feed['name']}")
        print(f"  Failures: {feed['consecutive_failures']}")
        print(f"  Last error: {feed.get('last_error', 'unknown')}")
        print(f"  Last fetched: {feed.get('last_fetched', 'never')}")
```

**What to watch for:**
- `stale_feeds` list: feeds that haven't been fetched within the threshold
- `degraded` count: feeds with consecutive failures (network issues, dead URLs)
- `low_signal` count: feeds that consistently produce low-urgency items (consider removing)
- `disabled` count: feeds that have been auto-disabled due to persistent failures

### Tutorial 11: Receive a Fleet Event from Another MCP Server

Other MCP servers in the fleet can push structured events into AIWatcher. This is the primary cross-repo integration mechanism.

```python
# Example: a robofang robot battery alert
event = ingest_fleet_event(
    title="Robot battery critical: Roomba kitchen died",
    summary="Battery dropped below 10% during cleaning cycle, robot may be stranded",
    source="robofang",
    url="http://robofang.local/events/evt-12345",
    urgency_hint=9.0  # Pre-scored: very urgent
)
print(f"Event ingested: ID {event.get('id')}")

# Example: a gitops GitHub PR event
event = ingest_fleet_event(
    title="New PR: Add Overseerr support to arr-mcp",
    summary="Added automatic Overseerr request routing to the arr-mcp orchestration pipeline",
    source="github",
    url="https://github.com/sandraschi/arr-mcp/pull/42"
)
print(f"PR event ingested: {event['title']}")

# Example: a calibre-mcp book addition
event = ingest_fleet_event(
    title="New book in Calibre: 'The Age of AI' by Henry Kissinger",
    summary="Added to Calibre library 'AI News'",
    source="calibre-mcp",
    url=""
)

# Example: a monitoring disk alert
event = ingest_fleet_event(
    title="Server disk usage at 92%",
    summary="C: drive on dev-box has only 8GB remaining",
    source="monitoring",
    urgency_hint=8.5
)

# Check if the event appeared in top items
latest = get_top_items(limit=5, hours=48)
for item in latest['items']:
    print(f"  [{item['urgency']}/10] {item['title']}")
```

**Without urgency_hint:** If no `urgency_hint` is provided, the event will be scored by the LLM during the next scheduled distillation cycle (or you can call `distill_pending()` manually).

### Tutorial 12: Clean Up Old Low-Urgency Items

Manually trigger item retention to free database space. This is useful before a backup or when you want to verify the retention policy is working.

```python
# Check current stats first
digest = generate_digest(hours=72)
print(f"Items in last 72h: {digest['item_count']}")

# Run retention
result = expire_old_items()
print(f"Deleted {result['deleted']} old items")
print(f"Retention policy: {result['retention_days']} days")

# Items with urgency >= 8.5 are preserved regardless of age
# Check what was kept
top = get_top_items(limit=5, hours=999999)
print(f"\nPreserved high-urgency items: {top['count']}")
```

**Retention logic:**
- Items older than `ITEM_RETENTION_DAYS` (default 90) are deleted
- Exception: items with `urgency_score >= 8.5` are kept permanently
- Feed decay: feeds with consistently low urgency over `FEED_DECAY_DAYS` may have their items aged out more aggressively
- The scheduled retention job runs daily at 03:00 UTC automatically

### Tutorial 13: Reload the Spam Blocklist

After editing the spam blocklist file (`data/spam_blocklist.txt`), reload it without restarting the server.

```python
# First, edit the blocklist file
# data/spam_blocklist.txt contains one pattern per line
# Example patterns:
#   .*spammy-blog.com.*
#   .*buy now.*
#   .*crypto scam.*

# Reload without restart
result = scrubber_reload()
print(f"Blocklist reloaded: {result['status']}")

# Verify by checking feed health for dropped items
health = get_feed_health()
print(f"Feeds affected by blocklist: {len(health.get('feeds', []))}")
```

**Blocklist file location:** The Scrubber reads `data/spam_blocklist.txt` relative to the package directory. Patterns are matched as substrings against item titles and source names. Lines starting with `#` are treated as comments.

### Tutorial 14: Poll Readly Magazine Subscriptions

If you have a Readly-MCP bridge configured, you can poll magazine articles directly into AIWatcher's ingestion pipeline.

```python
# View current Readly watchlist
watchlist = readly_watchlist(action="get")
print(f"Current watchlist ({watchlist['count']} magazines):")
for mag in watchlist['watchlist']:
    print(f"  {mag}")
print(f"Readly enabled: {watchlist['readly_enabled']}")
print(f"Poll interval: {watchlist['poll_interval_hours']}h")

# Add magazines to the watchlist
readly_watchlist(action="add", magazines="Wired, MIT Technology Review, Nature")

# Verify the updated list
watchlist = readly_watchlist(action="get")
print(f"\nUpdated watchlist ({watchlist['count']} magazines):")
for mag in watchlist['watchlist']:
    print(f"  {mag}")

# Manually poll Readly
result = poll_readly()
print(f"New articles from Readly: {result['new_items']}")

# If you want to replace the entire list
readly_watchlist(action="set", magazines="Science, Nature, The Economist")

# Remove a specific magazine
readly_watchlist(action="remove", magazines="Nature")

# Check the final state
watchlist = readly_watchlist(action="get")
print(f"\nFinal watchlist: {watchlist['watchlist']}")
```

**Important:** Runtime changes to the Readly watchlist are in-memory only. To make them persistent, set `READLY_WATCHLIST` in your `.env` file.

### Tutorial 15: View the Fleet Dashboard

Open the fleet status dashboard as a rich Prefab card in supporting MCP clients.

```python
# Show the dashboard card
# This returns a PrefabApp visual card rendered in-chat
# (Claude Desktop, Cursor, Windsurf all support this)
card = show_dashboard_card()
# The card displays:
# - Active Feeds count
# - Items Today (last 24h)
# - Unread Items count
# - Critical Items (urgency >= 8.5)
# - Total Items in database
```

In non-Prefab clients, the card falls back to a plain-text summary. The dashboard data is fetched live from the database every time the card is shown.

**Dashboard KPI reference:**
- **Active Feeds** — Number of feeds with `enabled=true` in the database. This is your total monitoring surface area.
- **Items Today** — Total items ingested in the last 24 hours, regardless of score. High numbers mean active feeds; low or zero numbers suggest stale feeds or a broken pipeline.
- **Unread Items** — Items that have been ingested but not yet scored by the LLM. If this number is high, consider running `distill_pending()` or checking the distillation scheduler is running.
- **Critical Items** — Items with urgency score >= `ALERT_THRESHOLD` (default 8.5). Any non-zero number here means there are items that need immediate attention.
- **Total Items** — Grand total of all items in the database. Use this to gauge overall corpus size and plan retention schedules.

### Tutorial 16: Manage Feed Quality and Decay

AIWatcher tracks feed quality over time and can flag or decay feeds that consistently produce low-urgency content. This keeps your pipeline focused on signal.

```python
# View feed health with quality scoring
health = get_feed_health()
print(f"=== Feed Health Report ===")
print(f"Total feeds: {health['total']}")
print(f"Degraded (failing): {health['degraded']}")
print(f"Auto-disabled: {health['disabled']}")
print(f"Low-signal feeds: {health['low_signal']}")

# Inspect low-signal feeds in detail
for feed in health['feeds']:
    if feed.get('quality_flag') == 'low_signal':
        print(f"\n  LOW SIGNAL: {feed['name']}")
        print(f"  URL: {feed['url']}")
        print(f"  Last fetched: {feed.get('last_fetched', 'never')}")

# Check if feed decay settings are working
# FeedDecay: items older than FEED_DECAY_DAYS (default 30)
# with avg urgency below FEED_DECAY_URGENCY_THRESHOLD (default 2.0)
# and fewer than FEED_DECAY_MIN_ITEMS (default 5) are flagged

# After removing low-signal feeds, run retention
result = expire_old_items()
print(f"\nCleaned up {result['deleted']} aged-out items")
```

### Tutorial 17: Full Setup Script

Here's a complete from-scratch setup that adds typical feeds, creates bundles, and starts the pipeline:

```python
# 1. Add diverse AI news feeds
feeds_to_add = [
    ("ArXiv ML", "http://export.arxiv.org/rss/cs.LG", "rss"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "rss"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/", "atom"),
    ("Nature AI", "https://www.nature.com/subjects/artificial-intelligence.rss", "rss"),
    ("Hacker News", "https://hnrss.org/frontpage", "rss"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "rss"),
]
feed_ids = []
for name, url, ftype in feeds_to_add:
    result = add_feed(name=name, url=url, feed_type=ftype)
    feed_ids.append(result['id'])
    print(f"Added feed: {name} (ID: {result['id']})")

# 2. Create bundles
bundles_to_create = [
    "AI Research", "Robotics", "Climate Tech",
    "Biotechnology", "Cryptocurrency", "Space Exploration"
]
bundle_ids = []
for topic in bundles_to_create:
    bundle = create_bundle_from_topic(topic=topic)
    bundle_ids.append(bundle['id'])
    print(f"Created bundle: {bundle['name']} (ID: {bundle['id']})")

# 3. Link first feed to first bundle
link_feed_to_bundle(feed_id=feed_ids[0], bundle_id=bundle_ids[0])

# 4. Poll feeds
poll_result = poll_feeds()
print(f"\nPolled feeds: {poll_result['total_new']} new items")

# 5. Run distillation
distill_result = distill_pending(batch_size=30)
print(f"Distilled: {distill_result['items_distilled']} items")

# 6. View results
top = get_top_items(limit=5, hours=48)
print(f"\nTop items: {top['count']}")
for item in top['items']:
    print(f"  [{item['urgency']}/10] {item['title']}")
```

## REST API Reference (HTTP Mode)

When running in HTTP mode (`uv run python -m aiwatcher_mcp.api`), the server exposes:

### Health

```
GET /health
```
Returns 200 OK with server status. Unauthenticated (exempt from AIWATCHER_API_KEY auth).

### MCP Endpoint

```
GET /mcp  → SSE transport
POST /mcp → JSON-RPC message
```
Standard MCP streamable HTTP transport. All MCP tools listed above are available via JSON-RPC.

### Feeds

```
GET /api/feeds — List all feeds
GET /api/feeds/health — Feed health with quality scores
```

### Items

```
GET /api/items/top?hours=24&limit=10&bundle_id= — Top scored items
GET /api/items/search?q=transformer&limit=20 — FTS5 search
```

### Bundles

```
GET /api/bundles — List bundles
GET /api/bundles/:id/health — Per-bundle health metrics
```

### Digests

```
GET /api/digests — Digest history
GET /api/digests/:id — Full digest HTML body
POST /api/digests/generate?hours=24 — Generate fresh digest
POST /api/digests/send — Send digest email
```

### Stats

```
GET /api/stats — Database statistics snapshot
GET /api/tags/trends?days=7&limit=20 — Tag trends
```

### Fleet

```
POST /api/fleet/ingest — Ingest fleet event (JSON body)
GET /api/fleet/liveness?stale_hours=48 — Pipeline liveness
```

### Auth

All API endpoints (except `/health`) require authentication when `AIWATCHER_API_KEY` is set. Use header `X-AIWatcher-Key` or `Authorization: Bearer <token>`.

## Troubleshooting

### "Feeds returning no items"

1. Verify the feed URL is valid by opening it in a browser or curl
2. Check `get_feed_health()` for failure counts and error messages
3. Some RSS feeds block requests without a proper User-Agent — the server sends one by default, but some feeds require specific headers
4. The scrubber may be blocking content — check `data/spam_blocklist.txt` for over-matching patterns
5. Check the server logs for feedparser errors: `LOG_LEVEL=DEBUG` for detailed output
6. Verify the feed is enabled: `get_feeds_list()` shows `enabled` status

### "Distillation not scoring items"

1. Verify the LLM provider is reachable: check `LLM_BASE_URL` or provider API key
2. Check the server logs for provider validation errors on startup
3. If using a cloud provider, verify it is in `CLOUD_PROVIDERS_ALLOWED`
4. Ensure items exist: run `poll_feeds()` first, then check `get_top_items()`
5. Increase log verbosity: `LOG_LEVEL=DEBUG` to see per-item scoring results
6. Check the LLM provider's rate limits — the server retries with backoff, but persistent 429s mean you need higher rate limits
7. If using Ollama, verify the model is pulled: `ollama list`

### "Digest not sending"

1. Check email-mcp connectivity if using `EMAIL_MCP_URL`
2. Verify SMTP credentials if using direct SMTP
3. Ensure `EMAIL_ENABLED=true` in your .env
4. Run `send_digest_now()` to force immediate delivery (generates + sends in one call)
5. Check `get_digest_history()` for recent digest send status
6. For Gmail SMTP, you may need an app-specific password (not your regular password)
7. Check the Intel Hub URL if digests are being published there

### "Pipeline liveness shows stale feeds"

1. Verify the feed URL is still valid (sites change their RSS URLs)
2. Check if the feed's domain has network issues
3. If the feed is permanently dead, remove it and find an alternative
4. Adjust `stale_hours` threshold if you expect longer gaps
5. Check if the scheduler is running: `LOG_LEVEL=DEBUG` shows scheduler job execution

### "Bundle has low signal with many items"

1. The scoring persona (system_prompt) may be too broad — update it via `update_fleet_bundle()`
2. The feeds linked to this bundle may be producing noisy content — remove low-signal feeds
3. Adjust the bundle's system prompt to be more specific about what constitutes relevant content
4. Consider creating more specific bundles for sub-topics
5. Check `get_bundle_health()` to see which feeds contribute the most low-urgency items

### "Error: UNIQUE constraint failed"

1. This feed URL is already in the database
2. Use `get_feeds_list()` to find the existing entry
3. If you need to add a similar feed, verify the URL is different

### "OPML import returned errors"

1. Verify the OPML XML is well-formed (validate with an XML validator)
2. Some feed readers export non-standard OPML — check for unusual namespace attributes
3. Duplicate URLs (already in the database) are reported as "duplicate" status, not errors
4. The count in the response may include both additions and duplicates

## FAQ

**Q: How often does AIWatcher poll feeds?**
A: Every 30 minutes by default. Configure with `FEED_POLL_INTERVAL_MINUTES`. You can also manually trigger `poll_feeds()` at any time.

**Q: How long are items kept?**
A: Default 90 days (`ITEM_RETENTION_DAYS`). High-urgency items (score >= 8.5) are kept permanently regardless of age.

**Q: What scoring does the distillation use?**
A: Each item gets relevance (0-10) and urgency (0-10) scores, a distilled summary in Sandra's technical voice, 3-6 auto-generated tags, and a scoring reason. The LLM persona is defined by the bundle's system prompt. Items matching portfolio watch keywords get a `portfolio-watch` tag and an urgency boost.

**Q: Can I use a local LLM instead of Claude?**
A: Yes. The default is LM Studio (local). Set `LLM_PROVIDER=ollama` and configure `LLM_BASE_URL=http://localhost:11434/v1` to use Ollama. You can also enable DeepSeek (cheap cloud) or Anthropic (expensive, quality-critical) by adding them to `CLOUD_PROVIDERS_ALLOWED` and providing the corresponding API key.

**Q: What is 2-tier flash+pro distillation?**
A: An optional cost-saving mode where a cheap local model (e.g., Gemma 3 1B) pre-scores everything. Items that are clearly junk (relevance < 4) or clearly important (relevance > 7) keep their flash scores. Only borderline items (relevance 4-7) get re-scored by the expensive model. This saves API costs while keeping quality high.

**Q: How do I add new RSS feeds?**
A: Use `add_feed(name, url, feed_type)` for single feeds or `import_opml(opml_xml)` for bulk import from feed readers like Feedly, Inoreader, or NewsBlur.

**Q: Can AIWatcher alert me on my phone?**
A: AIWatcher sends alerts to robofang (TTS), which can trigger desktop notifications. For mobile alerts, configure robofang with your preferred notification channel (webhook, email, etc.).

**Q: What happens if a feed is broken?**
A: The feed quality tracker tracks consecutive failures. Feeds with persistent failures may be auto-disabled. Check `get_feed_health()` for per-feed failure counts and error messages.

**Q: How do I search my ingested items?**
A: Use `search_items(query)` with FTS5 syntax. Examples: `"transformer AND attention"`, `"AI OR ML"`, `"NOT survey"`, `"GPU*"`. Results are sorted by urgency score descending.

**Q: Can I import from Feedly/Inoreader?**
A: Yes. Export your feeds as OPML and use `import_opml(opml_xml)`.

**Q: What does the 'Critical' badge on the dashboard mean?**
A: Items with urgency score >= `ALERT_THRESHOLD` (default 8.5) are considered critical. These are items that need immediate attention and trigger TTS alerts via robofang.

**Q: How do fleet events work?**
A: Other MCP servers call `ingest_fleet_event()` with a title, summary, source name, optional URL, and optional urgency hint. Without a hint, the event will be scored during the next distillation run. With a hint, it bypasses LLM scoring.

**Q: What's the difference between SQLite bundles (get_bundles_list) and fleet bundles (list_fleet_bundles)?**
A: SQLite bundles are used by the distillation engine to score items per-bundle. Fleet bundles (from `interests.json`) are shared with other fleet MCP servers. Both are kept in sync — `create_bundle_from_topic()` writes to both.

**Q: Can AIWatcher monitor arXiv papers?**
A: Yes. Enable `ARXIV_ENABLED=true` and configure `ARXIV_MCP_URL` pointing to arxiv-mcp. The server will poll specified arXiv category feeds (configurable via `ARXIV_CATEGORIES`).

**Q: Does AIWatcher support multiple languages?**
A: The RSS/Atom ingestion handles any language that the feed provides. The LLM scoring is configured for English in the default Sandra persona, but you can customize the system prompt per-bundle for other languages.

**Q: What is the Intel Hub?**
A: A fleet-wide digest publishing endpoint (fleet-agent-mcp's Intel Hub). Every generated digest is optionally published there for visibility across the fleet. Configure via `CENTRAL_DOCS_PATH`.

**Q: Can I run AIWatcher without any LLM?**
A: The server will start and poll feeds without an LLM, but distillation, scoring, digest generation, and alerts will be unavailable. You need at least a local provider (LM Studio, Ollama) for the core value proposition.
