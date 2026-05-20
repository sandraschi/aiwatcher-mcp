"""
Query top-scored items from the last 24 hours.

Usage:
    uv run python examples/query_top_items.py
    uv run python examples/query_top_items.py --hours 48 --limit 20
"""

from __future__ import annotations

import argparse
import asyncio


async def main(hours: int, limit: int) -> None:
    from aiwatcher_mcp.database import get_recent_items

    items = await get_recent_items(hours=hours, limit=limit)
    if not items:
        print(f"No items in the last {hours}h.")
        return

    print(f"\nTop {len(items)} items — last {hours}h\n{'─' * 70}")
    for item in items:
        u = item.get("urgency_score") or 0
        r = item.get("relevance_score") or 0
        badge = "🔴" if u >= 9 else "🟡" if u >= 7 else "🔵" if u >= 5 else "⚪"
        print(f"{badge} U={u:.1f} R={r:.1f}  {item['title'][:75]}")
        if item.get("distilled_summary"):
            print(f"   {item['distilled_summary'][:120]}")
        print(f"   {item.get('url', '')[:80]}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query top AIWatcher items")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()
    asyncio.run(main(args.hours, args.limit))
