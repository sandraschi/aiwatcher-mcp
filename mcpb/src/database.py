"""
Database layer — aiosqlite, schema, CRUD helpers.
Single file for scaffold; split into models/crud if it grows.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from aiwatcher_mcp.config import get_settings

log = logging.getLogger(__name__)

_db_initialized = False
_init_lock = asyncio.Lock()
_db_conn: aiosqlite.Connection | None = None
_db_pool_lock = asyncio.Lock()


def clear_db_init_guard() -> None:
    """Reset idempotent init guard (tests that DROP schema must call before init_db)."""
    global _db_initialized
    _db_initialized = False


async def close_db_pool() -> None:
    """Close the shared SQLite connection (tests and shutdown)."""
    global _db_conn
    async with _db_pool_lock:
        if _db_conn is not None:
            await _db_conn.close()
            _db_conn = None


async def _get_pooled_connection() -> aiosqlite.Connection:
    global _db_conn
    cfg = get_settings()
    import os

    os.makedirs(os.path.dirname(cfg.db_path) or ".", exist_ok=True)
    async with _db_pool_lock:
        if _db_conn is None:
            # Orphan-process fix (2026-06-11): aiosqlite.Connection is a
            # non-daemon worker thread. Mark it daemon BEFORE awaiting (i.e.
            # before the thread starts) so interpreter shutdown never blocks
            # on it if lifespan teardown is skipped (hard cancel, EOF races).
            _pending = aiosqlite.connect(cfg.db_path)
            _pending.daemon = True
            _db_conn = await _pending
            _db_conn.row_factory = aiosqlite.Row
            await _db_conn.execute("PRAGMA journal_mode=WAL")
            await _db_conn.execute("PRAGMA foreign_keys=ON")
        return _db_conn


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS feeds (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    url                  TEXT NOT NULL UNIQUE,
    feed_type            TEXT NOT NULL DEFAULT 'rss',  -- rss | atom | email | custom
    enabled              INTEGER NOT NULL DEFAULT 1,
    last_fetched         TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id           INTEGER REFERENCES feeds(id) ON DELETE CASCADE,
    guid              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    url               TEXT UNIQUE,
    summary           TEXT,
    content_html      TEXT,
    published_at      TEXT,
    fetched_at        TEXT NOT NULL DEFAULT (datetime('now')),
    is_read           INTEGER NOT NULL DEFAULT 0,
    relevance_score   REAL,
    urgency_score     REAL,
    tags              TEXT,           -- JSON array
    distilled_at      TEXT,
    distilled_summary TEXT,
    llm_provider      TEXT,
    score_reason      TEXT,
    sent_email        INTEGER NOT NULL DEFAULT 0,
    sent_robofang     INTEGER NOT NULL DEFAULT 0,
    sent_calibre      INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS bundles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    topic            TEXT,
    system_prompt    TEXT NOT NULL,
    alert_threshold  REAL NOT NULL DEFAULT 8.5,
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bundle_feeds (
    bundle_id INTEGER REFERENCES bundles(id) ON DELETE CASCADE,
    feed_id   INTEGER REFERENCES feeds(id) ON DELETE CASCADE,
    PRIMARY KEY (bundle_id, feed_id)
);

CREATE TABLE IF NOT EXISTS bundle_item_distillations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id         INTEGER REFERENCES bundles(id) ON DELETE CASCADE,
    item_id           INTEGER REFERENCES items(id) ON DELETE CASCADE,
    relevance_score   REAL,
    urgency_score     REAL,
    summary           TEXT,
    tags              TEXT,           -- JSON array
    reason            TEXT,
    llm_provider      TEXT,
    distilled_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(bundle_id, item_id)
);

-- FTS5 virtual table for full-text search over items
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    summary,
    distilled_summary,
    content=items,
    content_rowid=id
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS items_fts_insert
AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, summary, distilled_summary)
    VALUES (new.id, new.title, coalesce(new.summary,''), coalesce(new.distilled_summary,''));
END;

CREATE TRIGGER IF NOT EXISTS items_fts_update
AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary, distilled_summary)
    VALUES ('delete', old.id, old.title, coalesce(old.summary,''), coalesce(old.distilled_summary,''));
    INSERT INTO items_fts(rowid, title, summary, distilled_summary)
    VALUES (new.id, new.title, coalesce(new.summary,''), coalesce(new.distilled_summary,''));
END;

CREATE TRIGGER IF NOT EXISTS items_fts_delete
AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary, distilled_summary)
    VALUES ('delete', old.id, old.title, coalesce(old.summary,''), coalesce(old.distilled_summary,''));
END;

CREATE INDEX IF NOT EXISTS idx_items_feed    ON items(feed_id);
CREATE INDEX IF NOT EXISTS idx_items_fetched ON items(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_urgency ON items(urgency_score DESC);
CREATE INDEX IF NOT EXISTS idx_items_read    ON items(is_read);
CREATE INDEX IF NOT EXISTS idx_items_url     ON items(url);
"""

