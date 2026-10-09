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


def test_parse_hn_stats_and_controversy():
    from aiwatcher_mcp.hn_ingestion import controversy_score, parse_hn_stats

    pts, cmts = parse_hn_stats("HN: 781 points, 350 comments, by snehesht.")
    assert (pts, cmts) == (781, 350)
    assert controversy_score(781, 350) == round(350 / 781, 3)
    # Flamewar scores higher than consensus hit
    assert controversy_score(150, 400) > controversy_score(781, 350)
    # Fresh story floor avoids div-by-tiny explosion
    assert controversy_score(2, 10) == round(10 / 10, 3)
    assert parse_hn_stats(None) == (None, None)
    assert parse_hn_stats("no stats here") == (None, None)


@pytest.mark.asyncio
async def test_search_hn_stories_no_ingest(fresh_db):
    from aiwatcher_mcp.hn_ingestion import search_hn_stories

    hits = [
        {
            "objectID": "1",
            "title": "X launches",
            "url": "https://example.com/x",
            "author": "a",
            "points": 150,
            "num_comments": 400,
            "created_at": "2026-10-08T00:00:00Z",
        }
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://hn.algolia.com/api/v1/search").respond(json={"hits": hits})
        items = await search_hn_stories("X", limit=10)

    assert len(items) == 1
    assert items[0]["hn_id"] == 1
    assert items[0]["controversy"] == round(400 / 150, 3)
    assert items[0]["hn_url"] == "https://news.ycombinator.com/item?id=1"

    # No DB write: search is read-only
    from aiwatcher_mcp.database import get_db

    async with get_db() as db, db.execute("SELECT COUNT(*) AS n FROM items") as cur:
        row = await cur.fetchone()
    assert row["n"] == 0
    assert await search_hn_stories("  ") == []


@pytest.mark.asyncio
async def test_distill_hn_thread_mocked(monkeypatch):
    import aiwatcher_mcp.hn_ingestion as hn

    async def _fake_thread(item_id: int, force: bool = False):
        return {
            "id": item_id,
            "title": "Why X failed",
            "url": "https://example.com/x",
            "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
            "points": 200,
            "comment_count": 3,
            "story_text": "",
            "comments": [
                {
                    "id": 1,
                    "author": "a",
                    "text": "X failed because of Y, long substantive take " * 10,
                    "children": [],
                },
                {
                    "id": 2,
                    "author": "b",
                    "text": "No, X failed because of Z, counter take " * 10,
                    "children": [],
                },
            ],
        }

    async def _fake_llm(system: str, prompt: str, max_tokens: int = 800, **kwargs):
        assert "Why X failed" in prompt
        return (
            '{"thread_summary": "Two camps.", "positions": '
            '[{"label": "Y camp", "gist": "blames Y", "n": "some"}], '
            '"disagreement": "Y vs Z", "tools_mentioned": ["tool1"], '
            '"try_this": "Try tool1."}'
        )

    monkeypatch.setattr(hn, "fetch_hn_comments", _fake_thread)
    import aiwatcher_mcp.distillation as dist_mod

    monkeypatch.setattr(dist_mod, "_get_llm_response", _fake_llm)
    # distill_hn_thread imports _get_llm_response lazily, patch target module works
    import aiwatcher_mcp.hn_ingestion as hn2

    out = await hn2.distill_hn_thread(123, max_comments=10)
    assert out["id"] == 123
    assert out["thread_summary"] == "Two camps."
    assert out["disagreement"] == "Y vs Z"
    assert out["tools_mentioned"] == ["tool1"]


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
