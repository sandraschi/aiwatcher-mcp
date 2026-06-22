"""
FastMCP 3.2 MCP server — tools, prompts, resources, Prefab UI.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastmcp.server import create_proxy
from fastmcp.server.context import Context
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
        name=config["name"],
        topic=topic,
        system_prompt=config["system_prompt"]
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
        "system_prompt": config["system_prompt"]
    }
    fleet_bundles.append(new_bundle)
    save_fleet_bundles(fleet_bundles)
    
    return {
        "id": bundle_id,
        "fleet_id": new_bundle["id"],
        "name": config["name"],
        "topic": topic,
        "system_prompt": config["system_prompt"],
        "suggested_feeds": config.get("suggested_feeds", [])
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
async def get_top_items(ctx: Context, bundle_id: int | None = None, limit: int = 10, hours: int = 24) -> dict:
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

    async with get_db() as db, db.execute(
        """SELECT id, name, url, feed_type, enabled, last_fetched,
                  consecutive_failures, last_error
           FROM feeds ORDER BY consecutive_failures DESC, name"""
    ) as cur:
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
                    ("Active Feeds",  str(stats["active_feeds"]),   "secondary"),
                    ("Items Today",   str(stats["items_last_24h"]), "secondary"),
                    ("Unread",        str(stats["unread_items"]),   "warning"),
                    ("Critical",      str(stats["critical_items"]), "destructive"),
                    ("Total Items",   str(stats["total_items"]),    "secondary"),
                ]:
                    with Card(), CardContent(css_class="pt-4"):
                        Muted(label)
                        Heading(value)

        return PrefabApp(view=view, title="AIWatcher Fleet Status")


# ── Prompts ────────────────────────────────────────────────────────────────────

@mcp.prompt()
async def breaking_news_brief() -> str:
    """Generate a verbal breaking news brief for Sandra."""
    from aiwatcher_mcp.database import get_recent_items
    items = await get_recent_items(hours=2, limit=5)
    if not items:
        return "No breaking items in the last 2 hours."
    lines = "\n".join(
        f"- [{i.get('urgency_score', 0):.0f}/10] {i['title']} ({i.get('feed_name','')})"
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