DEFAULT_FEEDS = [
    ("Alpha Signal", "newsletter@alphasignal.ai", "email"),
    ("The Decoder", "https://the-decoder.com/feed/", "rss"),
    ("Import AI (Jack Clark)", "https://importai.substack.com/feed", "rss"),
    (
        "AI News (Reuters)",
        "https://news.google.com/rss/search?q=site:reuters.com+technology&hl=en-US&gl=US&ceid=US:en",
        "rss",
    ),
    ("HN / AI/ML", "https://hnrss.org/newest?q=AI+machine+learning&points=50", "rss"),
    (
        "Anthropic Blog",
        "https://news.google.com/rss/search?q=site:anthropic.com/news+OR+site:anthropic.com/research&hl=en-US&gl=US&ceid=US:en",
        "rss",
    ),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml", "rss"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "rss"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/", "rss"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/feed/", "rss"),
    ("MIT News AI", "https://news.mit.edu/rss/topic/artificial-intelligence2", "rss"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "rss"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss", "rss"),
]

#: After this many consecutive failures a feed is auto-disabled.
FEED_AUTO_DISABLE_THRESHOLD = 5


@asynccontextmanager
async def get_db():
    yield await _get_pooled_connection()


async def init_db() -> None:
    global _db_initialized
    async with _init_lock:
        if _db_initialized:
            return
        async with get_db() as db:
            await db.executescript(SCHEMA)
            await db.commit()

            # Simple schema migrations for 'feeds' table
            try:
                await db.execute(
                    "ALTER TABLE feeds ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0"
                )
                await db.execute("ALTER TABLE feeds ADD COLUMN last_error TEXT")
                await db.commit()
                log.info("Migrated feeds table: added consecutive_failures and last_error")
            except aiosqlite.OperationalError:
                pass

            # Simple schema migrations for 'items' table
            columns_to_add = [
                ("llm_provider", "TEXT"),
                ("score_reason", "TEXT"),
                ("sent_email", "INTEGER NOT NULL DEFAULT 0"),
                ("sent_robofang", "INTEGER NOT NULL DEFAULT 0"),
                ("sent_calibre", "INTEGER NOT NULL DEFAULT 0"),
            ]

            for col_name, col_def in columns_to_add:
                try:
                    await db.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_def}")
                    await db.commit()
                    log.info("Migrated items table: added %s", col_name)
                except aiosqlite.OperationalError:
                    pass

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

            # Bundle Migration: Create 'Sandra's AI Research' as the default bundle
            async with db.execute(
                "SELECT id FROM bundles WHERE name='Sandra''s AI Research'"
            ) as cur:
                bundle_row = await cur.fetchone()

            if not bundle_row:
                from aiwatcher_mcp.distillation import SANDRA_SYSTEM

                cur = await db.execute(
                    "INSERT INTO bundles(name, topic, system_prompt) VALUES (?,?,?)",
                    ("Sandra's AI Research", "Artificial Intelligence", SANDRA_SYSTEM),
                )
                bundle_id = cur.lastrowid
                await db.commit()
                log.info("Created default bundle: Sandra's AI Research (id=%d)", bundle_id)

                await db.execute(
                    "INSERT OR IGNORE INTO bundle_feeds (bundle_id, feed_id) SELECT ?, id FROM feeds",
                    (bundle_id,),
                )

                await db.execute(
                    """INSERT OR IGNORE INTO bundle_item_distillations
                       (bundle_id, item_id, relevance_score, urgency_score, summary, tags, reason, llm_provider, distilled_at)
                       SELECT ?, id, relevance_score, urgency_score, distilled_summary, tags, score_reason, llm_provider, distilled_at
                       FROM items WHERE distilled_at IS NOT NULL""",
                    (bundle_id,),
                )
                await db.commit()
                log.info("Migrated existing item distillations to default bundle")

            await ensure_fleet_bundle_presets(db)

        _db_initialized = True


