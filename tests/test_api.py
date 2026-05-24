"""
Integration tests for api.py — Starlette REST endpoints.
Uses httpx.AsyncClient with the Starlette app directly (no network).
DB uses the session-scoped temp-file from conftest.py.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
async def fresh_db():
    from aiwatcher_mcp.database import get_db
    async with get_db() as db:
        await db.executescript(
            "DROP TABLE IF EXISTS items_fts;"
            "DROP TRIGGER IF EXISTS items_fts_insert;"
            "DROP TRIGGER IF EXISTS items_fts_update;"
            "DROP TRIGGER IF EXISTS items_fts_delete;"
            "DROP TABLE IF EXISTS digests;"
            "DROP TABLE IF EXISTS items;"
            "DROP TABLE IF EXISTS feeds;"
        )
        await db.commit()
    from aiwatcher_mcp.database import init_db
    await init_db()


@pytest.fixture()
def client():
    """Return a configured AsyncClient pointed at the Starlette app."""
    from aiwatcher_mcp.api import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Stats ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_stats(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_feeds" in data
    assert "total_items" in data
    assert data["active_feeds"] > 0  # default feeds seeded


# ── Feeds ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_feeds_list(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/feeds")
    assert resp.status_code == 200
    data = resp.json()
    assert "feeds" in data
    assert len(data["feeds"]) > 0


@pytest.mark.asyncio
async def test_api_add_feed(client: AsyncClient):
    async with client as c:
        resp = await c.post(
            "/api/feeds/add",
            json={"name": "Test Feed", "url": "https://test.example.com/rss", "feed_type": "rss"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_api_add_feed_duplicate_returns_error(client: AsyncClient):
    payload = {"name": "Dup Feed", "url": "https://dup.example.com/rss"}
    async with client as c:
        await c.post("/api/feeds/add", json=payload)
        resp = await c.post("/api/feeds/add", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_api_feed_health(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/feeds/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "feeds" in data
    assert "count" in data
    # All feeds start healthy
    assert all(f["consecutive_failures"] == 0 for f in data["feeds"])


@pytest.mark.asyncio
async def test_api_toggle_feed(client: AsyncClient):
    from aiwatcher_mcp.database import get_db
    async with get_db() as db, db.execute("SELECT id, enabled FROM feeds LIMIT 1") as c:
        row = await c.fetchone()
    feed_id, original_enabled = row["id"], row["enabled"]

    from aiwatcher_mcp.api import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        resp = await c.post(f"/api/feeds/{feed_id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify the enabled flag flipped
    from aiwatcher_mcp.database import get_db
    async with get_db() as db, db.execute("SELECT enabled FROM feeds WHERE id=?", (feed_id,)) as cur:
        (new_enabled,) = await cur.fetchone()
    assert new_enabled != original_enabled


# ── Items ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_items_empty(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_api_items_returns_recent(client: AsyncClient):
    from aiwatcher_mcp.database import upsert_item
    await upsert_item(1, {
        "guid": "api-test-guid-001",
        "title": "API Test Item",
        "url": "https://example.com/api-test",
        "summary": "Test summary for API",
        "content_html": None,
        "published_at": None,
        "tags": [],
    })

    async with client as c:
        resp = await c.get("/api/items?hours=24&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    titles = [i["title"] for i in data["items"]]
    assert "API Test Item" in titles


# ── Search ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_search_requires_query(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/search")
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_api_search_finds_inserted_item(client: AsyncClient):
    from aiwatcher_mcp.database import upsert_item
    await upsert_item(1, {
        "guid": "fts-test-guid-001",
        "title": "Anthropic Releases Magnificent Claude",
        "url": "https://example.com/fts-test",
        "summary": "A huge milestone for large language models.",
        "content_html": None,
        "published_at": None,
        "tags": [],
    })

    async with client as c:
        resp = await c.get("/api/search?q=Anthropic+Claude")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    titles = [i["title"] for i in data["items"]]
    assert any("Claude" in t for t in titles)


@pytest.mark.asyncio
async def test_api_search_no_results(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/search?q=xyznonexistentterm123")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ── Digest history ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_digest_history_empty(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/digest/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["digests"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_api_digest_history_after_save(client: AsyncClient):
    from aiwatcher_mcp.database import save_digest
    await save_digest(
        html_body="<html>test</html>",
        text_body="test",
        item_count=5,
        period_hours=24,
        recipients=["sandra@example.com"],
    )

    async with client as c:
        resp = await c.get("/api/digest/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["digests"][0]["item_count"] == 5


# ── Retention ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_expire_items(client: AsyncClient):
    async with client as c:
        resp = await c.post("/api/items/expire")
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted" in data
    assert "retention_days" in data
    assert data["deleted"] == 0  # no old items in fresh DB


# ── Config reload ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_config_reload(client: AsyncClient):
    async with client as c:
        resp = await c.post("/api/config/reload")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "llm_provider" in data
    assert "alert_threshold" in data


# ── Capabilities ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_capabilities(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "tool_surface" in data
    assert "features" in data
    tools = data["tool_surface"]["atomic_tools"]
    assert isinstance(tools, list)
    assert len(tools) >= 8
    assert data["tool_surface"]["total"] == len(tools)


def test_redact_env_dict_masks_secrets() -> None:
    from aiwatcher_mcp.api import redact_env_dict

    src = {"FOO": "bar", "ANTHROPIC_API_KEY": "sk-secret", "PUBLIC": "visible"}
    out = redact_env_dict(src)
    assert out["FOO"] == "bar"
    assert out["ANTHROPIC_API_KEY"] == "***REDACTED***"
    assert out["PUBLIC"] == "visible"


# ── Bundle health ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_bundle_health(client: AsyncClient):
    from aiwatcher_mcp.database import get_bundles
    bundles = await get_bundles(enabled_only=True)
    bundle_id = bundles[0]["id"]

    async with client as c:
        resp = await c.get(f"/api/bundles/{bundle_id}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["bundle_id"] == bundle_id
    assert "items_scored" in data


@pytest.mark.asyncio
async def test_api_bundle_health_404(client: AsyncClient):
    async with client as c:
        resp = await c.get("/api/bundles/99999/health")
    assert resp.status_code == 404


# ── OPML import ───────────────────────────────────────────────────────────────

OPML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>Test OPML</title></head><body>
<outline text="AI News" title="AI News">
  <outline type="rss" text="Test OPML Feed" title="Test OPML Feed" xmlUrl="https://example.com/opml-feed"/>
  <outline type="rss" text="Another Feed" title="Another Feed" xmlUrl="https://example.com/opml-feed2"/>
</outline>
</body></opml>"""


@pytest.mark.asyncio
async def test_api_opml_import(client: AsyncClient):
    async with client as c:
        resp = await c.post("/api/opml/import", json={"opml_xml": OPML_SAMPLE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["imported"]) == 2


@pytest.mark.asyncio
async def test_api_opml_import_empty(client: AsyncClient):
    async with client as c:
        resp = await c.post("/api/opml/import", json={})
    assert resp.status_code == 400
    assert "error" in resp.json()
