"""
Unit tests for database.py — schema, CRUD helpers, default feed seeding.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    from aiwatcher_mcp.database import get_db

    async with get_db() as db, db.execute("SELECT name FROM sqlite_master WHERE type='table'") as c:
        tables = {row[0] for row in await c.fetchall()}

    assert "feeds" in tables
    assert "items" in tables
    assert "digests" in tables


@pytest.mark.asyncio
async def test_init_db_seeds_default_feeds():
    from aiwatcher_mcp.bundle_presets import IDE_HOST_FEEDS
    from aiwatcher_mcp.database import DEFAULT_FEEDS, get_db

    async with get_db() as db, db.execute("SELECT COUNT(*) FROM feeds") as c:
        (count,) = await c.fetchone()

    assert count >= len(DEFAULT_FEEDS)

    async with get_db() as db, db.execute("SELECT url FROM feeds") as c:
        urls = {row[0] for row in await c.fetchall()}
    for _name, url, _ftype in IDE_HOST_FEEDS:
        assert url in urls


@pytest.mark.asyncio
async def test_upsert_item_inserts_new():
    from aiwatcher_mcp.database import upsert_item

    inserted = await upsert_item(
        1,
        {
            "guid": "test-guid-upsert",
            "title": "Test Item",
            "url": "https://example.com/test",
            "summary": "Test summary",
            "content_html": None,
            "published_at": None,
            "tags": ["test"],
        },
    )
    assert inserted is True


@pytest.mark.asyncio
async def test_upsert_item_deduplicates():
    from aiwatcher_mcp.database import upsert_item

    item = {
        "guid": "test-guid-dup",
        "title": "Dup Item",
        "url": "https://example.com/dup",
        "summary": None,
        "content_html": None,
        "published_at": None,
        "tags": [],
    }
    first = await upsert_item(1, item)
    second = await upsert_item(1, item)
    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_get_undistilled_items_returns_unscored():
    from aiwatcher_mcp.database import get_undistilled_items, upsert_item

    await upsert_item(
        1,
        {
            "guid": "undistilled-001",
            "title": "Unscored Item",
            "url": "https://example.com/u",
            "summary": "summary",
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )

    items = await get_undistilled_items(limit=10)
    guids = [i["guid"] for i in items]
    assert "undistilled-001" in guids


@pytest.mark.asyncio
async def test_update_item_scores_sets_fields():
    import json

    from aiwatcher_mcp.database import get_db, update_item_scores, upsert_item

    await upsert_item(
        1,
        {
            "guid": "score-test-001",
            "title": "Score Me",
            "url": "https://example.com/s",
            "summary": None,
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )

    async with (
        get_db() as db,
        db.execute("SELECT id FROM items WHERE guid='score-test-001'") as cur,
    ):
        (item_id,) = await cur.fetchone()

    await update_item_scores(
        item_id=item_id,
        relevance=8.5,
        urgency=7.0,
        summary="Scored summary.",
        tags=["ai", "test"],
    )

    async with (
        get_db() as db,
        db.execute(
            "SELECT relevance_score, urgency_score, distilled_summary, tags, distilled_at "
            "FROM items WHERE id=?",
            (item_id,),
        ) as c,
    ):
        row = await c.fetchone()

    assert row[0] == 8.5
    assert row[1] == 7.0
    assert row[2] == "Scored summary."
    assert json.loads(row[3]) == ["ai", "test"]
    assert row[4] is not None


@pytest.mark.asyncio
async def test_get_alert_candidates_filters_by_threshold():
    from aiwatcher_mcp.database import get_alert_candidates, get_db, upsert_item

    await upsert_item(
        1,
        {
            "guid": "high-urgency-001",
            "title": "Breaking",
            "url": "https://example.com/b",
            "summary": None,
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )

    async with get_db() as db:
        async with db.execute("SELECT id FROM items WHERE guid='high-urgency-001'") as c:
            (item_id,) = await c.fetchone()
        await db.execute("UPDATE items SET urgency_score=9.5 WHERE id=?", (item_id,))
        await db.commit()

    candidates = await get_alert_candidates(threshold=8.5)
    assert any(c["id"] == item_id for c in candidates)

    low_candidates = await get_alert_candidates(threshold=9.9)
    assert not any(c["id"] == item_id for c in low_candidates)


@pytest.mark.asyncio
async def test_get_stats_returns_expected_keys():
    from aiwatcher_mcp.database import get_stats

    stats = await get_stats()
    assert "active_feeds" in stats
    assert "total_items" in stats
    assert "unread_items" in stats
    assert "critical_items" in stats
    assert "items_last_24h" in stats
    assert stats["active_feeds"] > 0


@pytest.mark.asyncio
async def test_ensure_ide_host_signal_bundle():
    from aiwatcher_mcp.bundle_presets import IDE_HOST_BUNDLE, IDE_HOST_FEEDS
    from aiwatcher_mcp.database import ensure_fleet_bundle_presets, get_bundle_feeds, get_bundles

    await ensure_fleet_bundle_presets()

    bundles = await get_bundles()
    ide = [b for b in bundles if b["name"] == IDE_HOST_BUNDLE["name"]]
    assert len(ide) == 1
    assert ide[0]["alert_threshold"] == IDE_HOST_BUNDLE["alert_threshold"]

    feeds = await get_bundle_feeds(ide[0]["id"])
    linked_urls = {f["url"] for f in feeds}
    for _name, url, _ftype in IDE_HOST_FEEDS:
        assert url in linked_urls


@pytest.mark.asyncio
async def test_get_bundle_stats_returns_metrics():
    from aiwatcher_mcp.database import get_bundle_stats, get_bundles

    bundles = await get_bundles(enabled_only=True)
    assert len(bundles) >= 1

    stats = await get_bundle_stats(bundles[0]["id"])
    assert stats is not None
    assert stats["bundle_id"] == bundles[0]["id"]
    assert "name" in stats
    assert "items_scored" in stats
    assert "avg_urgency" in stats
    assert "top_tags" in stats
    assert "source_feeds" in stats


@pytest.mark.asyncio
async def test_get_bundle_stats_returns_none_for_missing():
    from aiwatcher_mcp.database import get_bundle_stats

    stats = await get_bundle_stats(99999)
    assert stats is None


@pytest.mark.asyncio
async def test_find_similar_item_detects_near_duplicate():
    from aiwatcher_mcp.database import _find_similar_item, upsert_item

    await upsert_item(
        1,
        {
            "guid": "dedup-original",
            "title": "Claude 5 Released: Major AI Capability Jump Announced",
            "url": "https://example.com/claude-5-original",
            "summary": None,
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )

    similar = await _find_similar_item("Claude 5 Released — Major AI capability jump announced", 2)
    assert similar is not None
    assert "Claude 5" in similar["title"]


@pytest.mark.asyncio
async def test_find_similar_item_returns_none_for_different_titles():
    from aiwatcher_mcp.database import _find_similar_item, upsert_item

    await upsert_item(
        1,
        {
            "guid": "dedup-unique",
            "title": "Claude 5 Released",
            "url": "https://example.com/claude5",
            "summary": None,
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )

    similar = await _find_similar_item("World Cup Results: Argentina Wins", 2)
    assert similar is None