async def ensure_fleet_bundle_presets(db: aiosqlite.Connection | None = None) -> dict[str, int]:
    """Idempotently seed fleet-maintained bundles and link feeds (existing DBs + fresh)."""
    from aiwatcher_mcp.bundle_presets import FLEET_BUNDLE_PRESETS

    created_bundles = 0
    linked_feeds = 0

    async def _run(conn: aiosqlite.Connection) -> tuple[int, int]:
        nonlocal created_bundles, linked_feeds
        for preset in FLEET_BUNDLE_PRESETS:
            bundle_meta = preset["bundle"]
            name = str(bundle_meta["name"])
            topic = str(bundle_meta.get("topic") or "")
            system_prompt = str(bundle_meta["system_prompt"])
            alert_threshold = float(bundle_meta.get("alert_threshold", 8.5))

            feed_ids: list[int] = []
            for feed_name, url, feed_type in preset["feeds"]:
                await conn.execute(
                    "INSERT OR IGNORE INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                    (feed_name, url, feed_type),
                )
                async with conn.execute("SELECT id FROM feeds WHERE url=?", (url,)) as cur:
                    row = await cur.fetchone()
                if row:
                    feed_ids.append(int(row[0]))

            async with conn.execute("SELECT id FROM bundles WHERE name=?", (name,)) as cur:
                bundle_row = await cur.fetchone()

            if bundle_row:
                bundle_id = int(bundle_row[0])
                await conn.execute(
                    """UPDATE bundles
                       SET topic=?, system_prompt=?, alert_threshold=?, enabled=1
                       WHERE id=?""",
                    (topic, system_prompt, alert_threshold, bundle_id),
                )
            else:
                cur = await conn.execute(
                    """INSERT INTO bundles(name, topic, system_prompt, alert_threshold)
                       VALUES (?,?,?,?)""",
                    (name, topic, system_prompt, alert_threshold),
                )
                bundle_id = int(cur.lastrowid)
                created_bundles += 1
                log.info("Created fleet bundle preset: %s (id=%d)", name, bundle_id)

            for feed_id in feed_ids:
                await conn.execute(
                    "INSERT OR IGNORE INTO bundle_feeds (bundle_id, feed_id) VALUES (?,?)",
                    (bundle_id, feed_id),
                )
                linked_feeds += 1

        await conn.commit()
        return created_bundles, linked_feeds

    if db is not None:
        await _run(db)
    else:
        async with get_db() as conn:
            await _run(conn)

    return {"bundles_created": created_bundles, "feed_links_touched": linked_feeds}


# ── Feed health ────────────────────────────────────────────────────────────────


async def record_feed_success(feed_id: int) -> None:
    """Reset failure counter and update last_fetched timestamp."""
    async with get_db() as db:
        await db.execute(
            """UPDATE feeds
               SET last_fetched=?, consecutive_failures=0, last_error=NULL
               WHERE id=?""",
            (datetime.now(UTC).isoformat(), feed_id),
        )
        await db.commit()


async def record_feed_failure(feed_id: int, error: str) -> bool:
    """
    Increment consecutive_failures counter, store last_error.
    Auto-disables the feed if threshold is exceeded.
    Returns True if the feed was auto-disabled.
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE feeds
               SET consecutive_failures = consecutive_failures + 1,
                   last_error = ?
               WHERE id=?""",
            (error[:500], feed_id),
        )
        await db.commit()

        async with db.execute(
            "SELECT consecutive_failures FROM feeds WHERE id=?", (feed_id,)
        ) as cur:
            row = await cur.fetchone()
            failures = row[0] if row else 0

        if failures >= FEED_AUTO_DISABLE_THRESHOLD:
            await db.execute("UPDATE feeds SET enabled=0 WHERE id=?", (feed_id,))
            await db.commit()
            log.warning("Feed id=%d auto-disabled after %d consecutive failures", feed_id, failures)
            return True
    return False


