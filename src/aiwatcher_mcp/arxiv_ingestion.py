"""
ArXiv research paper ingestion.
Pulls latest papers from configured categories via arxiv-mcp REST API.
"""

from __future__ import annotations

import logging

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_failure, record_feed_success, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)


async def _get_or_create_arxiv_feed(category: str) -> int:
    """Ensure an 'arxiv' type feed exists for the category, return its id."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='arxiv'",
            (f"ArXiv: {category}",),
        ) as cur:
            row = await cur.fetchone()

        if row:
            return row["id"]

        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            (f"ArXiv: {category}", category, "arxiv"),
        )
        await db.commit()
        log.info("Created arxiv feed id=%d for %s", cur.lastrowid, category)
        return int(cur.lastrowid or 0)


def _paper_id(p: dict) -> str | None:
    """arxiv-mcp returns paper_id; older mocks may use arxiv_id."""
    pid = p.get("paper_id") or p.get("arxiv_id")
    return str(pid).strip() if pid else None


async def poll_arxiv() -> dict[str, int]:
    """
    Fetch latest papers from all configured ArXiv categories.
    Returns {category: new_count}.
    """
    cfg = get_settings()
    if not cfg.arxiv_enabled or not cfg.arxiv_mcp_url:
        return {}

    categories = [c.strip() for c in cfg.arxiv_categories.split(",") if c.strip()]
    results: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        for cat in categories:
            feed_id = await _get_or_create_arxiv_feed(cat)
            try:
                resp = await client.get(
                    f"{cfg.arxiv_mcp_url.rstrip('/')}/api/category/latest",
                    params={"category": cat, "limit": 25, "hours": 24},
                )
                resp.raise_for_status()
                data = resp.json()
                papers = data.get("papers", [])

                new_count = 0
                skipped_no_id = 0
                for p in papers:
                    arxiv_id = _paper_id(p)
                    if not arxiv_id:
                        skipped_no_id += 1
                        continue

                    guid = f"arxiv:{arxiv_id}"
                    item = {
                        "guid": guid,
                        "title": p.get("title", "(no title)"),
                        "url": p.get("abs_url") or f"https://arxiv.org/abs/{arxiv_id}",
                        "summary": p.get("summary") or p.get("abstract"),
                        "content_html": None,
                        "published_at": p.get("published"),
                        "tags": (p.get("categories") or []) + ["arxiv", cat],
                    }

                    result, reason = Scrubber().check_item(item)
                    if result in ("spam", "scam"):
                        log.info(
                            "ArXiv scrubber blocked '%s' [%s]: %s",
                            p.get("title", "")[:60],
                            result,
                            reason,
                        )
                        continue

                    if await upsert_item(feed_id, item):
                        new_count += 1

                if papers and skipped_no_id == len(papers):
                    log.error(
                        "ArXiv %s: %d papers returned but none had paper_id/arxiv_id — "
                        "check arxiv-mcp API field names",
                        cat,
                        len(papers),
                    )

                await record_feed_success(feed_id)
                results[cat] = new_count
                log.info("ArXiv %s: %d new papers", cat, new_count)

            except Exception as exc:
                log.error("Failed to poll ArXiv category %s: %s", cat, exc)
                await record_feed_failure(feed_id, str(exc))
                results[cat] = 0

    if results:
        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()

    return results
