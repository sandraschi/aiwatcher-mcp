"""Per-feed signal quality (decay) metrics for health dashboards."""

from __future__ import annotations

from typing import Any

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db


async def get_feed_quality_map() -> dict[int, dict[str, Any]]:
    """Average urgency per feed over the configured decay window."""
    cfg = get_settings()
    async with get_db() as db, db.execute(
        """SELECT f.id AS feed_id,
                  COUNT(i.id) AS scored_count,
                  AVG(i.urgency_score) AS avg_urgency
           FROM feeds f
           LEFT JOIN items i ON i.feed_id = f.id
               AND i.urgency_score IS NOT NULL
               AND i.fetched_at >= datetime('now', ?)
           GROUP BY f.id""",
        (f"-{cfg.feed_decay_days} days",),
    ) as cur:
        rows = await cur.fetchall()

    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        fid = int(row["feed_id"])
        count = int(row["scored_count"] or 0)
        avg = float(row["avg_urgency"] or 0)
        if count < cfg.feed_decay_min_items:
            flag = "insufficient_data"
        elif avg < cfg.feed_decay_urgency_threshold:
            flag = "low_signal"
        else:
            flag = "healthy"
        out[fid] = {
            "scored_count_30d": count,
            "avg_urgency_30d": round(avg, 2),
            "quality_flag": flag,
        }
    return out


async def enrich_feeds_with_quality(feeds: list[dict]) -> list[dict]:
    quality = await get_feed_quality_map()
    enriched = []
    for f in feeds:
        row = dict(f)
        q = quality.get(int(row["id"]), {})
        row.update(q)
        enriched.append(row)
    return enriched
