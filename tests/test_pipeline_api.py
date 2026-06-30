"""REST tests for pipeline liveness, fleet ingest, scrubber reload."""

from __future__ import annotations

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response


@pytest.fixture()
def client():
    from aiwatcher_mcp.api import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_pipeline_liveness_endpoint(client: AsyncClient, monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ARXIV_ENABLED", "true")
    monkeypatch.setenv("ARXIV_MCP_URL", "http://arxiv.test")
    monkeypatch.setenv("VLA_MCP_ENABLED", "false")
    cfg_mod._settings = None

    upstream = {"success": True, "healthy": True, "alerts": [], "checks": []}
    with respx.mock:
        respx.get("http://arxiv.test/api/health").mock(
            return_value=Response(200, json={"status": "ok"})
        )
        respx.get("http://arxiv.test/api/pipeline/liveness").mock(
            return_value=Response(200, json=upstream)
        )
        async with client as c:
            resp = await c.get("/api/pipeline/liveness?stale_hours=48")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "alerts" in data
    assert "checked_at" in data
    assert data.get("upstream") == upstream


@pytest.mark.asyncio
async def test_fleet_ingest_rest(client: AsyncClient):
    async with client as c:
        resp = await c.post(
            "/api/fleet/ingest",
            json={
                "title": "[code-drop] FunASR release",
                "summary": "cs.SD paper weights live",
                "source": "arxiv-codehunt",
                "url": "https://github.com/example/funasr",
                "urgency_hint": 8.5,
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["inserted"] is True


@pytest.mark.asyncio
async def test_fleet_ingest_populates_bundle_distillation(
    client: AsyncClient, tmp_path, monkeypatch
):
    import aiwatcher_mcp.config as cfg_mod

    interests = {
        "interests": [
            {
                "name": "China Open Weights",
                "topic": "t",
                "system_prompt": "json",
                "feed_patterns": ["Fleet Events"],
            }
        ]
    }
    path = tmp_path / "interests.json"
    path.write_text(__import__("json").dumps(interests), encoding="utf-8")
    monkeypatch.setenv("INTERESTS_JSON_PATH", str(path))
    cfg_mod._settings = None

    async with client as c:
        await c.post(
            "/api/fleet/ingest",
            json={
                "title": "Drop",
                "summary": "repo live",
                "source": "arxiv-codehunt",
                "urgency_hint": 9.0,
            },
        )

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT COUNT(*) AS n FROM bundle_item_distillations") as cur,
    ):
        row = await cur.fetchone()
    assert row["n"] >= 1


@pytest.mark.asyncio
async def test_scrubber_reload_rest(client: AsyncClient):
    async with client as c:
        resp = await c.post("/api/scrubber/reload")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reloaded"
