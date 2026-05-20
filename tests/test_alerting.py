"""
Integration tests for alerting.py — robofang POSTs, TTS, process_alerts flow.
External HTTP mocked with respx; DB uses temp file.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response


@pytest.fixture(autouse=True)
async def fresh_db():
    from aiwatcher_mcp.database import get_db
    async with get_db() as db:
        await db.executescript(
            "DROP TABLE IF EXISTS digests;"
            "DROP TABLE IF EXISTS items;"
            "DROP TABLE IF EXISTS feeds;"
        )
        await db.commit()
    from aiwatcher_mcp.database import init_db
    await init_db()


async def _insert_critical_item(urgency: float = 9.5) -> int:
    from aiwatcher_mcp.database import get_db

    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO feeds(name, url) VALUES (?,?)",
            ("Alert Test Feed", "https://example.com/rss"),
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM feeds WHERE url=?", ("https://example.com/rss",)
        ) as c:
            (feed_id,) = await c.fetchone()

        await db.execute(
            """INSERT INTO items
               (feed_id, guid, title, url, urgency_score, relevance_score,
                distilled_summary, tags, distilled_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
            (
                feed_id,
                "alert-guid-001",
                "BREAKING: Major AI acquisition",
                "https://example.com/breaking",
                urgency,
                9.0,
                "A major AI company was acquired today in a landmark deal.",
                json.dumps(["acquisition", "breaking"]),
            ),
        )
        await db.commit()
        async with db.execute("SELECT id FROM items WHERE guid='alert-guid-001'") as c:
            (item_id,) = await c.fetchone()
        return item_id


@pytest.mark.asyncio
async def test_fire_robofang_alert_success():
    from aiwatcher_mcp.alerting import fire_robofang_alert

    item = {
        "id": 1,
        "title": "BREAKING: Claude 5 acquisition",
        "url": "https://example.com/1",
        "urgency_score": 9.8,
        "distilled_summary": "Summary text.",
        "tags": json.dumps(["acquisition"]),
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.post("http://localhost:10871/api/v1/events").mock(
            return_value=Response(200, json={"ok": True})
        )
        result = await fire_robofang_alert(item)

    assert result is True


@pytest.mark.asyncio
async def test_fire_robofang_alert_failure_returns_false():
    from aiwatcher_mcp.alerting import fire_robofang_alert

    item = {
        "id": 1,
        "title": "Test alert",
        "url": "https://example.com/1",
        "urgency_score": 9.0,
        "distilled_summary": None,
        "tags": "[]",
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.post("http://localhost:10871/api/v1/events").mock(
            return_value=Response(503, text="Service Unavailable")
        )
        result = await fire_robofang_alert(item)

    assert result is False


@pytest.mark.asyncio
async def test_fire_robofang_disabled_returns_false(monkeypatch: pytest.MonkeyPatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ROBOFANG_ENABLED", "false")
    cfg_mod._settings = None

    try:
        from aiwatcher_mcp.alerting import fire_robofang_alert
        item = {"id": 1, "title": "x", "url": "", "urgency_score": 10.0,
                "distilled_summary": None, "tags": "[]"}
        with respx.mock(assert_all_called=False):
            result = await fire_robofang_alert(item)
        assert result is False
    finally:
        monkeypatch.setenv("ROBOFANG_ENABLED", "true")
        cfg_mod._settings = None


@pytest.mark.asyncio
async def test_process_alerts_fires_for_critical_items():
    await _insert_critical_item(urgency=9.5)

    with respx.mock(assert_all_called=False) as mock:
        mock.post("http://localhost:10871/api/v1/events").mock(
            return_value=Response(200, json={"ok": True})
        )
        mock.post("http://localhost:10895/api/v1/tts").mock(
            return_value=Response(200, json={"ok": True})
        )
        from aiwatcher_mcp.alerting import process_alerts
        alerted = await process_alerts()

    assert len(alerted) == 1
    assert "BREAKING" in alerted[0]


@pytest.mark.asyncio
async def test_process_alerts_empty_when_below_threshold():
    await _insert_critical_item(urgency=5.0)

    with respx.mock(assert_all_called=False):
        from aiwatcher_mcp.alerting import process_alerts
        alerted = await process_alerts()

    assert alerted == []


@pytest.mark.asyncio
async def test_process_alerts_no_duplicate_alerts():
    from aiwatcher_mcp.database import get_db

    item_id = await _insert_critical_item(urgency=9.5)
    async with get_db() as db:
        await db.execute("UPDATE items SET sent_robofang=1 WHERE id=?", (item_id,))
        await db.commit()

    with respx.mock(assert_all_called=False):
        from aiwatcher_mcp.alerting import process_alerts
        alerted = await process_alerts()

    assert alerted == []
