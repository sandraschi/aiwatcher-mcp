"""
FastMCP 3.2 MCP server — tools, prompts, resources, Prefab UI.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastmcp import Context
from fastmcp.server import create_proxy
from fastmcp.server.lifespan import lifespan
from fastmcp.server.providers.skills import SkillsDirectoryProvider
from fastmcp.server.server import FastMCP
from prefab_ui.app import PrefabApp

from aiwatcher_mcp._version import __version__
from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)
cfg = get_settings()


@lifespan
async def _mcp_db_lifespan(_server):
    from aiwatcher_mcp.database import close_db_pool, init_db

    await init_db()
    log.info("aiwatcher-mcp startup: DB ready")
    try:
        yield {}
    finally:
        # Orphan-process fix (2026-06-11): without this, the pooled
        # aiosqlite connection thread outlives the event loop and the
        # process never exits after stdio EOF (client restart leak).
        await close_db_pool()
        log.info("aiwatcher-mcp shutdown: DB pool closed")


mcp = FastMCP(
    name=cfg.server_name,
    version=__version__,
    instructions="AI news ingestion, distillation, and alert system for Sandra's fleet",
    lifespan=_mcp_db_lifespan,
)

_bridge_proxies = []
bridge_urls = os.getenv("MCP_BRIDGE_URLS", "")
if bridge_urls:
    for url in bridge_urls.split(","):
        url = url.strip()
        if url:
            try:
                mcp.add_provider(create_proxy(url))
                _bridge_proxies.append(url)
            except Exception:
                pass

# Skills provider (expert-level context for chat preprompt)
_skills_dir = Path(__file__).resolve().parent / "skills"
if _skills_dir.is_dir():
    mcp.add_provider(SkillsDirectoryProvider(roots=[_skills_dir]))
    log.info("Skills provider registered")

# ── Tools ──────────────────────────────────────────────────────────────────────


@mcp.tool()
async def poll_feeds(ctx: Context) -> dict:
    """
    Poll all enabled RSS/Atom feeds for new items.

    Rationale: Manually trigger a feed poll outside the scheduled interval.
    Useful after adding a new feed or when chasing a breaking story.

    Returns: dict with per-feed new item counts and total.
    """
    from aiwatcher_mcp.ingestion import poll_all_feeds

    await ctx.info("Starting feed poll...")
    results = await poll_all_feeds()
    total = sum(results.values())
    await ctx.info(f"Poll complete: {total} new items")
    return {"total_new": total, "by_feed": results}


@mcp.tool()
async def distill_pending(ctx: Context, batch_size: int = 20) -> dict:
    """
    Score and summarize unprocessed items with Claude.

    Rationale: Run Claude distillation on-demand rather than waiting for the scheduler.
    Each item gets a relevance score, urgency score, Sandra-voice summary, and tags.

    Args:
        batch_size: Max items to process in this call (default 20, max 50).

    Returns: dict with count of items processed.
    """
    from aiwatcher_mcp.distillation import distill_items

    batch_size = min(batch_size, 50)
    await ctx.info(f"Distilling up to {batch_size} items...")
    count = await distill_items(batch_size)
    return {"items_distilled": count}


@mcp.tool()
async def check_alerts(ctx: Context) -> dict:
    """
    Check for critical items and fire alerts (robofang + TTS).

    Rationale: Manually trigger the alert pipeline — e.g. Sandra just woke up
    and wants to know if anything broke overnight before the 5am job ran.

    Returns: dict with list of alerted item titles.
    """
    from aiwatcher_mcp.alerting import process_alerts

    await ctx.info("Checking alert candidates...")
    alerted = await process_alerts()
    return {"alerted": alerted, "count": len(alerted)}


@mcp.tool()
async def generate_digest(ctx: Context, hours: int = 24) -> dict:
    """
    Generate a fresh HTML+text digest of recent scored items.

    Rationale: Preview the digest before sending, or regenerate on demand.

    Args:
        hours: Lookback window in hours (default 24).

    Returns: dict with subject, html_body (truncated), text_body.
    """
    from aiwatcher_mcp.distillation import generate_digest as _gen

    await ctx.info(f"Generating digest for last {hours}h...")
    result = await _gen(hours=hours)
    # Truncate html for MCP response — full HTML is in the REST API
    result["html_preview"] = result.get("html_body", "")[:500] + "..."
    result.pop("html_body", None)
    return result


@mcp.tool()
async def send_digest_now(ctx: Context) -> dict:
    """
    Send the daily digest email to Sandra and Steve immediately.

    Rationale: Force-send outside the 07:00 UTC schedule.

    Returns: dict with delivery status.
    """
    from aiwatcher_mcp.distillation import generate_digest as _gen
    from aiwatcher_mcp.email_delivery import send_digest

    digest = await _gen(hours=24)
    success = await send_digest(digest)
    return {"sent": success, "subject": digest.get("subject", "")}


@mcp.tool()
async def get_bundles_list(ctx: Context) -> dict:
    """
    List all configured interest bundles.

    Returns: dict with list of bundles.
    """
    from aiwatcher_mcp.database import get_bundles

    bundles = await get_bundles()
    return {"bundles": bundles, "count": len(bundles)}


@mcp.tool()
async def create_bundle_from_topic(ctx: Context, topic: str) -> dict:
    """
    Generate and create a new interest bundle based on a topic keyword.

    Rationale: Low-friction way to add new interests (e.g. "dogs", "yachts").
    Claude will generate the persona and configuration.

    Args:
        topic: The topic keyword (e.g. "Space exploration", "Formula 1").

    Returns: dict with the new bundle configuration and ID.
    """
    from aiwatcher_mcp.bundles import elicit_bundle_config, load_fleet_bundles, save_fleet_bundles
    from aiwatcher_mcp.database import add_bundle

    await ctx.info(f"Eliciting bundle config for topic: {topic}...")
    config = await elicit_bundle_config(topic)

    # Save to SQLite for distillation logic
    bundle_id = await add_bundle(
        name=config["name"], topic=topic, system_prompt=config["system_prompt"]
    )

    # Sync to Fleet JSON
    fleet_bundles = load_fleet_bundles()
    new_bundle = {
        "id": f"bundle-{bundle_id}",
        "name": config["name"],
        "description": f"AI-elicited bundle for {topic}",
        "interests": [topic],
        "sources": config.get("suggested_feeds", []),
        "active": True,
        "system_prompt": config["system_prompt"],
    }
    fleet_bundles.append(new_bundle)
    save_fleet_bundles(fleet_bundles)

    return {
        "id": bundle_id,
        "fleet_id": new_bundle["id"],
        "name": config["name"],
        "topic": topic,
        "system_prompt": config["system_prompt"],
        "suggested_feeds": config.get("suggested_feeds", []),
    }


@mcp.tool()
async def list_fleet_bundles(ctx: Context) -> dict:
    """
    List all interest bundles defined in the fleet (MCD).
    """
    from aiwatcher_mcp.bundles import load_fleet_bundles

    bundles = load_fleet_bundles()
    return {"bundles": bundles, "count": len(bundles)}


@mcp.tool()
async def update_fleet_bundle(ctx: Context, bundle_id: str, updates: dict) -> dict:
    """
    Update a fleet bundle's configuration.

    Args:
        bundle_id: The unique ID of the bundle.
        updates: Dictionary of fields to update (name, description, active, sources, etc.).
    """
    from aiwatcher_mcp.bundles import load_fleet_bundles, save_fleet_bundles

    bundles = load_fleet_bundles()
    for b in bundles:
        if b["id"] == bundle_id:
            b.update(updates)
            save_fleet_bundles(bundles)
            return {"success": True, "bundle": b}
    return {"error": f"Bundle {bundle_id} not found"}


@mcp.tool()
async def link_feed_to_bundle(ctx: Context, feed_id: int, bundle_id: int) -> dict:
    """
    Link an existing feed to an interest bundle.

    Args:
        feed_id: ID of the feed.
        bundle_id: ID of the bundle.

    Returns: dict with success status.
    """
    from aiwatcher_mcp.database import link_feed_to_bundle as _link

    await _link(feed_id, bundle_id)
    return {"success": True, "feed_id": feed_id, "bundle_id": bundle_id}


@mcp.tool()
async def get_top_items(
    ctx: Context, bundle_id: int | None = None, limit: int = 10, hours: int = 24
) -> dict:
    """
    Get top-scored items from the last N hours, sorted by urgency.

    Args:
        bundle_id: Optional bundle ID to filter by.
        limit: Number of items to return (default 10).
        hours: Lookback window (default 24).

    Returns: dict with list of top items.
    """
    if bundle_id:
        from aiwatcher_mcp.database import get_bundle_recent_items

        items = await get_bundle_recent_items(bundle_id=bundle_id, hours=hours, limit=limit)
    else:
        from aiwatcher_mcp.database import get_recent_items

        items = await get_recent_items(hours=hours, limit=limit)

    # Slim down for MCP response
    slim = [
        {
            "title": i["title"],
            "source": i.get("feed_name", ""),
            "feed_type": i.get("feed_type", ""),
            "url": i.get("url", ""),
            "urgency": i.get("urgency_score"),
            "relevance": i.get("relevance_score"),
            "summary": i.get("distilled_summary") or i.get("summary", "")[:200],
            "tags": json.loads(i.get("bundle_tags" if bundle_id else "tags") or "[]"),
        }
        for i in items
    ]
    return {"items": slim, "count": len(slim), "hours": hours, "bundle_id": bundle_id}


@mcp.tool()
async def get_feeds_list(ctx: Context) -> dict:
    """
    List all configured feeds with status and last fetch time.

    Returns: dict with list of feeds.
    """
    from aiwatcher_mcp.database import get_feeds

    feeds = await get_feeds()
    return {"feeds": feeds, "count": len(feeds)}


@mcp.tool()
async def search_items(ctx: Context, query: str, limit: int = 20) -> dict:
    """
    Full-text search across item titles, summaries, and distilled summaries.

    Uses SQLite FTS5 (BM25 ranking). Returns items sorted by urgency.

    Args:
        query: Search query string. Supports FTS5 syntax (AND, OR, NOT, prefix*).
        limit: Max results to return (default 20, max 100).

    Returns: dict with matching items and count.
    """
    from aiwatcher_mcp.database import search_items as _search

    limit = min(limit, 100)
    items = await _search(query=query, limit=limit)
    slim = [
        {
            "title": i["title"],
            "source": i.get("feed_name", ""),
            "url": i.get("url", ""),
            "urgency": i.get("urgency_score"),
            "relevance": i.get("relevance_score"),
            "summary": i.get("distilled_summary") or i.get("summary", "")[:200],
            "tags": json.loads(i.get("tags") or "[]"),
            "fetched_at": i.get("fetched_at"),
        }
        for i in items
    ]
    return {"items": slim, "count": len(slim), "query": query}


@mcp.tool()
async def get_digest_history(ctx: Context, limit: int = 10) -> dict:
    """
    List recently generated digests (metadata only — no HTML body).

    Args:
        limit: Number of digests to return (default 10, max 50).

    Returns: dict with digest list showing id, dates, item_count, sent_at.
    """
    from aiwatcher_mcp.database import get_recent_digests

    digests = await get_recent_digests(limit=min(limit, 50))
    return {"digests": digests, "count": len(digests)}


@mcp.tool()
async def expire_old_items(ctx: Context) -> dict:
    """
    Manually trigger item retention — delete old low-urgency items.

    Items older than ITEM_RETENTION_DAYS (default 90) are deleted,
    EXCEPT those with urgency_score >= 8.5 (kept permanently).

    Returns: dict with count of deleted items.
    """
    from aiwatcher_mcp.config import get_settings
    from aiwatcher_mcp.database import expire_old_items as _expire

    cfg = get_settings()
    deleted = await _expire(retention_days=cfg.item_retention_days)
    return {"deleted": deleted, "retention_days": cfg.item_retention_days}


@mcp.tool()
async def get_feed_health(ctx: Context) -> dict:
    """
    Show feed health status — highlights degraded or auto-disabled feeds.

    Returns: dict with feeds sorted by failure count descending.
    """
    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.feed_quality import enrich_feeds_with_quality

    async with (
        get_db() as db,
        db.execute(
            """SELECT id, name, url, feed_type, enabled, last_fetched,
                  consecutive_failures, last_error
           FROM feeds ORDER BY consecutive_failures DESC, name"""
        ) as cur,
    ):
        feeds = [dict(r) for r in await cur.fetchall()]
    feeds = await enrich_feeds_with_quality(feeds)
    degraded = [f for f in feeds if f["consecutive_failures"] > 0]
    disabled = [f for f in feeds if not f["enabled"]]
    low_signal = [f for f in feeds if f.get("quality_flag") == "low_signal"]
    return {
        "feeds": feeds,
        "total": len(feeds),
        "degraded": len(degraded),
        "disabled": len(disabled),
        "low_signal": len(low_signal),
    }


@mcp.tool()
async def get_tag_trends(ctx: Context, days: int = 7, limit: int = 20) -> dict:
    """Emerging topic tags from scored items over the last N days."""
    from aiwatcher_mcp.trends import get_tag_trends as _trends

    trends = await _trends(days=days, limit=limit)
    return {"days": days, "trends": trends, "count": len(trends)}


@mcp.tool()
async def pipeline_liveness(ctx: Context, stale_hours: int = 48) -> dict:
    """Check arXiv ingestion pipeline health (stale feeds, wrong port, upstream down)."""
    from aiwatcher_mcp.pipeline_liveness import check_pipeline_liveness

    return await check_pipeline_liveness(stale_hours=stale_hours)


@mcp.tool()
async def ingest_fleet_event(
    ctx: Context,
    title: str,
    summary: str = "",
    source: str = "fleet",
    url: str = "",
    urgency_hint: float | None = None,
) -> dict:
    """Ingest a structured event from another fleet MCP (PR, robot, calibre, etc.)."""
    from aiwatcher_mcp.fleet_events import ingest_fleet_event as _ingest

    return await _ingest(
        title=title,
        summary=summary,
        source=source,
        url=url,
        urgency_hint=urgency_hint,
    )


@mcp.tool()
async def add_feed(ctx: Context, name: str, url: str, feed_type: str = "rss") -> dict:
    """
    Add a new feed to the ingestion list.

    Args:
        name: Human-readable feed name.
        url: RSS/Atom feed URL.
        feed_type: Feed type — 'rss' or 'atom' (default 'rss').

    Returns: dict with new feed id.
    """
    from aiwatcher_mcp.database import get_db

    async with get_db() as db:
        try:
            cur = await db.execute(
                "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                (name, url, feed_type),
            )
            await db.commit()
            return {"id": cur.lastrowid, "name": name, "url": url}
        except Exception as exc:
            return {"error": str(exc)}


@mcp.tool()
async def get_bundle_health(ctx: Context, bundle_id: int) -> dict:
    """
    Show per-bundle health metrics — scored items, avg urgency, top tags, feed contributions.

    Args:
        bundle_id: The numeric bundle ID to inspect.

    Returns: dict with stats or error if bundle not found.
    """
    from aiwatcher_mcp.database import get_bundle_stats

    stats = await get_bundle_stats(bundle_id)
    if stats is None:
        return {"error": f"Bundle {bundle_id} not found"}
    return stats


@mcp.tool()
async def find_feeds_for_topic(ctx: Context, topic: str) -> dict:
    """
    Discover actual RSS/Atom feeds for a topic — probes URLs, verifies they return valid feeds.

    Rationale: Unlike create_bundle_from_topic which uses an LLM (may hallucinate feed URLs),
    this tool actually fetches and validates each candidate feed before returning results.

    Args:
        topic: The topic keyword (e.g. "Formula 1", "Space exploration").

    Returns: dict with bundle config and a verified `suggested_feeds` list.
    """
    from aiwatcher_mcp.bundles import find_feeds_for_topic as _find

    await ctx.info(f"Discovering feeds for topic: {topic}...")
    config = await _find(topic)
    verified = [f for f in config.get("suggested_feeds", []) if f.get("verified")]
    await ctx.info(f"Found {len(verified)} verified feeds for '{topic}'")
    return config


@mcp.tool()
async def poll_huggingface(ctx: Context) -> dict:
    """
    Poll Hugging Face for new daily papers, models, and trending repos.

    Rationale: Manually trigger HF ingestion outside the scheduled interval.
    Checks daily papers and new models by default; trending requires HF_INCLUDE_TRENDING=true.

    Returns: dict with per-category new item counts.
    """
    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface as _hf_poll

    await ctx.info("Polling Hugging Face...")
    results = await _hf_poll()
    total = sum(results.values())
    await ctx.info(f"HuggingFace poll complete: {total} new items")
    return {"total_new": total, "by_category": results}


@mcp.tool()
async def poll_readly(ctx: Context) -> dict:
    """
    Poll Readly magazines from READLY_WATCHLIST (or legacy single-page mode).

    Rationale: Manually trigger readly ingestion outside the 6h scheduler job.

    Returns: dict with new item count.
    """
    from aiwatcher_mcp.readly_ingestion import poll_readly_articles

    await ctx.info("Polling Readly watchlist...")
    count = await poll_readly_articles()
    return {"new_items": count}


@mcp.tool()
async def readly_watchlist(action: str = "get", magazines: str = "") -> dict:
    """
    Get or mutate the Readly magazine watchlist at runtime.

    action: get | set | add | remove
    magazines: comma-separated names (required for set/add/remove)

    Env READLY_WATCHLIST loads on startup; runtime changes are in-memory until restart.
    """
    from aiwatcher_mcp.readly_ingestion import (
        get_effective_readly_watchlist,
        set_runtime_readly_watchlist,
    )

    cfg = get_settings()
    current = get_effective_readly_watchlist()
    act = (action or "get").lower().strip()

    if act == "get":
        return {
            "watchlist": current,
            "count": len(current),
            "readly_enabled": cfg.readly_enabled,
            "readly_mcp_url": cfg.readly_mcp_url,
            "poll_interval_hours": cfg.readly_poll_interval_hours,
            "poll_max_articles": cfg.readly_poll_max_articles,
        }

    parts = [p.strip() for p in magazines.split(",") if p.strip()]
    if act == "set":
        if not parts:
            return {"error": "magazines required for set"}
        set_runtime_readly_watchlist(parts)
    elif act == "add":
        if not parts:
            return {"error": "magazines required for add"}
        merged = list(current)
        for part in parts:
            if part not in merged:
                merged.append(part)
        set_runtime_readly_watchlist(merged)
    elif act == "remove":
        if not parts:
            return {"error": "magazines required for remove"}
        remove_set = {p.lower() for p in parts}
        set_runtime_readly_watchlist([m for m in current if m.lower() not in remove_set])
    else:
        return {"error": f"unknown action: {action}"}

    updated = get_effective_readly_watchlist()
    return {"action": act, "watchlist": updated, "count": len(updated)}


@mcp.tool()
async def import_opml(ctx: Context, opml_xml: str) -> dict:
    """
    Import feeds from OPML XML (e.g. exported from Feedly, Inoreader, etc.).

    Args:
        opml_xml: The raw OPML file content as a string.

    Returns: dict with list of imported feed names and count.
    """
    from aiwatcher_mcp.opml import import_feeds_from_opml

    return await import_feeds_from_opml(opml_xml)


@mcp.tool()
async def scrubber_reload(ctx: Context) -> dict:
    """Reload the spam blocklist file without restarting the server.

    Reads data/spam_blocklist.txt next to the package (see scrubber.Scrubber).
    Useful after manually editing the blocklist.
    """
    Scrubber().reload()
    await ctx.info("Scrubber blocklist reloaded")
    return {"status": "reloaded"}


@mcp.tool(annotations={"readOnly": True}, version="0.1.0")
async def query_logs(
    source: str | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> dict:
    """Query the in-memory UiLog ring buffer for recent log entries.

    Filter by source (logger name), level (INFO, WARNING, ERROR, DEBUG),
    or free-text search in the message body.

    Returns: dict with filtered log entries, count, total_matching.
    """
    from aiwatcher_mcp.logging_utils import log_buffer

    items = list(log_buffer)
    if source:
        items = [i for i in items if source.lower() in i.get("name", "").lower()]
    if level:
        level_upper = level.upper()
        items = [i for i in items if i.get("level", "").upper() == level_upper]
    if search:
        q = search.lower()
        items = [i for i in items if q in i.get("message", "").lower()]

    total = len(items)
    page = items[-limit:] if limit else items
    return {"success": True, "logs": page, "count": len(page), "total_matching": total}


@mcp.tool()
async def aiwatcher_help(topic: str | None = None) -> dict:
    """AIWATCHER_HELP — Fleet pipeline, API keys, ingest, integrations, and scoring docs.

    Call with no topic for the index. Topics: fleet_pipeline, api_keys, integrations,
    alerts, scoring.

    Args:
        topic: Help section id, or omit for overview + topic list.
    """
    from aiwatcher_mcp.help_content import get_help

    return get_help(topic)


# ── Prefab UI tools ────────────────────────────────────────────────────────────

if cfg.aiwatcher_prefab_apps:

    @mcp.tool(app=True)
    async def show_dashboard_card(ctx: Context) -> PrefabApp:
        """Show AIWatcher fleet status as a rich Prefab card."""
        from prefab_ui.components import (
            Card,
            CardContent,
            Column,
            Grid,
            Heading,
            Muted,
            Separator,
        )

        from aiwatcher_mcp.database import get_stats

        stats = await get_stats()

        with Column(gap=4, css_class="p-4") as view:
            Heading("AIWatcher — Fleet Status")
            Separator()
            with Grid(columns=3, gap=3):
                for label, value, _variant in [
                    ("Active Feeds", str(stats["active_feeds"]), "secondary"),
                    ("Items Today", str(stats["items_last_24h"]), "secondary"),
                    ("Unread", str(stats["unread_items"]), "warning"),
                    ("Critical", str(stats["critical_items"]), "destructive"),
                    ("Total Items", str(stats["total_items"]), "secondary"),
                ]:
                    with Card(), CardContent(css_class="pt-4"):
                        Muted(label)
                        Heading(value)

        return PrefabApp(view=view, title="AIWatcher Fleet Status")


# ── Current AI Map ────────────────────────────────────────────────────────────


@mcp.tool()
async def currentai(
    ctx: Context,
    operation: str,
    snapshot_id: str | None = None,
    snapshot_id_b: str | None = None,
    product_query: str | None = None,
    stack_layer: str | None = None,
) -> dict:
    """
    CURRENTAI — Ingest, diff, and query the Current AI "AI Stack Gap Map" dataset.

    Data source: currentai-org/os-ai-map (GitHub). Fetches the compiled
    stack_map/repos.csv pinned to a specific commit hash, normalises into
    an internal JSON schema, stores versioned snapshots, and diffs between
    them to detect concentration risk and sovereignty-relevant changes.

    [RATIONALE]
    Consolidates Current AI map operations into a single portmanteau tool.
    A separate tool for each operation would bloat the tool registry; the
    operation enum acts as a built-in catalog.

    ## Operations
    - refresh: Fetch latest upstream CSV, store snapshot if commit differs.
      Auto-diffs against previous and writes summary to advanced-memory.
      Returns {new_snapshot, commit, product_count}.
    - diff: Compare two most recent snapshots (or two given snapshot_ids).
      Returns added, removed, openness_reclassified, stage_changed,
      adoption_changed. Empty diff is explicit and valid.
    - query: Lookup by product name (case-insensitive substring) or
      stack_layer filter.
    - gap_report: Per stack_layer counts of open / open-ish / closed products.
    - check_dependency: Run watchlist against latest snapshot. Flags
      concentration risk (< 3 fully-open products in the entry's layer)
      and status changes since the previous snapshot.

    ## Return Format
    {"success": bool, "message": str, "data": {...}}

    ## Examples
    currentai(operation="refresh")
    currentai(operation="diff")
    currentai(operation="query", product_query="fastmcp")
    currentai(operation="query", stack_layer="product_ux")
    currentai(operation="gap_report")
    currentai(operation="check_dependency")
    """
    from aiwatcher_mcp.currentai import (
        check_dependency_risk,
        diff_snapshots,
        fetch_normalized_products,
        gap_report,
        list_snapshots,
        load_snapshot,
        save_snapshot,
    )
    from aiwatcher_mcp.currentai.store import get_latest

    op = operation.strip().lower()

    if op == "refresh":
        await ctx.info("Fetching Current AI dataset...")
        try:
            records, commit_sha = await fetch_normalized_products()
        except Exception as exc:
            return {
                "success": False,
                "operation": "refresh",
                "error": str(exc),
                "message": "Upstream unreachable — retry later.",
            }

        latest_ptr = get_latest()
        if latest_ptr and latest_ptr.get("commit", "")[:7] == commit_sha[:7]:
            return {
                "success": True,
                "operation": "refresh",
                "new_snapshot": False,
                "commit": commit_sha[:8],
                "product_count": len(records),
                "message": "Already at latest commit.",
            }

        diff = None
        if latest_ptr:
            prev = load_snapshot()
            if prev:
                prev_data, _ = prev
                curr_data = {
                    "commit": commit_sha,
                    "short_commit": commit_sha[:8],
                    "products": records,
                }
                diff = diff_snapshots(prev_data, curr_data)

        path = save_snapshot(records, commit_sha)
        await ctx.info(f"Stored {len(records)} products from {commit_sha[:8]}")

        if diff and not diff.get("is_empty", True):
            await ctx.info("Writing diff briefing to advanced-memory...")
            from aiwatcher_mcp.config import get_settings as _get_cfg
            _cfg = _get_cfg()
            if _cfg.memops_url:
                import asyncio as _asyncio
                _asyncio.ensure_future(_write_note_async(diff))

        return {
            "success": True,
            "operation": "refresh",
            "new_snapshot": True,
            "commit": commit_sha[:8],
            "product_count": len(records),
            "path": path,
            "diff": diff,
            "message": f"New snapshot: {len(records)} products at {commit_sha[:8]}.",
        }

    if op == "diff":
        if snapshot_id and snapshot_id_b:
            a = load_snapshot(snapshot_id)
            b = load_snapshot(snapshot_id_b)
        else:
            snaps = list_snapshots()
            if len(snaps) < 2:
                return {
                    "success": False,
                    "operation": "diff",
                    "error": "Need >= 2 snapshots. Run refresh first.",
                }
            a = load_snapshot(snaps[-2])
            b = load_snapshot(snaps[-1])

        if not a or not b:
            return {
                "success": False,
                "operation": "diff",
                "error": "Snapshot not found.",
            }

        older_data, _ = a
        newer_data, _ = b
        result = diff_snapshots(older_data, newer_data)
        result["success"] = True
        result["operation"] = "diff"
        return result

    if op == "query":
        loaded = load_snapshot(snapshot_id)
        if not loaded:
            return {
                "success": False,
                "operation": "query",
                "error": "No snapshot. Run refresh first.",
            }
        data, _ = loaded
        products = data.get("products", [])
        if product_query:
            q = product_query.lower()
            matches = [p for p in products if q in p.get("product", "").lower()]
        elif stack_layer:
            matches = [p for p in products if p.get("stack_layer") == stack_layer]
        else:
            matches = products[:50]
        return {
            "success": True,
            "operation": "query",
            "results": matches,
            "count": len(matches),
        }

    if op == "gap_report":
        loaded = load_snapshot(snapshot_id)
        if not loaded:
            return {
                "success": False,
                "operation": "gap_report",
                "error": "No snapshot. Run refresh first.",
            }
        data, _ = loaded
        report = gap_report(data.get("products", []))
        report["success"] = True
        report["operation"] = "gap_report"
        return report

    if op == "check_dependency":
        loaded = load_snapshot(snapshot_id)
        if not loaded:
            return {
                "success": False,
                "operation": "check_dependency",
                "error": "No snapshot. Run refresh first.",
            }
        data, name = loaded

        snaps = list_snapshots()
        prev = None
        if len(snaps) >= 2:
            p = load_snapshot(snaps[-2])
            if p:
                prev = p[0]

        result = check_dependency_risk(data.get("products", []), prev)
        flagged = [r for r in result if r.get("flagged")]
        return {
            "success": True,
            "operation": "check_dependency",
            "flags": result,
            "flagged_count": len(flagged),
            "snapshot": name,
        }

    return {
        "success": False,
        "operation": op,
        "error": f"Unknown operation '{op}'. Valid: refresh, diff, query, gap_report, check_dependency",
    }


async def _write_note_async(diff: dict) -> None:
    """Async helper: POST diff summary to advanced-memory-mcp."""
    memops_url = cfg.memops_url
    if not memops_url:
        log.debug("memops_url not configured — skipping currentai briefing note")
        return

    from datetime import UTC, datetime

    iso_date = datetime.now(UTC).strftime("%Y-%m-%d")
    title = f"currentai-diff-{iso_date}"
    summary = diff.get("summary", "No changes")
    old_commit = diff.get("old_commit", "?")[:8]
    new_commit = diff.get("new_commit", "?")[:8]

    content = (
        f"# Current AI Map Diff — {iso_date}\n\n"
        f"## Summary\n{summary}\n\n"
        f"## Details\n"
        f"- Added: {len(diff.get('added', []))} products\n"
        f"- Removed: {len(diff.get('removed', []))} products\n"
        f"- Openness reclassified: {len(diff.get('openness_reclassified', []))}\n"
        f"- Maturity changed: {len(diff.get('stage_changed', []))}\n"
        f"- Adoption changed: {len(diff.get('adoption_changed', []))}\n\n"
        f"Commits: {old_commit} → {new_commit}"
    )

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{memops_url}/api/v1/notes",
                json={
                    "title": title,
                    "content": content,
                    "tags": ["aiwatcher", "currentai", "dataset-diff", "low"],
                },
            )
            if resp.status_code < 400:
                log.info("currentai briefing note written to advanced-memory: %s", title)
            else:
                log.warning("advanced-memory rejected note: HTTP %s — %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        log.warning("Failed to write currentai briefing note to advanced-memory: %s", exc)


# ── Prompts ────────────────────────────────────────────────────────────────────


@mcp.prompt()
async def breaking_news_brief() -> str:
    """Generate a verbal breaking news brief for Sandra."""
    from aiwatcher_mcp.database import get_recent_items

    items = await get_recent_items(hours=2, limit=5)
    if not items:
        return "No breaking items in the last 2 hours."
    lines = "\n".join(
        f"- [{i.get('urgency_score', 0):.0f}/10] {i['title']} ({i.get('feed_name', '')})"
        for i in items
    )
    return f"Last 2 hours — top items:\n{lines}"


@mcp.prompt()
async def portfolio_impact_analysis() -> str:
    """Prompt template for analysing portfolio impact of current AI news."""
    from aiwatcher_mcp.database import get_recent_items

    items = await get_recent_items(hours=24, limit=20)
    titles = "\n".join(f"- {i['title']}" for i in items)
    return f"""You are Sandra's portfolio analyst. Assess these AI news items for
portfolio impact (AI stocks, tool subscriptions, infra decisions):

{titles}

Identify: (1) immediate actions needed, (2) watch list additions,
(3) budget reallocation signals. Be direct, no hype."""


# ── Resources ─────────────────────────────────────────────────────────────────


@mcp.resource("aiwatcher://feeds/list")
async def resource_feeds() -> str:
    from aiwatcher_mcp.database import get_feeds

    feeds = await get_feeds()
    return json.dumps(feeds, indent=2, default=str)


@mcp.resource("aiwatcher://stats")
async def resource_stats() -> str:
    from aiwatcher_mcp.database import get_stats

    stats = await get_stats()
    return json.dumps(stats, indent=2)


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    import asyncio

    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))
    asyncio.run(mcp.run_stdio_async(show_banner=False))


if __name__ == "__main__":
    main()