# ── Items ──────────────────────────────────────────────────────────────────────


async def upsert_item(feed_id: int, item: dict[str, Any]) -> bool:
    """
    Insert item if new (by guid or url). Returns True if inserted.
    Deduplicates on both guid (UNIQUE) and url (UNIQUE) to catch
    cross-feed duplicates where the same story appears on multiple sources.
    """
    async with get_db() as db:
        # Check url-based duplicate before attempting insert
        url = item.get("url")
        if url:
            async with db.execute("SELECT id FROM items WHERE url=?", (url,)) as cur:
                if await cur.fetchone():
                    return False

        try:
            if item.get("urgency_score") is not None:
                await db.execute(
                    """
                    INSERT INTO items (feed_id, guid, title, url, summary,
                        content_html, published_at, tags,
                        urgency_score, relevance_score, distilled_at, distilled_summary)
                    VALUES (:feed_id, :guid, :title, :url, :summary,
                        :content_html, :published_at, :tags,
                        :urgency_score, :relevance_score, :distilled_at, :distilled_summary)
                    """,
                    {
                        "feed_id": feed_id,
                        "guid": item["guid"],
                        "title": item.get("title", ""),
                        "url": url,
                        "summary": item.get("summary"),
                        "content_html": item.get("content_html"),
                        "published_at": item.get("published_at"),
                        "tags": json.dumps(item.get("tags", [])),
                        "urgency_score": item.get("urgency_score"),
                        "relevance_score": item.get("relevance_score"),
                        "distilled_at": item.get("distilled_at"),
                        "distilled_summary": item.get("distilled_summary"),
                    },
                )
            else:
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
                        "url": url,
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
    async with (
        get_db() as db,
        db.execute(
            """SELECT i.*, f.name as feed_name FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.distilled_at IS NULL
               ORDER BY i.fetched_at DESC LIMIT ?""",
            (limit,),
        ) as cur,
    ):
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_item_scores(
    item_id: int,
    relevance: float,
    urgency: float,
    summary: str,
    tags: list[str],
    llm_provider: str = "",
    score_reason: str = "",
) -> None:
    async with get_db() as db:
        await db.execute(
            """UPDATE items
               SET relevance_score=?, urgency_score=?,
                   distilled_summary=?, tags=?, distilled_at=?,
                   llm_provider=?, score_reason=?
               WHERE id=?""",
            (
                relevance,
                urgency,
                summary,
                json.dumps(tags),
                datetime.now(UTC).isoformat(),
                llm_provider,
                score_reason,
                item_id,
            ),
        )
        await db.commit()


