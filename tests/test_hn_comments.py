"""Tests for the on-demand HN comment drill-down.

GET /api/hn/item/{id}/comments reads one thread from Algolia (mocked with
respx), sanitizes comment HTML, depth-limits the tree, caches in memory,
and never writes comments to the DB. Also covers the structured hn_id on
/api/hn/dashboard items.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx
from httpx import ASGITransport, AsyncClient

ITEM_URL = "https://hn.algolia.com/api/v1/items/49953495"

THREAD = {
    "id": 49953495,
    "type": "story",
    "title": "Strata: 125B on a 4090",
    "url": "https://github.com/Niko1221/Strata",
    "author": "snehesht",
    "points": 781,
    "created_at": "2026-10-04T12:51:53Z",
    "text": None,
    "children": [
        {
            "id": 1,
            "type": "comment",
            "author": "alice",
            "created_at": "2026-10-04T13:00:00Z",
            "text": (
                "<p>Nice &amp; fast<script>alert(1)</script>"
                '<a href="https://example.com/x" onclick="evil()">link</a>'
                '<a href="javascript:alert(2)">bad</a>'
                '<img src=x onerror="alert(3)"></p>'
            ),
            "children": [
                {
                    "id": 2,
                    "type": "comment",
                    "author": "bob",
                    "created_at": "2026-10-04T13:05:00Z",
                    "text": "<i>agreed</i>",
                    "children": [],
                }
            ],
        },
        # deleted leaf: pruned
        {"id": 3, "type": "comment", "author": None, "text": None, "children": []},
        # deleted parent with a live reply: kept as [deleted]
        {
            "id": 4,
            "type": "comment",
            "author": None,
            "text": None,
            "children": [
                {"id": 5, "type": "comment", "author": "carol", "text": "<p>still here</p>"}
            ],
        },
    ],
}


def _client() -> AsyncClient:
    from aiwatcher_mcp.api import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture(autouse=True)
def _clear_cache():
    import aiwatcher_mcp.hn_ingestion as hn

    hn._COMMENTS_CACHE.clear()
    yield
    hn._COMMENTS_CACHE.clear()


def test_sanitize_strips_scripts_handlers_and_bad_schemes():
    from aiwatcher_mcp.hn_ingestion import sanitize_comment_html

    out = sanitize_comment_html(THREAD["children"][0]["text"])
    assert "<script" not in out and "alert(1)" not in out
    assert "onclick" not in out and "onerror" not in out and "<img" not in out
    assert "javascript:" not in out
    assert "bad" in out  # text of the dropped link survives as plain text
    assert '<a href="https://example.com/x" target="_blank"' in out
    assert "Nice &amp; fast" in out
    assert sanitize_comment_html(None) == ""
    # unclosed anchor gets closed
    assert sanitize_comment_html('<a href="https://a.b">x').endswith("</a>")


@pytest.mark.asyncio
async def test_comments_endpoint_returns_trimmed_tree():
    with respx.mock(assert_all_called=True) as mock:
        mock.get(ITEM_URL).respond(json=THREAD)
        async with _client() as c:
            resp = await c.get("/api/hn/item/49953495/comments")

    assert resp.status_code == 200
    data = resp.json()
    assert data["hn_url"] == "https://news.ycombinator.com/item?id=49953495"
    assert data["title"] == THREAD["title"]
    assert [n["id"] for n in data["comments"]] == [1, 4]
    first = data["comments"][0]
    assert first["author"] == "alice"
    assert set(first) == {"id", "author", "created_at", "text", "children", "truncated"}
    assert first["children"][0]["text"] == "<i>agreed</i>"
    assert data["comments"][1]["author"] == "[deleted]"
    assert data["comments"][1]["children"][0]["author"] == "carol"
    assert data["comment_count"] == 4


@pytest.mark.asyncio
async def test_comments_endpoint_depth_limit(monkeypatch):
    import aiwatcher_mcp.hn_ingestion as hn

    monkeypatch.setattr(hn, "_COMMENTS_MAX_DEPTH", 1)
    with respx.mock() as mock:
        mock.get(ITEM_URL).respond(json=THREAD)
        async with _client() as c:
            data = (await c.get("/api/hn/item/49953495/comments")).json()

    first = data["comments"][0]
    assert first["children"] == []
    assert first["truncated"] is True


@pytest.mark.asyncio
async def test_comments_endpoint_caches_and_refresh_bypasses():
    with respx.mock() as mock:
        route = mock.get(ITEM_URL).respond(json=THREAD)
        async with _client() as c:
            await c.get("/api/hn/item/49953495/comments")
            await c.get("/api/hn/item/49953495/comments")
            assert route.call_count == 1
            await c.get("/api/hn/item/49953495/comments?refresh=1")
            assert route.call_count == 2


@pytest.mark.asyncio
async def test_comments_endpoint_errors():
    with respx.mock() as mock:
        mock.get("https://hn.algolia.com/api/v1/items/1").respond(status_code=404)
        mock.get("https://hn.algolia.com/api/v1/items/2").respond(status_code=503)
        async with _client() as c:
            bad = await c.get("/api/hn/item/abc/comments")
            missing = await c.get("/api/hn/item/1/comments")
            upstream = await c.get("/api/hn/item/2/comments")

    assert bad.status_code == 400
    assert missing.status_code == 404
    assert upstream.status_code == 502
    assert "error" in upstream.json()


@pytest.mark.asyncio
async def test_comments_are_not_persisted(fresh_db):
    from aiwatcher_mcp.database import get_db

    with respx.mock() as mock:
        mock.get(ITEM_URL).respond(json=THREAD)
        async with _client() as c:
            assert (await c.get("/api/hn/item/49953495/comments")).status_code == 200

    async with get_db() as db, db.execute("SELECT COUNT(*) AS n FROM items") as cur:
        row = await cur.fetchone()
    assert row["n"] == 0


@pytest.mark.asyncio
async def test_dashboard_items_carry_hn_id(fresh_db):
    from aiwatcher_mcp.database import upsert_item
    from aiwatcher_mcp.hn_ingestion import _get_or_create_hn_feed

    feed_id = await _get_or_create_hn_feed("HN Front Page", "https://hnrss.org/frontpage")
    await upsert_item(
        feed_id,
        {
            "guid": "hn:49953495",
            "title": "Strata",
            "url": "https://github.com/Niko1221/Strata",
            "summary": "HN: 781 points, 350 comments, by snehesht.",
            "content_html": None,
            "published_at": datetime.now(UTC).isoformat(),
            "tags": ["hn", "hn-frontpage"],
        },
    )
    async with _client() as c:
        data = (await c.get("/api/hn/dashboard")).json()

    assert [i["hn_id"] for i in data["items"]] == [49953495]
