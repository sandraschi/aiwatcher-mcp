"""Wikipedia ingestion: Wikimedia API etiquette.

Wikimedia returns HTTP 403 to clients without a descriptive User-Agent,
including httpx's default "python-httpx/x.y". Before this test the poller
sent the default and failed every hour (2117 consecutive failures).
"""

from __future__ import annotations

import pytest
import respx


@pytest.fixture(autouse=True)
def _wiki_env(monkeypatch):
    monkeypatch.setenv("WIKIPEDIA_ENABLED", "true")
    monkeypatch.setenv("WIKIPEDIA_INCLUDE_RECENT_CHANGES", "true")
    monkeypatch.setenv("WIKIPEDIA_INCLUDE_FEATURED", "false")
    monkeypatch.setenv("WIKIPEDIA_INCLUDE_RANDOM", "false")
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    yield
    cfg_mod._settings = None


@pytest.mark.asyncio
async def test_poll_sends_descriptive_user_agent(fresh_db):
    from aiwatcher_mcp.wikipedia_ingestion import poll_wikipedia

    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://en.wikipedia.org/w/api.php").respond(
            json={"query": {"recentchanges": []}}
        )
        await poll_wikipedia()

    ua = route.calls.last.request.headers["user-agent"]
    assert ua.startswith("aiwatcher-mcp/"), ua
    assert "python-httpx" not in ua
    assert "github.com/sandraschi/aiwatcher-mcp" in ua  # contact info per Wikimedia UA policy


@pytest.mark.asyncio
async def test_disabled_feed_is_not_polled(fresh_db):
    """The Feeds page toggle must actually stop polling (it was ignored before)."""
    import aiwatcher_mcp.wikipedia_ingestion as wiki
    from aiwatcher_mcp.database import get_db

    wiki._FEED_CACHE.clear()
    feed_id = await wiki._get_or_create_wiki_feed("Wikipedia Recent Changes", "recent_changes")
    async with get_db() as db:
        await db.execute("UPDATE feeds SET enabled=0 WHERE id=?", (feed_id,))
        await db.commit()

    with respx.mock(assert_all_called=False) as mock:
        route = mock.get("https://en.wikipedia.org/w/api.php").respond(
            json={"query": {"recentchanges": []}}
        )
        results = await wiki.poll_wikipedia()

    assert route.call_count == 0
    assert results.get("recent_changes") == 0
    wiki._FEED_CACHE.clear()


@pytest.mark.asyncio
async def test_random_all_requests_failing_is_recorded_as_failure(fresh_db, monkeypatch):
    """Per-request errors were swallowed and the feed marked healthy with 0 items."""
    monkeypatch.setenv("WIKIPEDIA_INCLUDE_RECENT_CHANGES", "false")
    monkeypatch.setenv("WIKIPEDIA_INCLUDE_RANDOM", "true")
    import aiwatcher_mcp.config as cfg_mod
    import aiwatcher_mcp.wikipedia_ingestion as wiki
    from aiwatcher_mcp.database import get_db

    cfg_mod._settings = None
    wiki._FEED_CACHE.clear()
    with respx.mock() as mock:
        mock.get("https://en.wikipedia.org/api/rest_v1/page/random/summary").respond(
            status_code=403
        )
        await wiki.poll_wikipedia()

    async with (
        get_db() as db,
        db.execute(
            "SELECT consecutive_failures, last_error FROM feeds WHERE name='Wikipedia Random Articles'"
        ) as cur,
    ):
        row = await cur.fetchone()
    assert row["consecutive_failures"] == 1
    assert "403" in (row["last_error"] or "")
    wiki._FEED_CACHE.clear()
