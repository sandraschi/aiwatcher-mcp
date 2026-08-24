"""
Ingestion — RSS/Atom feed polling + Alpha Signal email parsing.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from aiwatcher_mcp.database import (
    _find_similar_item,
    get_feeds,
    record_feed_failure,
    record_feed_success,
    upsert_item,
)
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_SCRUBBER = Scrubber()

FEED_FALLBACK_PATHS = [
    "/feed/",
    "/rss/",
    "/index.xml",
    "/atom.xml",
    "/feed.xml",
    "/blog/feed/",
    "/feed",
    "/rss",
]


def _make_guid(url: str | None, title: str) -> str:
    raw = (url or "") + title
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_date(entry: Any) -> str | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=UTC).isoformat()
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=UTC).isoformat()
        except Exception:
            pass
    return None


async def poll_feed(feed_id: int, url: str, feed_name: str) -> int:
    """
    Fetch and ingest one RSS/Atom feed. Returns new item count.
    Updates feed health counters on success/failure.
    On HTTP 4xx/redirect, probes fallback URLs and auto-heals the feed URL.
    Cross-feed dedup: skips items that are >=85% title-similar to recent items.
    """
    new_count = 0
    try:
        raw = await _fetch_feed_content(url, feed_name)
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

            similar = await _find_similar_item(title, feed_id, summary=summary)
            if similar:
                continue

            item = {
                "guid": guid,
                "title": title,
                "url": link,
                "summary": summary,
                "content_html": content_html,
                "published_at": _parse_date(entry),
                "tags": [],
            }
            result, reason = _SCRUBBER.check_item(item)
            if result in ("spam", "scam"):
                log.info("Scrubber blocked '%s' [%s]: %s", title[:60], result, reason)
                item["tags"] = [result]
                await upsert_item(feed_id, item)
                continue
            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("Feed '%s': %d new items", feed_name, new_count)

    except Exception as exc:
        error_msg = str(exc)
        status_code = getattr(exc, "response", None)
        status = getattr(status_code, "status_code", 0) if status_code else 0

        if status in (404, 410) or (
            isinstance(exc, httpx.HTTPStatusError)
            and getattr(getattr(exc, "response", None), "status_code", 0) in (404, 410)
        ):
            healed = await _try_fallback_feed(feed_id, url, feed_name)
            if healed:
                new_count = await poll_feed(feed_id, healed, feed_name)
                return new_count

        log.error("Error polling feed '%s' (%s): %s", feed_name, url, error_msg)
        auto_disabled = await record_feed_failure(feed_id, error_msg)
        if auto_disabled:
            log.warning("Feed '%s' has been auto-disabled after repeated failures.", feed_name)

    return new_count


def _fetch_with_obscura(url: str) -> str | None:
    """Synchronous Obscura stealth fetch helper."""
    try:
        import sys
        from pathlib import Path
        obscura_mcp_path = Path("D:/Dev/repos/obscura-mcp/src")
        if obscura_mcp_path.exists() and str(obscura_mcp_path) not in sys.path:
            sys.path.insert(0, str(obscura_mcp_path))

        from obscura_mcp.server import fetch_with_obscura
        return fetch_with_obscura(url, dump="html", stealth=True, timeout=35)
    except Exception as e:
        log.warning("Obscura feed fetch fallback failed for %s: %s", url, e)
        return None


async def _fetch_feed_content(url: str, feed_name: str) -> str:
    """Fetch feed content with standard headers and Obscura stealth fallback."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "aiwatcher-mcp/0.2"})
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (403, 429, 503):
            log.warning("Feed '%s' HTTP %d block — attempting Obscura stealth fallback", feed_name, exc.response.status_code)
            import asyncio
            obs_text = await asyncio.to_thread(_fetch_with_obscura, url)
            if obs_text and len(obs_text.strip()) > 50:
                return obs_text
        raise


async def _try_fallback_feed(feed_id: int, original_url: str, feed_name: str) -> str | None:
    """Probe common feed path variants against the original feed's domain.
    Returns new working URL if found, updates the DB. Returns None if no fallback works."""
    from urllib.parse import urlparse

    from aiwatcher_mcp.database import get_db

    parsed = urlparse(original_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for path in FEED_FALLBACK_PATHS:
            fallback = f"{domain.rstrip('/')}{path}"
            if fallback == original_url:
                continue
            try:
                resp = await client.get(fallback, headers={"User-Agent": "aiwatcher-mcp/0.2"})
                if resp.status_code == 200:
                    raw = resp.text
                    if feedparser.parse(raw).entries:
                        async with get_db() as db:
                            await db.execute(
                                "UPDATE feeds SET url=? WHERE id=?", (fallback, feed_id)
                            )
                            await db.commit()
                        log.info(
                            "Feed '%s' URL healed: %s -> %s", feed_name, original_url, fallback
                        )
                        return fallback
            except Exception:
                continue
    return None


async def poll_all_feeds() -> dict[str, int]:
    """
    Poll all enabled feeds in parallel (up to 4 concurrent) using asyncio.gather.
    Returns {feed_name: new_count}.
    """
    import asyncio
    import os

    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()

    if os.environ.get("AIWATCHER_E2E") == "1":
        log.debug("AIWATCHER_E2E=1 — skipping live RSS/arxiv poll")
        return {"e2e_skipped": 0}

    feeds = await get_feeds()
    results: dict[str, int] = {}

    sem = asyncio.Semaphore(4)

    async def _poll_one(feed: dict) -> tuple[str, int]:
        async with sem:
            count = await poll_feed(feed["id"], feed["url"], feed["name"])
            return feed["name"], count

    rss_feeds = [f for f in feeds if f["enabled"] and f["feed_type"] in ("rss", "atom")]
    if rss_feeds:
        outcomes = await asyncio.gather(*[_poll_one(f) for f in rss_feeds], return_exceptions=True)
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                log.warning("Feed poll parallel error: %s", outcome)
            elif isinstance(outcome, tuple):
                name, count = outcome
                results[name] = count
            else:
                log.warning("Unexpected poll outcome: %s", type(outcome))

    # Gmail / email ingestion
    if cfg.gmail_enabled:
        try:
            from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal

            gmail_count = await poll_gmail_alphasignal()
            if gmail_count:
                results["Email: Alpha Signal"] = gmail_count
        except Exception as exc:
            log.error("Gmail ingestion error: %s", exc)

    # ArXiv ingestion
    if cfg.arxiv_enabled:
        try:
            from aiwatcher_mcp.arxiv_ingestion import poll_arxiv

            arxiv_results = await poll_arxiv()
            for cat, count in arxiv_results.items():
                if count:
                    results[f"ArXiv: {cat}"] = count
        except Exception as exc:
            log.error("ArXiv ingestion error: %s", exc)

    # Readly: watchlist polls run on dedicated scheduler job (readly_poll), not every RSS cycle
    if cfg.readly_enabled and not cfg.parsed_readly_watchlist():
        try:
            from aiwatcher_mcp.readly_ingestion import poll_readly_articles

            readly_count = await poll_readly_articles()
            if readly_count:
                results["Readly (legacy)"] = readly_count
        except Exception as exc:
            log.error("Readly ingestion error: %s", exc)

    return results
