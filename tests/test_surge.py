"""Tests for surge mode (P3) - high-urgency fan-out to the hub inbox."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_surge_below_threshold_skips(monkeypatch):
    """Below-threshold items never touch the hub."""
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("SURGE_ENABLED", "true")
    monkeypatch.setenv("SURGE_THRESHOLD", "8.5")
    monkeypatch.setenv("SURGE_HUB_URL", "http://hub.test")
    cfg_mod._settings = None

    from aiwatcher_mcp.surge import surge_fanout

    with respx.mock:
        respx.post("http://hub.test/api/v1/inbox/send").mock(
            return_value=Response(200, json={"success": True, "message": {"id": 1}})
        )
        result = await surge_fanout(title="low", urgency=3.0)
        assert result.get("skipped") == "below threshold"
        assert not respx.calls


@pytest.mark.asyncio
async def test_surge_disabled_skips(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("SURGE_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.surge import surge_fanout

    result = await surge_fanout(title="x", urgency=9.9)
    assert result.get("skipped") == "surge disabled"


@pytest.mark.asyncio
async def test_surge_fanout_posts_to_hub(monkeypatch):
    """Urgency >= threshold POSTs to the hub inbox with the right payload."""
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("SURGE_ENABLED", "true")
    monkeypatch.setenv("SURGE_THRESHOLD", "8.5")
    monkeypatch.setenv("SURGE_HUB_URL", "http://hub.test")
    monkeypatch.setenv("SURGE_TO_ENTITY", "fritz")
    cfg_mod._settings = None

    from aiwatcher_mcp.surge import surge_fanout

    with respx.mock:
        route = respx.post("http://hub.test/api/v1/inbox/send").mock(
            return_value=Response(200, json={"success": True, "message": {"id": 42}})
        )
        result = await surge_fanout(
            title="BREAKING: open-weight model drop",
            summary="summary text",
            urgency=9.2,
            url="http://x/y",
        )
        assert result["success"] is True
        assert result["message_id"] == 42
        assert route.called
        import json

        payload = json.loads(route.calls[0].request.content.decode())
        assert payload["to_entity"] == "fritz"
        assert "BREAKING" in payload["subject"]
        assert "http://x/y" in payload["body"]


@pytest.mark.asyncio
async def test_surge_hub_down_never_raises(monkeypatch):
    """Hub unreachable must not fail the ingest pipeline."""
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("SURGE_ENABLED", "true")
    monkeypatch.setenv("SURGE_THRESHOLD", "1.0")
    monkeypatch.setenv("SURGE_HUB_URL", "http://127.0.0.1:1")  # nothing listens here
    cfg_mod._settings = None

    from aiwatcher_mcp.surge import surge_fanout

    result = await surge_fanout(title="x", urgency=9.0)
    assert result["success"] is False
    assert "error" in result
