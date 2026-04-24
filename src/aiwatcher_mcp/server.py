"""
FastMCP 3.2 MCP server — tools, prompts, resources, Prefab UI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import fastmcp
from fastmcp import FastMCP, Context
from prefab_ui import PrefabApp, ToolResult

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp import __version__

log = logging.getLogger(__name__)
cfg = get_settings()

mcp = FastMCP(
    name=cfg.server_name,
    version=__version__,
    description="AI news ingestion, distillation, and alert system for Sandra's fleet",
)


# ── Lifespan probe ─────────────────────────────────────────────────────────────

@mcp.on_startup()
async def startup() -> None:
    from aiwatcher_mcp.database import init_db
    await init_db()
    log.info("aiwatcher-mcp startup: DB ready")


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
async def get_top_items(ctx: Context, limit: int = 10, hours: int = 24) -> dict:
    """
    Get top-scored items from the last N hours, sorted by urgency.

    Args:
        limit: Number of items to return (default 10).
        hours: Lookback window (default 24).

    Returns: dict with list of top items.
    """
    from aiwatcher_mcp.database import get_recent_items
    items = await get_recent_items(hours=hours, limit=limit)
    # Slim down for MCP response
    slim = [
        {
            "title": i["title"],
            "source": i.get("feed_name", ""),
            "url": i.get("url", ""),
            "urgency": i.get("urgency_score"),
            "relevance": i.get("relevance_score"),
            "summary": i.get("distilled_summary") or i.get("summary", "")[:200],
            "tags": json.loads(i.get("tags") or "[]"),
        }
        for i in items
    ]
    return {"items": slim, "count": len(slim), "hours": hours}


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


# ── Prefab UI tools ────────────────────────────────────────────────────────────

if cfg.aiwatcher_prefab_apps:

    @mcp.tool(app=True)
    async def show_dashboard_card(ctx: Context) -> ToolResult:
        """Show AIWatcher fleet status as a rich Prefab card."""
        from aiwatcher_mcp.database import get_stats
        stats = await get_stats()
        app = PrefabApp(
            title="AIWatcher — Fleet Status",
            sections=[
                {
                    "type": "stats_grid",
                    "items": [
                        {"label": "Active Feeds", "value": stats["active_feeds"], "color": "blue"},
                        {"label": "Total Items", "value": stats["total_items"], "color": "zinc"},
                        {"label": "Unread", "value": stats["unread_items"], "color": "amber"},
                        {"label": "Critical", "value": stats["critical_items"], "color": "red"},
                        {"label": "Last 24h", "value": stats["items_last_24h"], "color": "green"},
                    ],
                }
            ],
        )
        return ToolResult(
            content=f"AIWatcher: {stats['active_feeds']} feeds, {stats['unread_items']} unread, {stats['critical_items']} critical",
            structured_content=app,
        )


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
    mcp.run()


if __name__ == "__main__":
    main()
