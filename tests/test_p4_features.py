"""Tests for v0.1.6 P4 features: metrics, trends, fleet events, feed quality."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint():
    from aiwatcher_mcp.api import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/metrics")
    assert resp.status_code == 200
    assert "aiwatcher_items_total" in resp.text


@pytest.mark.asyncio
async def test_get_tag_trends_empty():
    from aiwatcher_mcp.trends import get_tag_trends

    trends = await get_tag_trends(days=7)
    assert isinstance(trends, list)


@pytest.mark.asyncio
async def test_ingest_fleet_event():
    from aiwatcher_mcp.fleet_events import ingest_fleet_event

    r = await ingest_fleet_event(
        title="Fritz merged PR #42",
        summary="Fleet agent release",
        source="fleet-agent",
        urgency_hint=7.5,
    )
    assert r["success"] is True
    assert r["inserted"] is True


@pytest.mark.asyncio
async def test_feed_quality_flags():
    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.feed_quality import enrich_feeds_with_quality

    async with get_db() as db:
        await db.execute(
            """INSERT INTO items (feed_id, guid, title, urgency_score, relevance_score, distilled_at)
               VALUES (1, 'q1', 'Low', 1.0, 1.0, datetime('now'))"""
        )
        await db.execute(
            """INSERT INTO items (feed_id, guid, title, urgency_score, relevance_score, distilled_at)
               VALUES (1, 'q2', 'Low2', 1.5, 1.0, datetime('now'))"""
        )
        await db.execute(
            """INSERT INTO items (feed_id, guid, title, urgency_score, relevance_score, distilled_at)
               VALUES (1, 'q3', 'Low3', 1.2, 1.0, datetime('now'))"""
        )
        await db.execute(
            """INSERT INTO items (feed_id, guid, title, urgency_score, relevance_score, distilled_at)
               VALUES (1, 'q4', 'Low4', 1.8, 1.0, datetime('now'))"""
        )
        await db.execute(
            """INSERT INTO items (feed_id, guid, title, urgency_score, relevance_score, distilled_at)
               VALUES (1, 'q5', 'Low5', 1.1, 1.0, datetime('now'))"""
        )
        await db.commit()

    async with (
        get_db() as db,
        db.execute("SELECT id, name, url, feed_type, enabled FROM feeds WHERE id=1") as cur,
    ):
        feeds = [dict(r) for r in await cur.fetchall()]
    enriched = await enrich_feeds_with_quality(feeds)
    assert enriched[0]["quality_flag"] == "low_signal"


def test_portfolio_match():
    from aiwatcher_mcp.portfolio_watch import portfolio_match

    hits = portfolio_match("Anthropic ships FastMCP 3.2 for the MCP fleet")
    assert "fastmcp" in hits or "anthropic" in hits
