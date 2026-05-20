"""
One-shot: poll all feeds then distill new items with Claude.

Usage:
    uv run python examples/poll_and_distill.py
"""

from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    # Must init DB first (creates tables + seeds default feeds if empty)
    from aiwatcher_mcp.database import init_db
    await init_db()

    from aiwatcher_mcp.ingestion import poll_all_feeds
    results = await poll_all_feeds()
    total_new = sum(results.values())
    print(f"\nPolled {len(results)} feeds — {total_new} new items")
    for name, count in sorted(results.items(), key=lambda x: -x[1]):
        if count:
            print(f"  {name}: +{count}")

    if total_new == 0:
        print("Nothing new. Run again in 30 min.")
        return

    from aiwatcher_mcp.distillation import distill_items
    processed = await distill_items(batch_size=20)
    print(f"\nDistilled {processed} items")


if __name__ == "__main__":
    asyncio.run(main())
