"""Tests for bundles.py — fleet JSON load/save and elicitation mock."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


def test_load_save_fleet_bundles(tmp_path, monkeypatch):
    import aiwatcher_mcp.bundles as bundles_mod

    bundles_path = tmp_path / "bundles.json"
    monkeypatch.setattr(bundles_mod, "get_bundles_json_path", lambda: str(bundles_path))

    bundles_mod.save_fleet_bundles([{"id": "b1", "name": "Test Bundle"}])
    loaded = bundles_mod.load_fleet_bundles()

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Test Bundle"


@pytest.mark.asyncio
async def test_elicit_bundle_config_parses_json(monkeypatch):
    import aiwatcher_mcp.bundles as bundles_mod

    raw = json.dumps(
        {
            "name": "Robotics",
            "system_prompt": "Score robotics news.",
            "suggested_feeds": [{"name": "IEEE", "url": "https://example.com/feed", "type": "rss"}],
        }
    )

    suggested = [{"name": "IEEE", "url": "https://example.com/feed", "type": "rss"}]
    with (
        patch(
            "aiwatcher_mcp.bundles._get_llm_response",
            new_callable=AsyncMock,
            return_value=raw,
        ),
        patch(
            "aiwatcher_mcp.bundles._probe_feed_urls",
            new_callable=AsyncMock,
            return_value=suggested,
        ),
    ):
        config = await bundles_mod.elicit_bundle_config("robotics")

    assert config["name"] == "Robotics"
    assert "robotics" in config["system_prompt"].lower()
    assert len(config["suggested_feeds"]) == 1
