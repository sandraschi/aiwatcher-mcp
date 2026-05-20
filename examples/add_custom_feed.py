"""
Add a custom RSS/Atom feed to the aiwatcher database.

Usage:
    uv run python examples/add_custom_feed.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    from aiwatcher_mcp.database import get_db, init_db

    await init_db()

    feeds_to_add = [
        ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "rss"),
        ("LessWrong (AI Safety)", "https://www.lesswrong.com/feed.xml?view=frontpage", "rss"),
        ("AI Alignment Forum", "https://www.alignmentforum.org/feed.xml", "rss"),
    ]

    async with get_db() as db:
        for name, url, feed_type in feeds_to_add:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                    (name, url, feed_type),
                )
                print(f"Added: {name}")
            except Exception as exc:
                print(f"Failed to add {name}: {exc}")
        await db.commit()

    print("\nDone. Run poll_and_distill.py to fetch items from new feeds.")


if __name__ == "__main__":
    asyncio.run(main())
