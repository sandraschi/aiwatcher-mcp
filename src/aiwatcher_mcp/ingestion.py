"""
Ingestion — RSS/Atom feed polling + Alpha Signal email parsing.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from aiwatcher_mcp.database import get_feeds, update_item_scores, upsert_item, get_db

log = logging.getLogger(__name__)


def _make_guid(url: str | None, title: str) -> str:
    raw = (url or "") + title
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_date(entry: Any) -> str | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return None


async def poll_feed(feed_id: int, url: str, feed_name: str) -> int:
    """Fetch and ingest one RSS/Atom feed. Returns new item count."""
    new_count = 0
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "aiwatcher-mcp/0.1"})
            resp.raise_for_status()
            raw = resp.text

        parsed = feedparser.parse(raw)
        if parsed.bozo:
            log.warning("Feed %s parse warning: %s", feed_name, parsed.bozo_exception)

        for entry in parsed.entries[:50]:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", "(no title)")
            guid = getattr(entry, "id", None) or _make_guid(link, title)
            summary = getattr(entry, "summary", None)
            content_html = None
            if hasattr(entry, "content") and entry.content:
                content_html = entry.content[0].get("value")

            item = {
                "guid": guid,
                "title": title,
                "url": link,
                "summary": summary,
                "content_html": content_html,
                "published_at": _parse_date(entry),
                "tags": [],
            }
            if await upsert_item(feed_id, item):
                new_count += 1

        # Update last_fetched
        async with get_db() as db:
            await db.execute(
                "UPDATE feeds SET last_fetched=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), feed_id),
            )
            await db.commit()

        log.info("Feed '%s': %d new items", feed_name, new_count)
    except Exception as exc:
        log.error("Error polling feed '%s' (%s): %s", feed_name, url, exc)
    return new_count


async def poll_all_feeds() -> dict[str, int]:
    """Poll all enabled feeds. Returns {feed_name: new_count}."""
    feeds = await get_feeds()
    results: dict[str, int] = {}
    for feed in feeds:
        if not feed["enabled"]:
            continue
        if feed["feed_type"] in ("rss", "atom"):
            count = await poll_feed(feed["id"], feed["url"], feed["name"])
            results[feed["name"]] = count
    return results
