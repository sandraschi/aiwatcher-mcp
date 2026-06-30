"""Tag frequency trends over scored items."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from aiwatcher_mcp.database import get_db


async def get_tag_trends(*, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
    """Top tags from item and bundle distillation JSON over the last N days."""
    async with (
        get_db() as db,
        db.execute(
            """SELECT tags FROM items
           WHERE tags IS NOT NULL
             AND fetched_at >= datetime('now', ?)
           UNION ALL
           SELECT tags FROM bundle_item_distillations
           WHERE tags IS NOT NULL
             AND distilled_at >= datetime('now', ?)""",
            (f"-{days} days", f"-{days} days"),
        ) as cur,
    ):
        rows = await cur.fetchall()

    counter: Counter[str] = Counter()
    for row in rows:
        raw = row["tags"]
        if not raw:
            continue
        try:
            tags = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str) and t.strip():
                    counter[t.strip().lower()] += 1

    return [{"tag": tag, "count": count} for tag, count in counter.most_common(limit)]
