"""Tests for calibre_integration.py — mocked calibre-mcp REST."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_ingest_digest_disabled(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("CALIBRE_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.calibre_integration import ingest_digest_to_calibre

    ok = await ingest_digest_to_calibre(
        {"html_body": "<p>x</p>", "text_body": "x", "item_ids": [1]}
    )
    assert ok is False


@pytest.mark.asyncio
async def test_ingest_digest_posts_html_file(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("CALIBRE_ENABLED", "true")
    monkeypatch.setenv("CALIBRE_MCP_URL", "http://calibre.test")
    cfg_mod._settings = None

    route = None

    def check_request(request):
        nonlocal route
        route = request
        return Response(200, json={"success": True, "book_id": 42})

    from aiwatcher_mcp.database import get_db

    async with get_db() as db:
        await db.execute(
            "INSERT INTO items (feed_id, guid, title) VALUES (1, 'cal-1', 'One')"
        )
        await db.execute(
            "INSERT INTO items (feed_id, guid, title) VALUES (1, 'cal-2', 'Two')"
        )
        await db.commit()
        async with db.execute("SELECT id FROM items WHERE guid='cal-1'") as c1:
            id_a = (await c1.fetchone())["id"]
        async with db.execute("SELECT id FROM items WHERE guid='cal-2'") as c2:
            id_b = (await c2.fetchone())["id"]

    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r"http://calibre\.test/api/books").mock(
            side_effect=check_request
        )
        from aiwatcher_mcp.calibre_integration import ingest_digest_to_calibre

        ok = await ingest_digest_to_calibre(
            {
                "subject": "Daily",
                "html_body": "<h1>Digest</h1>",
                "text_body": "",
                "item_ids": [id_a, id_b],
            }
        )

    assert ok is True
    assert route is not None

    async with get_db() as db, db.execute(
        "SELECT sent_calibre FROM items WHERE id IN (?, ?)",
        (id_a, id_b),
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 2
    assert all(r["sent_calibre"] == 1 for r in rows)
