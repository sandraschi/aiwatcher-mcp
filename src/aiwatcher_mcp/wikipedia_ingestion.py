"""Wikipedia ingestion - polls recent changes, featured content, and random articles.

Uses public Wikimedia REST API v1 (no API key required for read):
  - /api/rest_v1/feed/featured/{YYYY}/{MM}/{DD} - daily featured content
  - /api/rest_v1/page/random/summary - random article summaries
  - /w/api.php?action=query&list=recentchanges - recent article changes
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_failure, record_feed_success, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_WIKI_API_BASE = "https://en.wikipedia.org/api/rest_v1"
_WIKI_ACTION_API = "https://en.wikipedia.org/w/api.php"

_FEED_CACHE: dict[str, int] = {}


async def _get_or_create_wiki_feed(name: str, category: str) -> int:
    key = f"wiki:{category}:{name}"
    if key in _FEED_CACHE:
        return _FEED_CACHE[key]

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='wikipedia'",
            (name,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            _FEED_CACHE[key] = row["id"]
            return row["id"]

        url = f"wiki://{category}/{name.lower().replace(' ', '-')}"
        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            (name, url, "wikipedia"),
        )
        await db.commit()
        feed_id = int(cur.lastrowid or 0)
        _FEED_CACHE[key] = feed_id
        log.info("Created wikipedia feed id=%d name=%s", feed_id, name)
        return int(feed_id or 0)


def _wiki_item(
    feed_id: int,
    guid_prefix: str,
    title: str,
    url: str,
    summary: str | None,
    published_at: str | None,
    tags: list[str],
) -> dict:
    guid = hashlib.sha256(f"{guid_prefix}:{url}".encode()).hexdigest()[:32]
    return {
        "guid": guid,
        "title": title,
        "url": url,
        "summary": summary,
        "content_html": None,
        "published_at": published_at,
        "tags": tags + ["wikipedia", guid_prefix],
    }


async def poll_wikipedia() -> dict[str, int]:
    """
    Poll enabled Wikipedia sources (recent changes, featured, random).
    Returns {category: new_count}.
    """
    cfg = get_settings()
    if not cfg.wikipedia_enabled:
        return {}

    results: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        if cfg.wikipedia_include_recent_changes:
            results["recent_changes"] = await _poll_recent_changes(client)
        if cfg.wikipedia_include_featured:
            results["featured"] = await _poll_featured(client)
        if cfg.wikipedia_include_random:
            results["random"] = await _poll_random(client)

    if results:
        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()

    return results


async def _poll_recent_changes(client: httpx.AsyncClient) -> int:
    feed_id = await _get_or_create_wiki_feed("Wikipedia Recent Changes", "recent_changes")
    new_count = 0

    try:
        resp = await client.get(
            _WIKI_ACTION_API,
            params={
                "action": "query",
                "list": "recentchanges",
                "rcnamespace": "0",
                "rcshow": "!bot",
                "rclimit": "30",
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        changes = data.get("query", {}).get("recentchanges", [])

        for change in changes:
            title = change.get("title", "")
            if not title:
                continue
            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            summary = change.get("comment", "") or change.get("parsedcomment", "")
            published = change.get("timestamp", "")[:19]
            tags_list = change.get("tags", [])

            item = _wiki_item(
                feed_id,
                "rc",
                title,
                url,
                summary or f"Wikipedia article changed: {title}",
                published,
                tags_list + ["wiki-recent-change"],
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("Wikipedia recent changes: %d new items", new_count)
    except Exception as exc:
        log.error("Wikipedia recent changes poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count


async def _poll_featured(client: httpx.AsyncClient) -> int:
    feed_id = await _get_or_create_wiki_feed("Wikipedia Featured Content", "featured")
    new_count = 0
    today = datetime.now(UTC).date()

    try:
        resp = await client.get(
            f"{_WIKI_API_BASE}/feed/featured/{today.year}/{today.month:02d}/{today.day:02d}",
        )
        resp.raise_for_status()
        data = resp.json()

        entries: list[dict] = []
        for key in ("tfa", "mostread"):
            entry = data.get(key)
            if isinstance(entry, dict):
                entries.append(entry)

        for entry in entries:
            title = entry.get("title", "") or entry.get("displaytitle", "")
            if not title:
                continue
            url = entry.get("content_urls", {}).get("desktop", {}).get("page", "")
            if not url:
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            summary = entry.get("extract", "") or entry.get("description", "")
            tags_list = []
            if "tfa" in str(entry.get("pageid", "")):
                tags_list.append("wiki-featured-article")
            else:
                tags_list.append("wiki-featured")

            item = _wiki_item(
                feed_id,
                "featured",
                title,
                url,
                summary[:500] if summary else "",
                today.isoformat(),
                tags_list,
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("Wikipedia featured content: %d new items", new_count)
    except Exception as exc:
        log.error("Wikipedia featured content poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count


async def _poll_random(client: httpx.AsyncClient) -> int:
    feed_id = await _get_or_create_wiki_feed("Wikipedia Random Articles", "random")
    new_count = 0
    count = min(get_settings().wikipedia_random_count, 10)

    try:
        for _ in range(count):
            try:
                resp = await client.get(f"{_WIKI_API_BASE}/page/random/summary")
                resp.raise_for_status()
                page = resp.json()
            except Exception:
                continue

            title = page.get("title", "")
            if not title:
                continue
            url = (
                page.get("content_urls", {})
                .get("desktop", {})
                .get("page", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
            )
            summary = page.get("extract", "") or page.get("description", "")
            published = page.get("timestamp", "")[:19]

            item = _wiki_item(
                feed_id,
                "random",
                title,
                url,
                summary[:500] if summary else "",
                published,
                ["wiki-random"],
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("Wikipedia random articles: %d new items", new_count)
    except Exception as exc:
        log.error("Wikipedia random articles poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count
