"""
Integration tests for ingestion.py — feed polling and item parsing.
External HTTP mocked with respx; DB uses temp file (shared connections).
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test AI Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Claude 5 Released</title>
      <link>https://example.com/claude-5</link>
      <guid>guid-claude-5</guid>
      <description>Anthropic releases Claude 5 with massive capability jump.</description>
      <pubDate>Sun, 26 Apr 2026 08:00:00 +0000</pubDate>
    </item>
    <item>
      <title>GPT-5 Turbo Announced</title>
      <link>https://example.com/gpt5</link>
      <guid>guid-gpt5</guid>
      <description>OpenAI announces GPT-5 Turbo with 1M context window.</description>
    </item>
  </channel>
</rss>
"""


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


@pytest.mark.asyncio
async def test_poll_feed_returns_new_count():
    from aiwatcher_mcp.ingestion import poll_feed

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/rss").mock(return_value=Response(200, text=RSS_SAMPLE))
        count = await poll_feed(feed_id=1, url="https://example.com/rss", feed_name="Test Feed")

    assert count == 2


@pytest.mark.asyncio
async def test_poll_feed_deduplication():
    from aiwatcher_mcp.ingestion import poll_feed

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/rss").mock(return_value=Response(200, text=RSS_SAMPLE))
        first = await poll_feed(feed_id=1, url="https://example.com/rss", feed_name="Test Feed")

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/rss").mock(return_value=Response(200, text=RSS_SAMPLE))
        second = await poll_feed(feed_id=1, url="https://example.com/rss", feed_name="Test Feed")

    assert first == 2
    assert second == 0


@pytest.mark.asyncio
async def test_poll_feed_http_error_returns_zero():
    from aiwatcher_mcp.ingestion import poll_feed

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/broken").mock(return_value=Response(500, text="Server Error"))
        count = await poll_feed(
            feed_id=1, url="https://example.com/broken", feed_name="Broken"
        )

    assert count == 0


@pytest.mark.asyncio
async def test_poll_feed_network_timeout_returns_zero():
    import httpx

    from aiwatcher_mcp.ingestion import poll_feed

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/timeout").mock(side_effect=httpx.TimeoutException("timeout"))
        count = await poll_feed(
            feed_id=1, url="https://example.com/timeout", feed_name="Timeout"
        )

    assert count == 0


@pytest.mark.asyncio
async def test_poll_all_feeds_skips_disabled():
    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.ingestion import poll_all_feeds

    async with get_db() as db:
        await db.execute("UPDATE feeds SET enabled=0")
        await db.commit()

    with respx.mock(assert_all_called=False):
        results = await poll_all_feeds()

    assert results == {}


@pytest.mark.asyncio
async def test_make_guid_is_deterministic():
    from aiwatcher_mcp.ingestion import _make_guid

    g1 = _make_guid("https://example.com/a", "Title A")
    g2 = _make_guid("https://example.com/a", "Title A")
    g3 = _make_guid("https://example.com/b", "Title A")

    assert g1 == g2
    assert g1 != g3
    assert len(g1) == 32


@pytest.mark.asyncio
async def test_poll_feed_skips_similar_title():
    """Cross-feed dedup: second item with similar title should be skipped."""
    from aiwatcher_mcp.database import upsert_item
    from aiwatcher_mcp.ingestion import poll_feed

    await upsert_item(2, {
        "guid": "existing-001",
        "title": "Claude 5 Released With Major AI Capability Jump",
        "url": "https://feed2.example.com/claude5",
        "summary": None, "content_html": None, "published_at": None, "tags": [],
    })

    OTHER_FEED_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Other Feed</title>
<item>
  <title>Claude 5 Released — Major AI capability jump announced</title>
  <link>https://feed1.example.com/claude5</link>
  <guid>similar-guid</guid>
  <description>Similar story from a different source.</description>
</item>
</channel></rss>
"""

    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://example.com/otherfeed").mock(return_value=Response(200, text=OTHER_FEED_RSS))
        count = await poll_feed(feed_id=1, url="https://example.com/otherfeed", feed_name="Other Feed")

    assert count == 0  # Similar title should be deduped
