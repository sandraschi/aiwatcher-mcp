"""
Manually trigger the alert pipeline — same logic as the 04:55 UTC scheduled job.

Usage:
    uv run python examples/trigger_alert.py
"""

from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    from aiwatcher_mcp.alerting import process_alerts
    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()
    print(f"Alert threshold: {cfg.alert_threshold}")
    print(f"Robofang enabled: {cfg.robofang_enabled}")

    alerted = await process_alerts()
    if alerted:
        print(f"\nAlerted {len(alerted)} item(s):")
        for title in alerted:
            print(f"  - {title[:80]}")
    else:
        print(f"\nNo items above threshold {cfg.alert_threshold}.")


if __name__ == "__main__":
    asyncio.run(main())
