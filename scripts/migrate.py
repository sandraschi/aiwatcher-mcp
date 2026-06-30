"""
DB migration runner — applies incremental schema changes safely.

Migrations are numbered sequentially. Each migration is idempotent (uses
CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS patterns via ALTER TABLE
with exception handling).

Usage:
    uv run python scripts/migrate.py
    uv run python scripts/migrate.py --db data/aiwatcher.db
    uv run python scripts/migrate.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Callable

import aiosqlite

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Migration registry ─────────────────────────────────────────────────────────
# Each entry: (version: int, description: str, fn: async (db) -> None)
# Always append; never reorder or delete.

MigrationFn = Callable[[aiosqlite.Connection], None]

MIGRATIONS: list[tuple[int, str, object]] = []


def migration(version: int, description: str) -> Callable:
    """Decorator to register a migration function."""

    def decorator(fn: MigrationFn) -> MigrationFn:
        MIGRATIONS.append((version, description, fn))
        return fn

    return decorator


# ── Migrations ──────────────────────────────────────────────────────────────────


@migration(1, "Initial schema — baseline (no-op if tables already exist)")
async def migrate_001(db: aiosqlite.Connection) -> None:
    # Re-runs the baseline schema — all statements are IF NOT EXISTS so safe.
    from aiwatcher_mcp.database import SCHEMA

    await db.executescript(SCHEMA)


@migration(2, "Add llm_provider column to items (tracks which model scored the item)")
async def migrate_002(db: aiosqlite.Connection) -> None:
    try:
        await db.execute("ALTER TABLE items ADD COLUMN llm_provider TEXT")
        log.info("Added items.llm_provider column")
    except Exception:
        # Column already exists — sqlite raises OperationalError
        log.debug("items.llm_provider already exists, skipping")


@migration(3, "Add score_reason column to items (one-sentence scoring rationale)")
async def migrate_003(db: aiosqlite.Connection) -> None:
    try:
        await db.execute("ALTER TABLE items ADD COLUMN score_reason TEXT")
        log.info("Added items.score_reason column")
    except Exception:
        log.debug("items.score_reason already exists, skipping")


@migration(4, "Add feed health columns: consecutive_failures, last_error")
async def migrate_004(db: aiosqlite.Connection) -> None:
    for col, defn in [
        ("consecutive_failures", "INTEGER NOT NULL DEFAULT 0"),
        ("last_error", "TEXT"),
    ]:
        try:
            await db.execute(f"ALTER TABLE feeds ADD COLUMN {col} {defn}")
            log.info("Added feeds.%s column", col)
        except Exception:
            log.debug("feeds.%s already exists, skipping", col)


@migration(5, "Add FTS5 virtual table and triggers for full-text search on items")
async def migrate_005(db: aiosqlite.Connection) -> None:
    # Create FTS table if not exists
    await db.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            title,
            summary,
            distilled_summary,
            content=items,
            content_rowid=id
        );

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
    """)
    # Rebuild FTS index from existing rows
    await db.execute("INSERT INTO items_fts(items_fts) VALUES ('rebuild')")
    await db.commit()
    log.info("FTS5 table, triggers, and index rebuild complete")


@migration(6, "Add URL unique index on items (cross-feed deduplication)")
async def migrate_006(db: aiosqlite.Connection) -> None:
    try:
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_items_url_unique ON items(url) WHERE url IS NOT NULL"
        )
        await db.commit()
        log.info("Added unique index on items.url")
    except Exception as exc:
        # If there are existing duplicate URLs this will fail — log and skip
        log.warning("Could not create unique index on items.url (duplicates exist?): %s", exc)


@migration(7, "Add llm_provider and score_reason columns to items if missing")
async def migrate_007(db: aiosqlite.Connection) -> None:
    # Defensive: columns may already exist from migrate_002/003 on fresh DBs
    for col, defn in [
        ("llm_provider", "TEXT"),
        ("score_reason", "TEXT"),
    ]:
        try:
            await db.execute(f"ALTER TABLE items ADD COLUMN {col} {defn}")
            log.info("Added items.%s column", col)
        except Exception:
            log.debug("items.%s already exists, skipping", col)


# ── Runner ──────────────────────────────────────────────────────────────────────


async def create_migrations_table(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    await db.commit()


async def get_applied_versions(db: aiosqlite.Connection) -> set[int]:
    async with db.execute("SELECT version FROM _migrations") as cur:
        rows = await cur.fetchall()
    return {r[0] for r in rows}


async def run_migrations(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await create_migrations_table(db)
        applied = await get_applied_versions(db)
        pending = [(v, d, fn) for v, d, fn in sorted(MIGRATIONS) if v not in applied]

        if not pending:
            log.info("Database is up to date — no pending migrations.")
            return

        for version, description, fn in pending:
            log.info("Applying migration %03d: %s", version, description)
            await fn(db)
            await db.execute(
                "INSERT INTO _migrations(version, description) VALUES (?,?)",
                (version, description),
            )
            await db.commit()
            log.info("Migration %03d applied.", version)

        log.info("All migrations complete.")


async def list_migrations(db_path: str) -> None:
    try:
        async with aiosqlite.connect(db_path) as db:
            await create_migrations_table(db)
            applied = await get_applied_versions(db)
    except Exception:
        applied = set()

    print(f"\n{'Ver':>4}  {'Status':<10}  Description")
    print("─" * 60)
    for version, description, _ in sorted(MIGRATIONS):
        status = "applied" if version in applied else "pending"
        print(f"{version:>4}  {status:<10}  {description}")


def main() -> None:
    parser = argparse.ArgumentParser(description="aiwatcher-mcp DB migration runner")
    parser.add_argument("--db", default="data/aiwatcher.db", help="Path to SQLite DB")
    parser.add_argument("--list", action="store_true", help="List migrations without applying")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_migrations(args.db))
    else:
        asyncio.run(run_migrations(args.db))


if __name__ == "__main__":
    main()