async def get_alert_candidates(threshold: float) -> list[dict]:
    async with (
        get_db() as db,
        db.execute(
            """SELECT i.*, f.name as feed_name FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.urgency_score >= ? AND i.sent_robofang = 0
               ORDER BY i.urgency_score DESC""",
            (threshold,),
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]


async def mark_sent_robofang(item_id: int) -> None:
    async with get_db() as db:
        await db.execute("UPDATE items SET sent_robofang=1 WHERE id=?", (item_id,))
        await db.commit()


async def mark_items_sent_calibre(item_ids: list[int]) -> None:
    if not item_ids:
        return
    placeholders = ",".join("?" * len(item_ids))
    async with get_db() as db:
        await db.execute(
            f"UPDATE items SET sent_calibre=1 WHERE id IN ({placeholders})",
            item_ids,
        )
        await db.commit()


async def get_recent_items(
    hours: int = 24,
    limit: int = 50,
    offset: int = 0,
    feed_id: int | None = None,
) -> list[dict]:
    feed_clause = "AND i.feed_id = ? " if feed_id is not None else ""
    params: list = [f"-{hours} hours"]
    if feed_id is not None:
        params.append(feed_id)
    params.extend([limit, max(offset, 0)])
    async with (
        get_db() as db,
        db.execute(
            f"""SELECT i.*, f.name as feed_name, f.feed_type as feed_type FROM items i
               JOIN feeds f ON f.id = i.feed_id
               WHERE i.fetched_at >= datetime('now', ?)
               {feed_clause}
               ORDER BY COALESCE(i.urgency_score, 0) DESC, i.fetched_at DESC
               LIMIT ? OFFSET ?""",
            params,
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]


async def get_bundle_recent_items(bundle_id: int, hours: int = 24, limit: int = 50) -> list[dict]:
    """Get items and their scores for a specific bundle."""
    async with (
        get_db() as db,
        db.execute(
            """SELECT i.*, f.name as feed_name, bid.relevance_score, bid.urgency_score,
                  bid.summary as distilled_summary, bid.tags as bundle_tags
           FROM items i
           JOIN feeds f ON f.id = i.feed_id
           JOIN bundle_item_distillations bid ON bid.item_id = i.id
           WHERE bid.bundle_id = ? AND i.fetched_at >= datetime('now', ?)
           ORDER BY bid.urgency_score DESC, i.fetched_at DESC
           LIMIT ?""",
            (bundle_id, f"-{hours} hours", limit),
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]


async def get_feeds() -> list[dict]:
    async with get_db() as db, db.execute("SELECT * FROM feeds ORDER BY name") as cur:
        return [dict(r) for r in await cur.fetchall()]


# ── Bundles ────────────────────────────────────────────────────────────────────


async def get_bundles(enabled_only: bool = False) -> list[dict]:
    query = "SELECT * FROM bundles"
    if enabled_only:
        query += " WHERE enabled=1"
    query += " ORDER BY name"
    async with get_db() as db, db.execute(query) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_bundle_feeds(bundle_id: int) -> list[dict]:
    async with (
        get_db() as db,
        db.execute(
            """SELECT f.* FROM feeds f
           JOIN bundle_feeds bf ON bf.feed_id = f.id
           WHERE bf.bundle_id = ?""",
            (bundle_id,),
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]


async def add_bundle(name: str, topic: str, system_prompt: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO bundles(name, topic, system_prompt) VALUES (?,?,?)",
            (name, topic, system_prompt),
        )
        await db.commit()
        return cur.lastrowid


async def link_feed_to_bundle(feed_id: int, bundle_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO bundle_feeds(bundle_id, feed_id) VALUES (?,?)",
            (bundle_id, feed_id),
        )
        await db.commit()


async def get_undistilled_bundle_items(limit: int = 50) -> list[dict]:
    """
    Find items that need distillation for specific bundles.
    Returns list of (item_dict, bundle_dict).
    """
    async with (
        get_db() as db,
        db.execute(
            """SELECT i.*, f.name as feed_name, b.id as bundle_id, b.name as bundle_name, b.system_prompt as bundle_prompt
           FROM items i
           JOIN feeds f ON f.id = i.feed_id
           JOIN bundle_feeds bf ON bf.feed_id = f.id
           JOIN bundles b ON b.id = bf.bundle_id
           LEFT JOIN bundle_item_distillations bid ON bid.item_id = i.id AND bid.bundle_id = b.id
           WHERE b.enabled = 1 AND bid.id IS NULL
             AND (i.tags IS NULL OR i.tags = '[]' OR NOT EXISTS (
                 SELECT 1 FROM json_each(i.tags) WHERE value = 'spam'
             ))
           ORDER BY i.fetched_at DESC LIMIT ?""",
            (limit,),
        ) as cur,
    ):
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_bundle_item_scores(
    bundle_id: int,
    item_id: int,
    relevance: float,
    urgency: float,
    summary: str,
    tags: list[str],
    reason: str = "",
    llm_provider: str = "",
) -> None:
    async with get_db() as db:
        await db.execute(
            """INSERT INTO bundle_item_distillations
               (bundle_id, item_id, relevance_score, urgency_score, summary, tags, reason, llm_provider)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(bundle_id, item_id) DO UPDATE SET
                   relevance_score=excluded.relevance_score,
                   urgency_score=excluded.urgency_score,
                   summary=excluded.summary,
                   tags=excluded.tags,
                   reason=excluded.reason,
                   llm_provider=excluded.llm_provider,
                   distilled_at=datetime('now')""",
            (
                bundle_id,
                item_id,
                relevance,
                urgency,
                summary,
                json.dumps(tags),
                reason,
                llm_provider,
            ),
        )
        await db.commit()


async def get_stats() -> dict:
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM feeds WHERE enabled=1") as c:
            (feeds,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM items") as c:
            (total,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM items WHERE is_read=0") as c:
            (unread,) = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM items WHERE urgency_score >= 8.5") as c:
            (critical,) = await c.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM items WHERE fetched_at >= datetime('now', '-24 hours')"
        ) as c:
            (today,) = await c.fetchone()
        async with db.execute(
            "SELECT COUNT(*) FROM feeds WHERE consecutive_failures > 0 AND enabled=1"
        ) as c:
            (degraded,) = await c.fetchone()
        return {
            "active_feeds": feeds,
            "total_items": total,
            "unread_items": unread,
            "critical_items": critical,
            "items_last_24h": today,
            "degraded_feeds": degraded,
        }


# ── Bundle health ──────────────────────────────────────────────────────────────


async def get_bundle_stats(bundle_id: int) -> dict | None:
    """Per-bundle metrics: scored items, avg urgency, top tags, feed contributions."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, name, topic, enabled, created_at FROM bundles WHERE id=?",
            (bundle_id,),
        ) as cur:
            bundle = await cur.fetchone()
            if not bundle:
                return None

        async with db.execute(
            """SELECT COUNT(*) as scored,
                      COALESCE(AVG(urgency_score), 0) as avg_urgency,
                      COALESCE(AVG(relevance_score), 0) as avg_relevance,
                      MAX(distilled_at) as last_distilled
               FROM bundle_item_distillations WHERE bundle_id=?""",
            (bundle_id,),
        ) as cur:
            row = await cur.fetchone()

        async with db.execute(
            """SELECT tags FROM bundle_item_distillations
               WHERE bundle_id=? AND tags IS NOT NULL ORDER BY distilled_at DESC LIMIT 500""",
            (bundle_id,),
        ) as cur:
            tag_counts: dict[str, int] = {}
            async for r in cur:
                for tag in json.loads(r["tags"] or "[]"):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            top_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:10]

        async with db.execute(
            """SELECT f.name, f.id as feed_id,
                      COUNT(bid.id) as items,
                      COALESCE(AVG(bid.urgency_score), 0) as avg_urgency
               FROM feeds f
               JOIN bundle_feeds bf ON bf.feed_id = f.id
               LEFT JOIN items i ON i.feed_id = f.id
               LEFT JOIN bundle_item_distillations bid ON bid.item_id = i.id
                   AND bid.bundle_id = ?
               WHERE bf.bundle_id = ?
               GROUP BY f.id
               ORDER BY items DESC LIMIT 10""",
            (bundle_id, bundle_id),
        ) as cur:
            source_feeds = [dict(r) for r in await cur.fetchall()]

        return {
            "bundle_id": bundle["id"],
            "name": bundle["name"],
            "topic": bundle["topic"],
            "enabled": bool(bundle["enabled"]),
            "items_scored": row["scored"],
            "avg_urgency": round(row["avg_urgency"], 1),
            "avg_relevance": round(row["avg_relevance"], 1),
            "last_distilled": row["last_distilled"],
            "top_tags": top_tags,
            "source_feeds": source_feeds,
        }


# ── Cross-feed dedup ─────────────────────────────────────────────────────────


async def _find_similar_item(
    title: str,
    exclude_feed_id: int,
    summary: str | None = None,
) -> dict | None:
    """Find duplicate-ish items (title and/or title+summary) within 48h."""
    async with (
        get_db() as db,
        db.execute(
            """SELECT id, title, summary, url, feed_id, fetched_at
           FROM items
           WHERE feed_id != ? AND fetched_at >= datetime('now', '-48 hours')
           ORDER BY fetched_at DESC""",
            (exclude_feed_id,),
        ) as cur,
    ):
        rows = await cur.fetchall()
        if not rows:
            return None

    from difflib import SequenceMatcher

    norm_title = title.lower().strip()
    norm_body = f"{title} {summary or ''}".lower().strip()
    best_score = 0.0
    best_match = None
    for row in rows:
        existing_title = (row["title"] or "").lower().strip()
        existing_body = f"{row['title']} {row['summary'] or ''}".lower().strip()
        title_ratio = SequenceMatcher(None, norm_title, existing_title).ratio()
        body_ratio = SequenceMatcher(None, norm_body, existing_body).ratio()
        ratio = max(title_ratio, body_ratio)
        if ratio > best_score:
            best_score = ratio
            best_match = dict(row)

    if best_score >= 0.85 and best_match:
        return best_match
    return None


# ── Digest persistence ─────────────────────────────────────────────────────────


async def save_digest(
    html_body: str,
    text_body: str,
    item_count: int,
    period_hours: int = 24,
    recipients: list[str] | None = None,
) -> int:
    """Persist a generated digest to the digests table. Returns new digest id."""
    now = datetime.now(UTC)
    from datetime import timedelta

    period_from = (now - timedelta(hours=period_hours)).isoformat()
    period_to = now.isoformat()

    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO digests
               (period_from, period_to, html_body, text_body, item_count, recipients)
               VALUES (?,?,?,?,?,?)""",
            (
                period_from,
                period_to,
                html_body,
                text_body,
                item_count,
                json.dumps(recipients or []),
            ),
        )
        await db.commit()
        log.info("Digest saved: id=%d (%d items)", cur.lastrowid, item_count)
        return cur.lastrowid


async def mark_digest_sent(digest_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE digests SET sent_at=? WHERE id=?",
            (datetime.now(UTC).isoformat(), digest_id),
        )
        await db.commit()


async def get_recent_digests(limit: int = 10) -> list[dict]:
    async with (
        get_db() as db,
        db.execute(
            """SELECT id, created_at, period_from, period_to, item_count, sent_at
           FROM digests ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]


async def get_cached_digest(hours: int, ttl_minutes: int) -> dict[str, Any] | None:
    """Return the newest digest body if generated within ttl_minutes (skip LLM regen)."""
    if ttl_minutes <= 0:
        return None
    async with (
        get_db() as db,
        db.execute(
            """SELECT html_body, text_body, item_count, period_from, period_to
           FROM digests
           WHERE datetime(created_at) >= datetime('now', ?)
           ORDER BY created_at DESC LIMIT 1""",
            (f"-{ttl_minutes} minutes",),
        ) as cur,
    ):
        row = await cur.fetchone()
    if not row or not (row["html_body"] or row["text_body"]):
        return None
    count = row["item_count"] or 0
    return {
        "subject": f"AIWatcher Digest — {count} items (cached, last {hours}h)",
        "html_body": row["html_body"] or "",
        "text_body": row["text_body"] or "",
        "_cached": True,
        "period_from": row["period_from"],
        "period_to": row["period_to"],
    }


# ── Retention / expiry ────────────────────────────────────────────────────────


async def expire_old_items(retention_days: int = 90) -> int:
    """
    Delete items older than retention_days, EXCEPT those with urgency_score >= 8.5
    (critical items are kept permanently).
    Returns count of deleted rows.
    """
    async with get_db() as db:
        cur = await db.execute(
            """DELETE FROM items
               WHERE fetched_at < datetime('now', ?)
               AND (urgency_score IS NULL OR urgency_score < 8.5)""",
            (f"-{retention_days} days",),
        )
        await db.commit()
        deleted = cur.rowcount
        if deleted:
            log.info("Retention: deleted %d items older than %d days", deleted, retention_days)
        return deleted


# ── Full-text search ──────────────────────────────────────────────────────────


async def search_items(query: str, limit: int = 20) -> list[dict]:
    """
    Full-text search over item title, summary, and distilled_summary using FTS5.
    Returns items sorted by relevance (BM25 rank).
    """
    async with (
        get_db() as db,
        db.execute(
            """SELECT i.*, f.name as feed_name
           FROM items i
           JOIN feeds f ON f.id = i.feed_id
           WHERE i.id IN (
               SELECT rowid FROM items_fts WHERE items_fts MATCH ?
               ORDER BY rank LIMIT ?
           )
           ORDER BY COALESCE(i.urgency_score, 0) DESC""",
            (query, limit),
        ) as cur,
    ):
        return [dict(r) for r in await cur.fetchall()]
