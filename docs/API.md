# aiwatcher-mcp API Reference

**Package version:** `0.1.0` (`pyproject.toml`, `src/aiwatcher_mcp/_version.py`).  
**Surfaces:** (1) **stdio MCP** — `uv run python -m aiwatcher_mcp.server`. (2) **HTTP** — `uv run python -m aiwatcher_mcp.api`: REST under `/api/*`, **MCP streamable HTTP** at **`/mcp`** (port **10946** by default).

**Authoritative tool list:** call **`GET /api/capabilities`** on the HTTP API and read **`tool_surface.atomic_tools`** (and **`total`**). Extra tool names may appear when **`MCP_BRIDGE_URLS`** proxies remote MCPs.

---

## MCP tools (FastMCP 3.2)

Docstrings in `src/aiwatcher_mcp/server.py` are canonical; this section is a compact index.

### Ingestion & distillation

| Tool | Summary |
|------|--------|
| **`poll_feeds()`** | Poll all enabled RSS/Atom feeds. Returns `{ total_new, by_feed }`. |
| **`distill_pending(batch_size=20)`** | Score pending items (cap 50). Returns `{ items_distilled }`. |

### Alerts & digests

| Tool | Summary |
|------|--------|
| **`check_alerts()`** | Run alert pipeline (robofang / speechops). Returns `{ alerted, count }`. |
| **`generate_digest(hours=24)`** | Build digest; returns subject, preview, text (HTML truncated for MCP). |
| **`send_digest_now()`** | Send digest email now. Returns `{ sent, subject }`. |
| **`get_digest_history(limit=10)`** | Recent digest metadata (no full HTML). |

### Items & search

| Tool | Summary |
|------|--------|
| **`get_top_items(bundle_id=None, limit=10, hours=24)`** | Top items by urgency; optional **SQLite bundle id** filter. |
| **`search_items(query, limit=20)`** | FTS5 search (max 100 results). |

### Feeds

| Tool | Summary |
|------|--------|
| **`get_feeds_list()`** | All feeds + status. |
| **`get_feed_health()`** | Feeds with failure counts / degraded / disabled. |
| **`add_feed(name, url, feed_type="rss")`** | Add feed; `{ id, ... }` or `{ error }`. |

### Bundles & fleet

| Tool | Summary |
|------|--------|
| **`get_bundles_list()`** | SQLite-backed bundles. |
| **`create_bundle_from_topic(topic)`** | LLM elicitation + DB + fleet JSON sync. |
| **`link_feed_to_bundle(feed_id, bundle_id)`** | Link feed to bundle. |
| **`get_bundle_health(bundle_id)`** | Per-bundle metrics (returns `{ error }` if missing). |
| **`find_feeds_for_topic(topic)`** | Probe/verify feed URLs for a topic. |
| **`import_opml(opml_xml)`** | Import outlines with `xmlUrl` into `feeds`. |
| **`list_fleet_bundles()`** | Bundles from fleet JSON (MCD / registry workflow). |
| **`update_fleet_bundle(bundle_id, updates)`** | Patch fleet bundle by string `id`. |

### Maintenance & ops

| Tool | Summary |
|------|--------|
| **`expire_old_items()`** | Retention pass; returns `{ deleted, retention_days }`. |
| **`scrubber_reload()`** | Reload spam blocklist without restart. |

### Prefab UI *(when `AIWATCHER_PREFAB_APPS` is true)*

| Tool | Summary |
|------|--------|
| **`show_dashboard_card()`** | App tool — fleet status **Prefab** card in supported clients. |

---

## MCP prompts

| Prompt | Role |
|--------|------|
| **`breaking_news_brief()`** | Short brief of recent high-urgency items (TTS-friendly). |
| **`portfolio_impact_analysis()`** | Injects last 24h items; portfolio-style analysis instructions. |

---

## MCP resources

| URI | Content |
|-----|--------|
| **`aiwatcher://feeds/list`** | JSON list of feeds and status. |
| **`aiwatcher://stats`** | JSON fleet stats (totals, critical, unread, etc.). |

---

## HTTP REST (Starlette)

Base: **`http://localhost:10946`** (override with `BACKEND_PORT`).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/health`, `/health` | Liveness JSON (`version` = `server_version`). |
| GET | `/api/capabilities` | Fleet / UI contract: server meta, **live** `tool_surface`, `features`, `integrations`. |
| GET | `/api/env` | `.env` keys with **redacted** secret-like values (`***REDACTED***`). No auth by default — do not expose publicly. |
| POST | `/api/env` | Merge JSON keys into `.env` (write path). |

Representative **`POST`** routes (non-exhaustive): `/api/poll`, `/api/distill`, `/api/alerts/check`, `/api/feeds/add`, `/api/opml/import`, `/api/config/reload`, `/api/scrubber/reload`, … — see **`src/aiwatcher_mcp/api.py`** `routes = [...]` for the full list.

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — pipelines and storage.  
- [PRD.md](PRD.md) — product scope and roadmap.
