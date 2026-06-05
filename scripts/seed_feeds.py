"""Seed baseline RSS feeds when the feeds table is empty."""

from __future__ import annotations

import asyncio
import sys

# Curated baseline — AI / robotics / fleet-adjacent (verify URLs periodically).
BASELINE_FEEDS: tuple[tuple[str, str, str], ...] = (
    ("Anthropic Blog", "https://www.anthropic.com/news.rss", "rss"),
    ("OpenAI Blog", "https://openai.com/news/rss.xml", "rss"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "rss"),
    ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI", "rss"),
    ("arXiv cs.RO", "https://export.arxiv.org/rss/cs.RO", "rss"),
    ("arXiv cs.LG", "https://export.arxiv.org/rss/cs.LG", "rss"),
    ("arXiv cs.SD", "https://export.arxiv.org/rss/cs.SD", "rss"),
    ("The Decoder", "https://the-decoder.com/feed/", "rss"),
    ("HN — AI & LLM", "https://hnrss.org/newest?q=AI+LLM", "rss"),
    ("FastMCP Releases", "https://github.com/jlowin/fastmcp/releases.atom", "atom"),
)


async def seed_feeds(*, force: bool = False) -> dict:
    from aiwatcher_mcp.database import get_db, init_db

    await init_db()
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM feeds") as cur:
            (existing,) = await cur.fetchone()
        if existing and not force:
            return {"skipped": True, "reason": "feeds_already_populated", "existing": existing}

        inserted = 0
        for name, url, feed_type in BASELINE_FEEDS:
            try:
                await db.execute(
                    "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                    (name, url, feed_type),
                )
                inserted += 1
            except Exception as exc:
                if "UNIQUE" not in str(exc).upper():
                    raise
        await db.commit()
    return {"skipped": False, "inserted": inserted, "baseline_count": len(BASELINE_FEEDS)}


def main() -> int:
    force = "--force" in sys.argv
    result = asyncio.run(seed_feeds(force=force))
    print(result)
    return 0 if result.get("skipped") or result.get("inserted", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
