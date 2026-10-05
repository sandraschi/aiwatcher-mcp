"""Tests for HN front-page + watchlist ingestion (issue #11).

External HTTP mocked with respx; DB uses temp file (fresh_db).
Retrospective fixture: Strata (HN item 49953495, 781 pts / 350 comments).
"""

from __future__ import annotations

import pytest
import respx


@pytest.fixture(autouse=True)
def _hn_env(monkeypatch):
    monkeypatch.setenv("HN_ENABLED", "true")
    monkeypatch.setenv("HN_WATCHLIST", "")
    monkeypatch.setenv("HN_MIN_POINTS", "100")
    monkeypatch.setenv("HN_MIN_STAR_VELOCITY", "200")
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    import aiwatcher_mcp.hn_ingestion as hn

    hn._GH_CACHE.clear()
    hn.set_runtime_hn_watchlist(None)
    yield
    cfg_mod._settings = None
    hn._GH_CACHE.clear()
    hn.set_runtime_hn_watchlist(None)


STRATA_STORY = {
    "objectID": "49953495",
    "title": "Run Qwen 3.8 Flash Next (125B) on consumer hardware (RTX 4090) at 100T/s",
    "url": "https://github.com/Niko1221/Strata",
    "author": "snehesht",
    "points": 781,
    "num_comments": 350,
    "created_at": "2026-10-04T12:51:53Z",
}

STRATA_REPO = {
    "full_name": "Niko1221/Strata",
    "stargazers_count": 12000,
    "created_at": "2026-10-02T00:00:00Z",
}

QUIET_STORY = {
    "objectID": "49960001",
    "title": "A quiet weekend project with five points",
    "url": "https://example.com/quiet",
    "author": "nobody",
    "points": 5,
    "num_comments": 0,
    "created_at": "2026-10-05T08:00:00Z",
}


def test_hn_watchlist_parsed_from_env(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod
    from aiwatcher_mcp.config import get_settings

    monkeypatch.setenv("HN_WATCHLIST", "GGUF, Ollama")
    cfg_mod._settings = None
    assert get_settings().parsed_hn_watchlist() == ["GGUF", "Ollama"]


def test_runtime_hn_watchlist_override():
    from aiwatcher_mcp.hn_ingestion import (
        get_effective_hn_watchlist,
        set_runtime_hn_watchlist,
    )

    set_runtime_hn_watchlist(["local LLM", "MCP"])
    assert get_effective_hn_watchlist() == ["local LLM", "MCP"]


def test_story_meets_gate():
    from aiwatcher_mcp.hn_ingestion import _story_meets_gate

    assert (
        _story_meets_gate(
            {"points": 781},
            min_points=100,
            min_star_velocity=200.0,
            watchlist_hit=False,
            star_velocity=0.0,
        )
        is True
    )
    assert (
        _story_meets_gate(
            {"points": 5},
            min_points=100,
            min_star_velocity=200.0,
            watchlist_hit=False,
            star_velocity=4000.0,
        )
        is True
    )
    assert (
        _story_meets_gate(
            {"points": 5},
            min_points=100,
            min_star_velocity=200.0,
            watchlist_hit=True,
            star_velocity=0.0,
        )
        is True
    )
    assert (
        _story_meets_gate(
            {"points": 5},
            min_points=100,
            min_star_velocity=200.0,
            watchlist_hit=False,
            star_velocity=0.0,
        )
        is False
    )


def test_parse_github_repo():
    from aiwatcher_mcp.hn_ingestion import _parse_github_repo

    assert _parse_github_repo("https://github.com/Niko1221/Strata") == "Niko1221/Strata"
    assert _parse_github_repo("https://example.com/quiet") is None
    assert _parse_github_repo(None) is None


@pytest.mark.asyncio
async def test_poll_frontpage_ingests_strata_retrospective(fresh_db):
    from aiwatcher_mcp.hn_ingestion import poll_hn_frontpage

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://hn.algolia.com/api/v1/search").respond(
            json={"hits": [STRATA_STORY, QUIET_STORY]}
        )
        mock.get("https://api.github.com/repos/Niko1221/Strata").respond(json=STRATA_REPO)
        results = await poll_hn_frontpage()

    assert results.get("frontpage") == 1

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT guid, title, summary FROM items") as cur,
    ):
        rows = await cur.fetchall()

    assert len(rows) == 1
    assert rows[0]["guid"] == "hn:49953495"
    assert "Qwen 3.8 Flash Next" in rows[0]["title"]
    assert "781 points" in rows[0]["summary"]


@pytest.mark.asyncio
async def test_poll_survives_github_outage(fresh_db):
    from aiwatcher_mcp.hn_ingestion import poll_hn_frontpage

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://hn.algolia.com/api/v1/search").respond(json={"hits": [STRATA_STORY]})
        mock.get("https://api.github.com/repos/Niko1221/Strata").respond(status_code=500)
        results = await poll_hn_frontpage()

    # Points gate alone carries it - GH enrichment is best-effort
    assert results.get("frontpage") == 1


@pytest.mark.asyncio
async def test_poll_disabled_returns_empty(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("HN_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.hn_ingestion import poll_hn_frontpage

    assert await poll_hn_frontpage() == {}


@pytest.mark.asyncio
async def test_poll_watchlist_creates_distinct_feeds(fresh_db, monkeypatch):
    """Regression: frontpage + watchlist feeds share no UNIQUE url (live 500)."""
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("HN_WATCHLIST", "GGUF")
    cfg_mod._settings = None

    from aiwatcher_mcp.hn_ingestion import poll_hn_frontpage

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://hn.algolia.com/api/v1/search").respond(json={"hits": [STRATA_STORY]})
        mock.get("https://api.github.com/repos/Niko1221/Strata").respond(json=STRATA_REPO)
        mock.get("https://hn.algolia.com/api/v1/search_by_date").respond(
            json={"hits": [QUIET_STORY]}
        )
        results = await poll_hn_frontpage()

    assert results.get("frontpage") == 1
    assert results.get("watchlist") == 1

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT name, url FROM feeds WHERE feed_type='hn' ORDER BY name") as cur,
    ):
        feeds = await cur.fetchall()

    assert [r["name"] for r in feeds] == ["HN Front Page", "HN Watchlist"]
    assert len({r["url"] for r in feeds}) == 2
