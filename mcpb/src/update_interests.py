"""
Sync interests.json configuration with the database.
Updates bundles and links feeds based on patterns.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
from pathlib import Path

from aiwatcher_mcp.database import get_db

log = logging.getLogger(__name__)


async def sync_interests(json_path: str | Path = "interests.json"):
    path = Path(json_path)
    if not path.exists():
        log.error("Config file not found: %s", path)
        return

    with open(path, encoding="utf-8") as f:
        config = json.load(f)

    interests = config.get("interests", [])
    async with get_db() as db:
        # 1. Update/Insert Bundles
        for int_cfg in interests:
            name = int_cfg["name"]
            topic = int_cfg.get("topic")
            prompt = int_cfg["system_prompt"]
            threshold = int_cfg.get("alert_threshold", 8.5)
            enabled = 1 if int_cfg.get("enabled", True) else 0

            await db.execute(
                """INSERT INTO bundles (name, topic, system_prompt, alert_threshold, enabled)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     topic=excluded.topic,
                     system_prompt=excluded.system_prompt,
                     alert_threshold=excluded.alert_threshold,
                     enabled=excluded.enabled""",
                (name, topic, prompt, threshold, enabled),
            )

            # Get bundle_id
            async with db.execute("SELECT id FROM bundles WHERE name=?", (name,)) as cur:
                bundle_id = (await cur.fetchone())["id"]

            # 2. Link Feeds based on patterns
            patterns = int_cfg.get("feed_patterns", [])
            if not patterns:
                continue

            # Clear existing links for this bundle to allow fresh sync?
            # Or just keep adding? Fresh sync is safer for config management.
            await db.execute("DELETE FROM bundle_feeds WHERE bundle_id=?", (bundle_id,))

            async with db.execute("SELECT id, name FROM feeds") as cur:
                feeds = await cur.fetchall()

            for feed in feeds:
                matches = False
                for pattern in patterns:
                    if fnmatch.fnmatch(feed["name"], pattern):
                        matches = True
                        break

                if matches:
                    await db.execute(
                        "INSERT OR IGNORE INTO bundle_feeds (bundle_id, feed_id) VALUES (?, ?)",
                        (bundle_id, feed["id"]),
                    )

            log.info("Synced bundle '%s' (id=%d) with %d patterns", name, bundle_id, len(patterns))

        await db.commit()
    log.info("Interest synchronization complete.")


async def sync_interests_from_config() -> None:
    """Sync bundles/feed links using resolved interests.json path from settings."""
    from aiwatcher_mcp.config import get_settings

    path = get_settings().resolved_interests_path()
    if path.exists():
        await sync_interests(path)
    else:
        log.debug("sync_interests_from_config skipped — %s not found", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_interests())
