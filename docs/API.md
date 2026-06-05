# aiwatcher-mcp API Reference

**Package version:** `0.1.6` (`pyproject.toml`, `src/aiwatcher_mcp/_version.py`).  
**Surfaces:** (1) **stdio MCP** — `uv run python -m aiwatcher_mcp.server`. (2) **HTTP** — `uv run python -m aiwatcher_mcp.api`: REST under `/api/*`, **MCP streamable HTTP** at **`/mcp`** (port **10946** by default).

**Authoritative tool list:** call **`GET /api/capabilities`** and read **`tool_surface.atomic_tools`**.

---

## MCP tools (FastMCP 3.2)

### Ingestion & distillation

| Tool | Summary |
|------|--------|
| **`poll_feeds()`** | Poll all enabled RSS/Atom feeds. Returns `{ total_new, by_feed }`. |
| **`distill_pending(batch_size=20)`** | Score pending items (cap 50). Returns `{ items_distilled }`. |

### Alerts & digests

| Tool | Summary |
|------|--------|
| **`check_alerts()`** | Run alert pipeline (robofang / speechops). Returns `{ alerted, count }`. |
| **`generate_digest(hours=24)`** | Build digest (respects `DIGEST_CACHE_TTL_MINUTES`). |
| **`send_digest_now()`** | Send digest email now. Returns `{ sent, subject }`. |
| **`get_digest_history(limit=10)`** | Recent digest metadata (no full HTML). |

### Items & search

| Tool | Summary |
|------|--------|
| **`get_top_items(bundle_id=None, limit=10, hours=24)`** | Top items by urgency; optional bundle id. |
| **`search_items(query, limit=20)`** | FTS5 search (max 100 results). |

### Feeds & quality

| Tool | Summary |
|------|--------|
| **`get_feeds_list()`** | All feeds + status. |
| **`get_feed_health()`** | Feeds with failures + **`quality_flag`** / **`avg_urgency_30d`**. |
| **`add_feed(name, url, feed_type="rss")`** | Add feed; `{ id, ... }` or `{ error }`. |

### Bundles & fleet

| Tool | Summary |
|------|--------|
| **`get_bundles_list()`** | SQLite-backed bundles. |
| **`create_bundle_from_topic(topic)`** | LLM elicitation + DB + fleet JSON sync. |
| **`link_feed_to_bundle(feed_id, bundle_id)`** | Link feed to bundle. |
| **`get_bundle_health(bundle_id)`** | Per-bundle metrics. |
| **`find_feeds_for_topic(topic)`** | Probe/verify feed URLs. |
| **`import_opml(opml_xml)`** | Import OPML outlines with `xmlUrl`. |
| **`list_fleet_bundles()`** / **`update_fleet_bundle(...)`** | Fleet JSON bundles. |
| **`ingest_fleet_event(title, ...)`** | Record fleet-originated events for digests. |
| **`get_tag_trends(days=7, limit=20)`** | Tag frequency over scored items. |

### Maintenance & ops

| Tool | Summary |
|------|--------|
| **`expire_old_items()`** | Retention pass. |
| **`scrubber_reload()`** | Reload spam blocklist. |
| **`aiwatcher_help(topic?)`** | In-chat docs: `fleet_pipeline`, `api_keys`, `integrations`, … |
| **`show_dashboard_card()`** | Prefab UI card (when enabled). |

---

## HTTP REST (Starlette)

Base: **`http://localhost:10946`** (`BACKEND_PORT`).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health`, `/api/health` | Liveness + `items_total`, `items_last_24h`, `last_poll_at`, `scheduler_running`. |
| GET | `/metrics` | Prometheus text format (`aiwatcher_*` gauges). Public (no API key). |
| GET | `/api/capabilities` | Live `tool_surface`, features, integrations. |
| GET | `/api/env` | Redacted `.env` keys. **Non-loopback requires `AIWATCHER_API_KEY`.** |
| POST | `/api/env` | Merge keys into `.env`. Same remote rule as GET. |
| GET | `/api/trends?days=7` | Tag trend list. |
| GET | `/api/feeds/health` | Feeds + `quality_flag`, `low_signal_feeds` count. |
| GET | `/api/pipeline/liveness` | arXiv feed staleness + upstream arxiv/vla probes. |
| GET | `/api/help`, `/api/help/{topic}` | Markdown help (`fleet_pipeline`, `api_keys`, …). |
| POST | `/api/fleet/ingest` | Producer API for arxiv-codehunt and vla-mcp-pipeline events. |

When **`AIWATCHER_API_KEY`** is set, all other `/api/*` routes require **`X-AIWatcher-Key`** or **`Authorization: Bearer`**. Exempt: `/health`, `/api/health`, `/metrics`, `/mcp`.

See [FLEET_PIPELINE.md](FLEET_PIPELINE.md) for producer keys and interest bundles.

Representative **`POST`** routes: `/api/poll`, `/api/distill`, `/api/alerts/check`, `/api/feeds/add`, `/api/opml/import`, `/api/scrubber/reload`, … — see **`src/aiwatcher_mcp/api.py`**.

---

## Environment (selected)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AIWATCHER_API_KEY` | — | Optional REST auth; mirror on arxiv/vla producer env when set |
| `ARXIV_MCP_URL` | localhost:10770 | arXiv pull + code-hunt upstream (not 10719) |
| `VLA_MCP_URL` | localhost:11024 | VLA pipeline liveness probe |
| `DIGEST_CACHE_TTL_MINUTES` | 60 | Skip LLM if recent digest exists |
| `FEED_DECAY_DAYS` / `FEED_DECAY_MIN_ITEMS` / `FEED_DECAY_URGENCY_THRESHOLD` | 30 / 5 / 2.0 | Feed `quality_flag` |
| `PORTFOLIO_WATCH_TERMS` | fastmcp,… | Comma-separated keyword boost |
| `DIGEST_TONE_SANDRA` / `DIGEST_TONE_STEVE` | see `.env.example` | Digest audience hints |
| `INTERESTS_JSON_PATH` | interests.json | Daily `sync_interests` source |

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — pipelines and storage.  
- [FLEET_PIPELINE.md](FLEET_PIPELINE.md) — fleet ingest, API keys, liveness.  
- [PRD.md](PRD.md) — product scope and roadmap.
