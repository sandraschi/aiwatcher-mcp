"""
Readly-mcp ingestion - poll Readly magazine articles as feed items.

Requires readly-mcp REST API on READLY_MCP_URL.
Watchlist mode: READLY_WATCHLIST + /api/magazines/latest + /api/articles/read-all.
Legacy mode: single-page /api/articles/list + per-article extract (empty watchlist).
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_bundles, get_db, link_feed_to_bundle, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_FEED_CACHE: dict[str, int] = {}
_runtime_watchlist: list[str] | None = None


def get_effective_readly_watchlist() -> list[str]:
    cfg = get_settings()
    if _runtime_watchlist is not None:
        return list(_runtime_watchlist)
    return cfg.parsed_readly_watchlist()


def set_runtime_readly_watchlist(watchlist: list[str] | None) -> None:
    global _runtime_watchlist
    _runtime_watchlist = list(watchlist) if watchlist is not None else None


async def _get_or_create_readly_feed(magazine_name: str) -> int:
    """One feed row per magazine: name='Readly: {magazine_name}', feed_type='readly'."""
    key = magazine_name.strip()
    if key in _FEED_CACHE:
        return _FEED_CACHE[key]

    feed_name = f"Readly: {key}"
    feed_url = f"readly://magazine/{key.lower().replace(' ', '-')}"

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='readly'",
            (feed_name,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            _FEED_CACHE[key] = row["id"]
            return row["id"]

        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type, enabled) VALUES (?,?,?,1)",
            (feed_name, feed_url, "readly"),
        )
        await db.commit()
        feed_id = int(cur.lastrowid or 0)
        _FEED_CACHE[key] = feed_id
        log.info("Created readly feed id=%d name=%s", feed_id, feed_name)
        return int(feed_id or 0)


async def _ensure_bundle_for_magazine(magazine_name: str, feed_id: int) -> int | None:
    """Create interest bundle + link feed if missing."""
    from aiwatcher_mcp.bundles import elicit_bundle_config
    from aiwatcher_mcp.database import add_bundle

    topic = magazine_name.strip()
    bundles = await get_bundles()
    for bundle in bundles:
        if (bundle.get("topic") or "").lower() == topic.lower():
            await link_feed_to_bundle(feed_id, bundle["id"])
            return bundle["id"]

    config = await elicit_bundle_config(
        f"{topic} - longform magazine journalism; score for depth, investigative quality, "
        f"and relevance to AI, science, and technology policy"
    )
    bundle_id = await add_bundle(
        name=config.get("name") or f"Readly: {topic}",
        topic=topic,
        system_prompt=config["system_prompt"],
    )
    await link_feed_to_bundle(feed_id, bundle_id)
    log.info("Auto-created bundle id=%d for Readly magazine '%s'", bundle_id, topic)
    return bundle_id


async def _ingest_article(
    feed_id: int,
    magazine_name: str,
    article: dict,
    *,
    issue_title: str = "",
) -> bool:
    text = (article.get("text") or "").strip()
    wc = article.get("word_count") or len(text.split())
    if wc < 50:
        return False

    url = article.get("url") or ""
    title = article.get("title") or "(no title)"
    guid = hashlib.sha256(f"readly:{magazine_name}:{url or title}".encode()).hexdigest()[:32]
    slug = magazine_name.lower().replace(" ", "-")

    item = {
        "guid": guid,
        "title": title,
        "url": url,
        "summary": text[:500],
        "content_html": text,
        "published_at": None,
        "tags": ["readly", "magazine", "longform", slug, f"readly:{slug}"],
    }
    if issue_title:
        item["summary"] = f"{item['summary']}\n\nVia Readly: {issue_title}"

    result, reason = Scrubber().check_item(item)
    if result in ("spam", "scam"):
        log.info("Readly scrubber blocked '%s': %s", title[:60], reason)
        return False

    return await upsert_item(feed_id, item)


async def _poll_legacy_single_page(client: httpx.AsyncClient, readly_url: str) -> int:
    """Legacy path: whatever issue the browser is already on."""
    feed_id = await _get_or_create_readly_feed("Magazine Articles")
    new_count = 0

    resp = await client.get(f"{readly_url}/api/articles/list")
    resp.raise_for_status()
    article_data = resp.json()
    issue_title = article_data.get("issue_title", "Readly Issue")
    articles = article_data.get("articles", [])
    if not articles:
        return 0

    cfg = get_settings()
    for article in articles[: cfg.readly_poll_max_articles]:
        try:
            ext_resp = await client.get(
                f"{readly_url}/api/articles/extract",
                params={"index": article["index"]},
            )
            if ext_resp.status_code != 200:
                continue
            ext_data = ext_resp.json()
            if ext_data.get("error"):
                continue
            if await _ingest_article(
                feed_id, "Magazine Articles", ext_data, issue_title=issue_title
            ):
                new_count += 1
        except Exception as exc:
            log.warning("Readly legacy extract failed index %s: %s", article.get("index"), exc)

    return new_count


async def poll_readly_articles() -> int:
    """
    Poll Readly via watchlist API or legacy single-page mode.
    Returns new item count.
    """
    cfg = get_settings()
    if not cfg.readly_enabled or not cfg.readly_mcp_url:
        return 0

    readly_url = cfg.readly_mcp_url.rstrip("/")
    watchlist = get_effective_readly_watchlist()
    timeout = httpx.Timeout(120.0, connect=15.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if not watchlist:
            try:
                count = await _poll_legacy_single_page(client, readly_url)
                log.info("Readly legacy poll: %d new articles", count)
                return count
            except Exception as exc:
                log.warning("Readly legacy poll failed: %s", exc)
                return 0

        new_count = 0
        for magazine_name in watchlist:
            try:
                nav = await client.get(
                    f"{readly_url}/api/magazines/latest",
                    params={"name": magazine_name},
                )
                if nav.status_code != 200:
                    log.warning(
                        "Readly: latest issue HTTP %s for '%s'",
                        nav.status_code,
                        magazine_name,
                    )
                    continue
                nav_body = nav.json()
                if not nav_body.get("success"):
                    log.warning(
                        "Readly: could not open '%s': %s",
                        magazine_name,
                        nav_body.get("error", "unknown"),
                    )
                    continue

                batch = await client.get(
                    f"{readly_url}/api/articles/read-all",
                    params={"max": cfg.readly_poll_max_articles},
                )
                if batch.status_code != 200:
                    log.warning(
                        "Readly: read-all HTTP %s for '%s'",
                        batch.status_code,
                        magazine_name,
                    )
                    continue
                data = batch.json()
                if data.get("extraction_failed") or not data.get("articles"):
                    log.warning(
                        "Readly: no articles for '%s' (%s)",
                        magazine_name,
                        data.get("reason") or data.get("error") or "empty",
                    )
                    continue

                feed_id = await _get_or_create_readly_feed(magazine_name)
                await _ensure_bundle_for_magazine(magazine_name, feed_id)
                issue_title = data.get("issue_title") or magazine_name

                for article in data.get("articles", []):
                    if await _ingest_article(
                        feed_id, magazine_name, article, issue_title=issue_title
                    ):
                        new_count += 1

            except Exception as exc:
                log.warning("Readly poll failed for '%s': %s", magazine_name, exc)

        log.info(
            "Readly watchlist: %d new articles across %d magazines",
            new_count,
            len(watchlist),
        )
        return new_count
