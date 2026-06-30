"""Tests for Readly watchlist ingestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _readly_env(monkeypatch):
    monkeypatch.setenv("READLY_ENABLED", "true")
    monkeypatch.setenv("READLY_MCP_URL", "http://127.0.0.1:10863")
    monkeypatch.setenv(
        "READLY_WATCHLIST",
        "New Scientist,MIT Technology Review",
    )
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    import aiwatcher_mcp.readly_ingestion as ri

    ri._FEED_CACHE.clear()
    ri.set_runtime_readly_watchlist(None)
    yield
    cfg_mod._settings = None
    ri._FEED_CACHE.clear()
    ri.set_runtime_readly_watchlist(None)


def test_readly_watchlist_parsed_from_env():
    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()
    assert cfg.parsed_readly_watchlist() == ["New Scientist", "MIT Technology Review"]


def test_runtime_watchlist_override():
    from aiwatcher_mcp.readly_ingestion import (
        get_effective_readly_watchlist,
        set_runtime_readly_watchlist,
    )

    set_runtime_readly_watchlist(["Wired"])
    assert get_effective_readly_watchlist() == ["Wired"]


@pytest.mark.asyncio
async def test_poll_readly_watchlist_ingests_full_text(fresh_db):
    from aiwatcher_mcp.readly_ingestion import poll_readly_articles

    long_text = "word " * 120

    last_magazine: list[str] = []

    def _mock_get(url, params=None):
        resp = MagicMock()
        resp.status_code = 200
        if url.endswith("/api/magazines/latest"):
            last_magazine.clear()
            last_magazine.append(params.get("name", "mag"))
            resp.json.return_value = {"success": True, "magazine_name": params["name"]}
        elif url.endswith("/api/articles/read-all"):
            mag = last_magazine[0] if last_magazine else "mag"
            resp.json.return_value = {
                "success": True,
                "issue_title": f"{mag} Issue 1",
                "articles": [
                    {
                        "title": f"Story from {mag}",
                        "url": f"https://readly.com/read/{mag.replace(' ', '-')}",
                        "text": long_text,
                        "word_count": 120,
                    }
                ],
            }
        else:
            resp.json.return_value = {}
        return resp

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=_mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("aiwatcher_mcp.readly_ingestion.httpx.AsyncClient", return_value=mock_client),
        patch(
            "aiwatcher_mcp.readly_ingestion._ensure_bundle_for_magazine",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        count = await poll_readly_articles()

    assert count == 2

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT content_html FROM items WHERE title LIKE 'Story from %'") as cur,
    ):
        row = await cur.fetchone()
    assert row is not None
    assert len(row["content_html"]) > 500
