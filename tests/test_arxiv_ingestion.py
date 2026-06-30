"""Tests for arxiv_ingestion.py — mocked arxiv-mcp HTTP."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_poll_arxiv_disabled_returns_empty(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ARXIV_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.arxiv_ingestion import poll_arxiv

    assert await poll_arxiv() == {}


@pytest.mark.asyncio
async def test_poll_arxiv_ingests_papers(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ARXIV_ENABLED", "true")
    monkeypatch.setenv("ARXIV_MCP_URL", "http://arxiv.test")
    monkeypatch.setenv("ARXIV_CATEGORIES", "cs.AI")
    cfg_mod._settings = None

    payload = {
        "papers": [
            {
                "arxiv_id": "2606.00001",
                "title": "Test Paper",
                "summary": "Abstract here.",
                "url": "https://arxiv.org/abs/2606.00001",
            }
        ]
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://arxiv.test/api/category/latest").mock(
            return_value=Response(200, json=payload)
        )
        from aiwatcher_mcp.arxiv_ingestion import poll_arxiv

        results = await poll_arxiv()

    assert results.get("cs.AI", 0) >= 1

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT guid FROM items WHERE guid=?", ("arxiv:2606.00001",)) as cur,
    ):
        row = await cur.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_poll_arxiv_accepts_paper_id_field(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ARXIV_ENABLED", "true")
    monkeypatch.setenv("ARXIV_MCP_URL", "http://arxiv.test")
    monkeypatch.setenv("ARXIV_CATEGORIES", "cs.AI")
    cfg_mod._settings = None

    payload = {
        "papers": [
            {
                "paper_id": "2606.00002",
                "title": "Paper ID Field",
                "summary": "Abstract.",
                "abs_url": "https://arxiv.org/abs/2606.00002",
                "categories": ["cs.AI"],
            }
        ]
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://arxiv.test/api/category/latest").mock(
            return_value=Response(200, json=payload)
        )
        from aiwatcher_mcp.arxiv_ingestion import poll_arxiv

        results = await poll_arxiv()

    assert results.get("cs.AI", 0) >= 1

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute(
            "SELECT last_fetched FROM feeds WHERE name=? AND feed_type='arxiv'",
            ("ArXiv: cs.AI",),
        ) as cur,
    ):
        row = await cur.fetchone()
    assert row is not None
    assert row["last_fetched"] is not None
