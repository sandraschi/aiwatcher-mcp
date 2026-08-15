"""Ingest structured events from other fleet members into the items table."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from aiwatcher_mcp.database import (
    get_db,
    record_feed_success,
    update_bundle_item_scores,
    upsert_item,
)

log = logging.getLogger(__name__)

_FLEET_FEED_ID: int | None = None


async def _fleet_feed_id() -> int:
    global _FLEET_FEED_ID
    if _FLEET_FEED_ID is not None:
        return _FLEET_FEED_ID
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE feed_type='fleet' AND name='Fleet Events'"
        ) as cur:
            row = await cur.fetchone()
        if row:
            _FLEET_FEED_ID = int(row["id"])
            return _FLEET_FEED_ID
        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            ("Fleet Events", "fleet://local/events", "fleet"),
        )
        await db.commit()
        _FLEET_FEED_ID = int(cur.lastrowid or 0)
        return _FLEET_FEED_ID


async def _mirror_pre_distilled_to_bundles(
    feed_id: int,
    item_id: int,
    *,
    relevance: float,
    urgency: float,
    summary: str,
    tags: list[str],
    source: str,
) -> int:
    """Write bundle_item_distillations for bundles linked to this feed (code-hunt drops)."""
    async with (
        get_db() as db,
        db.execute("SELECT bundle_id FROM bundle_feeds WHERE feed_id=?", (feed_id,)) as cur,
    ):
        bundle_ids = [int(r["bundle_id"]) for r in await cur.fetchall()]

    for bundle_id in bundle_ids:
        await update_bundle_item_scores(
            bundle_id,
            item_id,
            relevance,
            urgency,
            summary,
            tags,
            reason=f"fleet pre-distilled ({source})",
            llm_provider="fleet-ingest",
        )
    return len(bundle_ids)


async def ingest_fleet_event(
    *,
    title: str,
    summary: str = "",
    source: str = "fleet",
    url: str = "",
    urgency_hint: float | None = None,
) -> dict:
    """
    Record a fleet-originated event (PR merge, robot mission, calibre import, etc.)
    for inclusion in distillation and digests.
    """
    feed_id = await _fleet_feed_id()
    stamp = datetime.now(UTC).isoformat()
    guid_src = f"{source}:{title}:{stamp}"
    guid = f"fleet:{hashlib.sha256(guid_src.encode()).hexdigest()[:24]}"
    body = summary[:4000] if summary else f"Fleet event from {source}"
    tags = ["fleet-event", source]
    item = {
        "guid": guid,
        "title": title[:500],
        "url": url or None,
        "summary": body,
        "content_html": None,
        "published_at": stamp,
        "tags": tags,
    }
    if urgency_hint is not None:
        score = min(10.0, max(0.0, float(urgency_hint)))
        item["urgency_score"] = score
        item["relevance_score"] = score
        item["distilled_at"] = stamp
        item["distilled_summary"] = body

    inserted = await upsert_item(feed_id, item)
    await record_feed_success(feed_id)

    from aiwatcher_mcp.update_interests import sync_interests_from_config

    await sync_interests_from_config()

    bundle_links = 0
    if urgency_hint is not None:
        async with get_db() as db, db.execute("SELECT id FROM items WHERE guid=?", (guid,)) as cur:
            row = await cur.fetchone()
        if row:
            bundle_links = await _mirror_pre_distilled_to_bundles(
                feed_id,
                int(row["id"]),
                relevance=item["relevance_score"],
                urgency=item["urgency_score"],
                summary=body,
                tags=tags,
                source=source,
            )

    log.info("Fleet event %s: %s", "inserted" if inserted else "duplicate", title[:80])

    # P3 surge: high-urgency fleet events (incl. arxiv codehunt live drops, which
    # already push here) fan out to the hub inbox immediately - best effort.
    if urgency_hint is not None and float(urgency_hint) >= 0:
        from aiwatcher_mcp.surge import surge_fanout

        await surge_fanout(
            title=title,
            summary=body,
            urgency=float(urgency_hint),
            source=f"fleet:{source}",
            url=url,
        )

    return {
        "success": True,
        "inserted": inserted,
        "guid": guid,
        "feed_id": feed_id,
        "source": source,
        "bundle_links": bundle_links,
    }
