"""
Database layer — aiosqlite, schema, CRUD helpers.
Single file for scaffold; split into models/crud if it grows.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from aiwatcher_mcp.config import get_settings

log = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS feeds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    feed_type   TEXT NOT NULL DEFAULT 'rss',  -- rss | atom | email | custom
    enabled     INTEGER NOT NULL DEFAULT 1,
    last_fetched TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id         INTEGER REFERENCES feeds(id) ON DELETE CASCADE,
    guid            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    url             TEXT,
    summary         TEXT,
    content_html    TEXT,
    published_at    TEXT,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    is_read         INTEGER NOT NULL DEFAULT 0,
    relevance_score REAL,           -- 0-10 from Claude
    urgency_score   REAL,           -- 0-10 from Claude
    tags            TEXT,           -- JSON array
    distilled_at    TEXT,
    distilled_summary TEXT,
    sent_email      INTEGER NOT NULL DEFAULT 0,
    sent_robofang   INTEGER NOT NULL DEFAULT 0,
    sent_calibre    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS digests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    period_from TEXT NOT NULL,
    period_to   TEXT NOT NULL,
    html_body   TEXT NOT NULL,
    text_body   TEXT NOT NULL,
    item_count  INTEGER NOT NULL DEFAULT 0,
    sent_at     TEXT,
    recipients  TEXT  -- JSON array
);

CREATE INDEX IF NOT EXISTS idx_items_feed    ON items(feed_id);
CREATE INDEX IF NOT EXISTS idx_items_fetched ON items(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_urgency ON items(urgency_score DESC);
CREATE INDEX IF NOT EXISTS idx_items_read    ON items(is_read);
"""

DEFAULT_FEEDS = [
    ("Alpha Signal (RSS)", "https://alphasignal.ai/rss", "rss"),
    ("The Decoder", "https://the-decoder.com/feed/", "rss"),
    ("Import AI (Jack Clark)", "https://importai.substack.com/feed", "rss"),
    ("AI News (Reuters)", "https://feeds.reuters.com/reuters/technologyNews", "rss"),
    ("HN — AI/ML", "https://hnrss.org/newest?q=AI+machine+learning&points=50", "rss"),
    ("Anthropic Blog", "https://www.anthropic.com/rss.xml", "rss"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml", "rss"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "rss"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/feed/", "rss"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "rss"),
]


@asynccontextmanager
async def get_db():
    cfg = get_settings()
    import os
    os.makedirs(os.path.dirname(cfg.db_path) or ".", exist_ok=True)
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript(SCHEMA)
        await db.commit()
        # Seed default feeds if table is empty
        async with db.execute("SELECT COUNT(*) FROM feeds") as cur:
            (count,) = await cur.fetchone()
        if count == 0:
            await db.executemany(
                "INSERT OR IGNORE INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                DEFAULT_FEEDS,
            )
            await db.commit()
            log.info("Seeded %d default feeds", len(DEFAULT_FEEDS))


# ── Items ──────────────────────────────────────────────────────────────────────

async def upsert_item(feed_id: int, item: dict[str, Any]) -> bool:
    """Insert item if new. Returns True if inserted."""
    async with get_db() as db:
        try:
            await db.execute(
                """
                INSERT INTO items (feed_id, guid, title, url, summary,
                    content_html, published_at, tags)
                VALUES (:feed_id, :guid, :title, :url, :summary,
                    :content_html, :published_at, :tags)
                """,
                {
                    "feed_id": feed_id,
                    "guid": item["guid"],
                    "title": item.get("title", ""),
                    "url": item.get("url"),
                    "summary": item.get("summary"),
                    "content_html": item.get("content_html"),
                    "published_at": item.get("published_at"),
                    "tags": json.dumps(item.get("tags", [])),
                },
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_undistilled_items(limit: int = 100) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.*, f.name as feed_name FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.distilled_at IS NULL
               ORDER BY i.fetched_at DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_item_scores(
    item_id: int,
    relevance: float,
    urgency: float,
    summary: str,
    tags: list[str],
) -> None:
    async with get_db() as db:
        await db.execute(
            """UPDATE items SET relevance_score=?, urgency_score=?,
               distilled_summary=?, tags=?, distilled_at=?
               WHERE id=?""",
            (
                relevance,
                urgency,
                summary,
                json.dumps(tags),
                datetime.now(timezone.utc).isoformat(),
                item_id,
            ),
        )
        await db.commit()


async def get_alert_candidates(threshold: float) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.*, f.name as feed_name FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.urgency_score >= ? AND i.sent_robofang = 0
               ORDER BY i.urgency_score DESC""",
            (threshold,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def mark_sent_robofang(item_id: int) -> None:
    async with get_db() as db:
        await db.execute("UPDATE items SET sent_robofang=1 WHERE id=?", (item_id,))
        await db.commit()


async def get_recent_items(hours: int = 24, limit: int = 50) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.*, f.name as feed_name FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.fetched_at >= datetime('now', ?)
               ORDER BY COALESCE(i.urgency_score, 0) DESC, i.fetched_at DESC
               LIMIT ?""",
            (f"-{hours} hours", limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_feeds() -> list[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM feeds ORDER BY name") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_stats() -> dict:
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM feeds WHERE enabled=1") as c:
            (feeds,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM items") as c:
            (total,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM items WHERE is_read=0") as c:
            (unread,) = await c.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM items WHERE urgency_score >= 8.5"
        ) as c:
            (critical,) = await c.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM items WHERE fetched_at >= datetime('now', '-24 hours')"
        ) as c:
            (today,) = await c.fetchone()
        return {
            "active_feeds": feeds,
            "total_items": total,
            "unread_items": unread,
            "critical_items": critical,
            "items_last_24h": today,
        }
