"""Tests for pipeline_liveness.py."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_wrong_port_alerts(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("ARXIV_ENABLED", "true")
    monkeypatch.setenv("ARXIV_MCP_URL", "http://localhost:10719")
    cfg_mod._settings = None

    from aiwatcher_mcp.pipeline_liveness import check_pipeline_liveness

    result = await check_pipeline_liveness(stale_hours=48)
    codes = {a["code"] for a in result["alerts"]}
    assert "ARXIV_MCP_WRONG_PORT" in codes
    assert result["healthy"] is False
