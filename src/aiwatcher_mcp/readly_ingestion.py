"""
Readly-mcp ingestion — poll Readly magazine articles as feed items.

Requires readly-mcp running with its REST API on READLY_MCP_URL.
Enabled via READLY_ENABLED=true in .env.

Strategy:
  - Calls readly-mcp GET /api/articles/list to discover articles on the current issue
  - Calls GET /api/articles/extract?index=N for full text
  - Inserts results as items with feed_type="readly"
  - Benefits from existing distillation pipeline (Claude scoring, alerts, digest)
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

READLY_FEED_ID: int | None = None


async def _get_or_create_readly_feed() -> int:
    """Ensure a 'readly' type feed exists, return its id."""
    global READLY_FEED_ID
    if READLY_FEED_ID is not None:
        return READLY_FEED_ID

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='readly'",
            ("Readly Magazine Articles",),
        ) as cur:
            row = await cur.fetchone()

        if row:
            READLY_FEED_ID = row["id"]
            return READLY_FEED_ID

        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            ("Readly Magazine Articles", "https://go.readly.com", "readly"),
        )
        await db.commit()
        READLY_FEED_ID = cur.lastrowid
        log.info("Created readly feed id=%d", READLY_FEED_ID)
        return READLY_FEED_ID


async def poll_readly_articles() -> int:
    """
    Call readly-mcp REST API to discover articles on the current magazine page.
    Returns new item count.
    """
    cfg = get_settings()
    readly_url = cfg.readly_mcp_url
    if not readly_url:
        return 0

    feed_id = await _get_or_create_readly_feed()
    new_count = 0

    try:
        # 1. List articles from current page
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{readly_url}/api/articles/list")
            resp.raise_for_status()
            article_data = resp.json()

        issue_title = article_data.get("issue_title", "Readly Issue")
        articles = article_data.get("articles", [])

        if not articles:
            log.info("Readly: no articles found on current page")
            return 0

        # 2. Process articles (limit to 10 to avoid long polling)
        async with httpx.AsyncClient(timeout=30) as client:
            for article in articles[:10]:
                try:
                    # Try to get full text
                    ext_resp = await client.get(
                        f"{readly_url}/api/articles/extract",
                        params={"index": article["index"]},
                    )
                    if ext_resp.status_code != 200:
                        continue
                    ext_data = ext_resp.json()
                    if "error" in ext_data:
                        continue

                    guid = hashlib.sha256(
                        f"readly:{ext_data.get('url', article.get('url', ''))}".encode()
                    ).hexdigest()[:32]

                    item = {
                        "guid": guid,
                        "title": ext_data.get("title", article.get("title", "(no title)")),
                        "url": ext_data.get("url", article.get("url", "")),
                        "summary": f"{ext_data.get('text', '')[:500]}...\n\nVia Readly: {issue_title}"
                        if ext_data.get("text")
                        else f"Article from Readly: {issue_title}",
                        "content_html": None,
                        "published_at": None,
                        "tags": ["readly", "magazine", "longform"],
                    }

                    result, reason = Scrubber().check_item(item)
                    if result in ("spam", "scam"):
                        log.info("Readly scrubber blocked '%s' [%s]: %s", item["title"][:60], result, reason)
                        continue

                    if await upsert_item(feed_id, item):
                        new_count += 1

                except Exception as exc:
                    log.warning("Readly article extract failed for index %d: %s", article.get("index", -1), exc)

    except Exception as exc:
        log.warning("Readly poll failed: %s", exc)

    log.info("Readly: %d new articles ingested", new_count)
    return new_count
