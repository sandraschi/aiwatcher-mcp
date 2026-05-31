"""
Tests for gmail_ingestion.py — Alpha Signal email link extraction and polling.
External HTTP mocked with respx; DB uses temp file (shared connections).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

SAMPLE_NEWSLETTER_HTML = """<html>
<body>
  <p><a href="https://alphasignal.ai/posts/claude-5-benchmarks">Claude 5 Shatters Benchmarks</a></p>
  <p><a href="https://alphasignal.ai/posts/gpt-5-turbo-review">GPT-5 Turbo: A Deep Dive</a></p>
  <p><a href="https://twitter.com/foo/status/123">Follow us on Twitter</a></p>
  <p><a href="https://example.com/unsubscribe">Unsubscribe</a></p>
  <p><a href="https://alphasignal.ai/posts/ai-safety-update">AI Safety Update</a></p>
  <p><a href="https://alphasignal.ai/posts/deepseek-r2">DeepSeek R2 Released</a></p>
</body>
</html>"""


# ── _extract_links_from_html ──────────────────────────────────────────────


def test_extract_links_returns_relevant_urls():
    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html

    links = _extract_links_from_html(SAMPLE_NEWSLETTER_HTML)

    assert len(links) == 4
    assert links[0]["title"] == "Claude 5 Shatters Benchmarks"
    assert links[0]["url"] == "https://alphasignal.ai/posts/claude-5-benchmarks"
    assert links[3]["title"] == "DeepSeek R2 Released"


def test_extract_links_skips_junk():
    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html

    links = _extract_links_from_html(SAMPLE_NEWSLETTER_HTML)
    urls = [ln["url"] for ln in links]

    assert "https://twitter.com/foo/status/123" not in urls
    assert "https://example.com/unsubscribe" not in urls


def test_extract_links_caps_at_thirty():
    html = "<html>" + "".join(
        f'<a href="https://example.com/{i}">Article {i}</a>'
        for i in range(50)
    ) + "</html>"

    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html
    links = _extract_links_from_html(html)

    assert len(links) <= 30


def test_extract_links_skips_short_titles():
    html = '<html><a href="https://example.com/1">Hi</a><a href="https://example.com/2">Long enough title</a></html>'

    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html
    links = _extract_links_from_html(html)

    assert len(links) == 1
    assert links[0]["title"] == "Long enough title"


def test_extract_links_skips_non_http():
    html = '<html><a href="ftp://example.com/file">FTP Link</a><a href="/relative/path">Relative</a></html>'

    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html
    links = _extract_links_from_html(html)

    assert len(links) == 0


def test_extract_links_dedups_on_base_url():
    """Two links to the same base URL should yield one entry."""
    html = """<html>
      <a href="https://example.com/article?ref=twitter">Article One</a>
      <a href="https://example.com/article?ref=email">Article Again</a>
    </html>"""

    from aiwatcher_mcp.gmail_ingestion import _extract_links_from_html
    links = _extract_links_from_html(html)

    assert len(links) == 1


# ── _get_or_create_email_feed ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_email_feed_creates_new():
    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.gmail_ingestion import _get_or_create_email_feed

    feed_id = await _get_or_create_email_feed("custom-sender@example.com")

    async with get_db() as db, db.execute(
        "SELECT name, feed_type FROM feeds WHERE id=?", (feed_id,)
    ) as cur:
        row = await cur.fetchone()
        assert row["name"] == "Email: custom-sender@example.com"
        assert row["feed_type"] == "email"


@pytest.mark.asyncio
async def test_get_or_create_email_feed_caches():
    from aiwatcher_mcp.gmail_ingestion import _get_or_create_email_feed

    first = await _get_or_create_email_feed("custom-sender@example.com")
    second = await _get_or_create_email_feed("custom-sender@example.com")

    assert first == second


# ── poll_gmail_alphasignal ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_gmail_returns_zero_when_disabled():
    import os
    os.environ["GMAIL_ENABLED"] = "false"

    from aiwatcher_mcp.config import get_settings
    get_settings().gmail_enabled = False

    from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal
    count = await poll_gmail_alphasignal()

    assert count == 0


def _enable_gmail() -> None:
    """Helper: enable Gmail with a custom sender to avoid default feed collision."""
    import os
    os.environ["GMAIL_ENABLED"] = "true"
    os.environ["GMAIL_MCP_URL"] = "http://localhost:10812"
    os.environ["ALPHASIGNAL_SENDER"] = "alpha-signal-digest@example.com"

    from aiwatcher_mcp.config import get_settings
    cfg = get_settings()
    cfg.gmail_enabled = True
    cfg.gmail_mcp_url = "http://localhost:10812"
    cfg.alphasignal_sender = "alpha-signal-digest@example.com"


@pytest.mark.asyncio
async def test_poll_gmail_extracts_and_inserts():
    _enable_gmail()

    from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal

    messages = {
        "messages": [
            {
                "id": "msg001",
                "subject": "Alpha Signal Weekly",
                "date": "2026-04-29T08:00:00",
                "body_html": SAMPLE_NEWSLETTER_HTML,
            }
        ]
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.get(
            "http://localhost:10812/api/v1/messages?q=from%3Aalpha-signal-digest%40example.com+is%3Aunread&max_results=10"
        ).mock(return_value=Response(200, json=messages))
        mock.post(
            "http://localhost:10812/api/v1/messages/msg001/read",
        ).mock(return_value=Response(200))

        count = await poll_gmail_alphasignal()

    assert count == 4  # 4 valid links from the HTML


@pytest.mark.asyncio
async def test_poll_gmail_http_error_returns_zero():
    _enable_gmail()

    from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal

    with respx.mock(assert_all_called=False) as mock:
        mock.get(
            "http://localhost:10812/api/v1/messages",
        ).mock(return_value=Response(500, text="Server Error"))

        count = await poll_gmail_alphasignal()

    assert count == 0


@pytest.mark.asyncio
async def test_poll_gmail_network_error_returns_zero():
    _enable_gmail()

    from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal

    with respx.mock(assert_all_called=False) as mock:
        mock.get("http://localhost:10812/api/v1/messages").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        count = await poll_gmail_alphasignal()

    assert count == 0
