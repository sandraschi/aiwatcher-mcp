"""Tests for interests.json → bundle_feeds sync."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_sync_links_arxiv_feed_to_china_bundle(tmp_path, monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    interests = {
        "interests": [
            {
                "name": "China Open Weights",
                "topic": "test",
                "system_prompt": "Score JSON only.",
                "alert_threshold": 8.0,
                "enabled": True,
                "feed_patterns": ["ArXiv: cs.AI", "Fleet Events"],
            }
        ]
    }
    path = tmp_path / "interests.json"
    path.write_text(json.dumps(interests), encoding="utf-8")
    monkeypatch.setenv("INTERESTS_JSON_PATH", str(path))
    cfg_mod._settings = None

    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.fleet_events import ingest_fleet_event
    from aiwatcher_mcp.update_interests import sync_interests

    async with get_db() as db:
        await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            ("ArXiv: cs.AI", "cs.AI", "arxiv"),
        )
        await db.commit()

    await sync_interests(path)

    async with get_db() as db, db.execute(
        """SELECT b.name, f.name AS feed_name
           FROM bundle_feeds bf
           JOIN bundles b ON b.id = bf.bundle_id
           JOIN feeds f ON f.id = bf.feed_id"""
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    assert any(r["feed_name"] == "ArXiv: cs.AI" for r in rows)

    await ingest_fleet_event(title="code drop", source="arxiv-codehunt", urgency_hint=9.0)

    async with get_db() as db, db.execute(
        "SELECT name FROM feeds WHERE feed_type='fleet'"
    ) as cur:
        assert await cur.fetchone() is not None

    await sync_interests(path)

    async with get_db() as db, db.execute(
        """SELECT f.name FROM bundle_feeds bf
           JOIN feeds f ON f.id = bf.feed_id
           JOIN bundles b ON b.id = bf.bundle_id
           WHERE b.name = 'China Open Weights'"""
    ) as cur:
        linked = {r["name"] for r in await cur.fetchall()}

    assert "ArXiv: cs.AI" in linked
    assert "Fleet Events" in linked
