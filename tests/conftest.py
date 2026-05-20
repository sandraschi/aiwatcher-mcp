"""
Shared test fixtures for aiwatcher-mcp.

Key design decision: aiosqlite opens a NEW connection per `async with get_db()` call.
SQLite in-memory databases (:memory:) are NOT shared between connections, so each
get_db() call would see an empty database.

Solution: use a temp file DB path, set via env var before any import of config.
The `fresh_db` fixture (autouse in each test module) re-creates the schema for each test.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Return a per-session temp file path for SQLite."""
    db_file = tmp_path_factory.mktemp("db") / "test_aiwatcher.db"
    return str(db_file)


@pytest.fixture(autouse=True, scope="session")
def configure_test_env(tmp_db_path: str) -> None:
    """Set env vars BEFORE any module import touches config."""
    os.environ["DB_PATH"] = tmp_db_path
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("LLM_PROVIDER", "anthropic")
    os.environ.setdefault("ROBOFANG_ENABLED", "true")
    os.environ.setdefault("ROBOFANG_BACKEND_URL", "http://localhost:10871")
    os.environ.setdefault("SPEECHOPS_HTTP_URL", "http://localhost:10895")
    os.environ.setdefault("EMAIL_ENABLED", "false")
    os.environ.setdefault("CALIBRE_ENABLED", "false")
    os.environ.setdefault("GMAIL_ENABLED", "false")

    # Reset the settings singleton so it re-reads the env vars
    import aiwatcher_mcp.config as cfg_mod
    cfg_mod._settings = None
