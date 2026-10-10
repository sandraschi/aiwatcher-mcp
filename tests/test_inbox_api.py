"""Inbox REST surface: scan skips session-scribe review notes, safe file preview.

data/inbox mixes two things: analysis drops meant for ingestion and
session_scribe.py review notes ("REVIEW: promote real work ... then
delete this"). Review notes must never be bulk-ingested as news items.
Uses a temp INBOX_PATH - never the real data/inbox.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

ANALYSIS = "---\ntitle: DeepSeek funding analysis\n---\n\nReal analysis body.\n"
SCRIBE = "---\ntitle: 2026-10-09 15:00 session scribe digest\n---\n\nREVIEW: promote real work.\n"


@pytest.fixture()
def inbox(tmp_path, monkeypatch):
    d = tmp_path / "inbox"
    d.mkdir()
    (d / "2026-10-09-deepseek-analysis.md").write_text(ANALYSIS, encoding="utf-8")
    (d / "2026-10-09_15-00_session-scribe.md").write_text(SCRIBE, encoding="utf-8")
    monkeypatch.setenv("INBOX_PATH", str(d))
    import aiwatcher_mcp.config as cfg_mod
    import aiwatcher_mcp.inbox as inbox_mod

    cfg_mod._settings = None
    inbox_mod._INBOX_FEED_ID = None
    yield d
    cfg_mod._settings = None
    inbox_mod._INBOX_FEED_ID = None


def _client() -> AsyncClient:
    from aiwatcher_mcp.api import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_list_splits_analysis_and_review_notes(fresh_db, inbox):
    async with _client() as c:
        data = (await c.get("/api/inbox/list")).json()
    assert data["pending_analysis"] == ["2026-10-09-deepseek-analysis.md"]
    assert data["review_notes"] == ["2026-10-09_15-00_session-scribe.md"]
    assert len(data["pending_files"]) == 2  # unchanged contract for existing callers


@pytest.mark.asyncio
async def test_scan_ingests_analysis_and_skips_review_notes(fresh_db, inbox):
    async with _client() as c:
        resp = await c.post("/api/inbox/scan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == 1
    assert data["skipped_review_notes"] == 1
    assert (inbox / "2026-10-09-deepseek-analysis.ingested.md").exists()
    assert (inbox / "2026-10-09_15-00_session-scribe.md").exists()  # untouched

    from aiwatcher_mcp.database import get_db

    async with get_db() as db, db.execute("SELECT title FROM items") as cur:
        titles = [r["title"] for r in await cur.fetchall()]
    assert titles == ["DeepSeek funding analysis"]


@pytest.mark.asyncio
async def test_file_preview_and_traversal_guard(fresh_db, inbox):
    (inbox.parent / "secret.md").write_text("outside inbox", encoding="utf-8")
    async with _client() as c:
        ok = await c.get("/api/inbox/file", params={"name": "2026-10-09-deepseek-analysis.md"})
        traversal = await c.get("/api/inbox/file", params={"name": "../secret.md"})
        absolute = await c.get("/api/inbox/file", params={"name": str(inbox.parent / "secret.md")})
        not_md = await c.get("/api/inbox/file", params={"name": "x.txt"})
        missing = await c.get("/api/inbox/file", params={"name": "nope.md"})
    assert ok.status_code == 200
    assert "Real analysis body" in ok.json()["content"]
    assert traversal.status_code == 400
    assert absolute.status_code == 400
    assert not_md.status_code == 400
    assert missing.status_code == 404
