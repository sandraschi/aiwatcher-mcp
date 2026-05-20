# aiwatcher-mcp v0.2.0 — Implementation Plan

**Date**: 2026-04-29
**Total scope**: 6 features, ~500 LOC

---

## F1: Interest Bundle Health Metrics

**Why**: Per-bundle metrics to answer "is my Robotics bundle getting useful news?" Currently only feed-level health exists.

**Implementation**:
- `database.py`: Add `get_bundle_stats(bundle_id)` — items scored, avg urgency, top tags, feed contributions
- `server.py`: Add `get_bundle_health` MCP tool
- `api.py`: Add `GET /api/bundles/{id}/health` REST endpoint
- `tests/test_database.py`: Add test for `get_bundle_stats`

**Scoreboard return**:
```json
{
  "bundle_id": 1, "name": "Sandra's AI Research",
  "items_scored": 342, "avg_urgency": 5.2,
  "top_tags": ["claude","openai","mcp"],
  "source_feeds": [
    {"name": "Anthropic Blog", "items": 23, "avg_urgency": 7.1},
    {"name": "The Decoder", "items": 87, "avg_urgency": 4.3}
  ],
  "last_distilled": "2026-04-29T10:00:00Z"
}
```

---

## F2: Actual Feed Discovery via URL Probing

**Why**: `elicit_bundle_config()` hallucinates feed URLs via LLM. Many are dead. This probes them.

**Implementation**:
- `bundles.py`: After LLM elicitation, probe each suggested URL with `httpx` + `feedparser`
- Keep only URLs that return 200 + valid RSS/Atom
- For failed URLs, try common feed path variants (`/feed/`, `/rss/`, `/index.xml`, `/atom.xml`)
- Return only verified feeds in the bundle config
- `server.py`: Add `find_feeds_for_topic` MCP tool that returns probed results
- `tests/test_bundles.py`: New test file

---

## F3: Cross-Feed Near-Dedup via Title Similarity

**Why**: Same Reuters story via Google News RSS and direct Reuters RSS = two items with different GUIDs/URLs. Currently no dedup.

**Implementation**:
- `database.py`: `upsert_item()` — before INSERT, search existing items for similar titles within last 48h using `difflib.SequenceMatcher` with threshold 0.85
- If similar item exists, update that item's tags to include the new feed name (as a cross-reference)
- `tests/test_database.py`: Add dedup tests

---

## F4: Stale Feed Fallback URL Probes

**Why**: 5 consecutive failures auto-disables a feed. But sites change feed URLs silently.

**Implementation**:
- `ingestion.py`: `poll_feed()` — when HTTP fetch fails (not timeout, but 404/410/301), try fallback paths
- Fallback list: `/feed/`, `/rss/`, `/index.xml`, `/atom.xml`, `/blog/feed/`
- If a fallback works, update the feed URL in the database
- `tests/test_ingestion.py`: Add fallback tests

---

## F5: OPML Import

**Why**: Import curated subscriptions from other RSS readers.

**Implementation**:
- `server.py`: Add `import_opml` MCP tool — accepts OPML XML string
- Parse with `defusedxml` (already in deps) or `feedparser` OPML support
- For each outline with an `xmlUrl`, call `add_feed`
- `tests/test_server.py`: Add OPML import test

---

## F6: readly-mcp Integration (SPEC only — blocked on readly-mcp)

**Why**: readly-mcp at port 10863 scrapes magazine pages as images. For aiwatcher-mcp integration, it needs a new "list articles" tool. Until readly-mcp gains that capability, this is design-only.

**Spec**:
- readly-mcp needs a new MCP tool: `list_current_issue_articles` — uses browser context to extract article titles and URLs from the currently viewed issue page
- aiwatcher-mcp adds a scheduler job: every 6h, call readly-mcp `GET /api/status`, if browser is on a magazine page and not scraping, call `list_current_issue_articles`, insert results as items
- OR: simpler approach — readly-mcp already saves PDFs to `~/Desktop/readly/`. Add a `poll_readly_exports` job that watches the export directory for new PDFs, extracts text via OCR/pymupdf, and inserts items
