"""Tests for fleet bundle presets (IDE Host Signal)."""

from __future__ import annotations

import pytest


def test_ide_host_feeds_non_empty():
    from aiwatcher_mcp.bundle_presets import IDE_HOST_FEEDS

    assert len(IDE_HOST_FEEDS) >= 8
    for name, url, feed_type in IDE_HOST_FEEDS:
        assert name
        assert url.startswith("http")
        assert feed_type in ("rss", "atom", "email", "custom")


def test_ide_host_bundle_metadata():
    from aiwatcher_mcp.bundle_presets import IDE_HOST_BUNDLE

    assert IDE_HOST_BUNDLE["name"] == "IDE Host Signal"
    assert IDE_HOST_BUNDLE["alert_threshold"] == 8.0
    assert "changelog-gap" in IDE_HOST_BUNDLE["system_prompt"]


def test_fleet_presets_registered():
    from aiwatcher_mcp.bundle_presets import FLEET_BUNDLE_PRESETS, IDE_HOST_BUNDLE

    names = {p["bundle"]["name"] for p in FLEET_BUNDLE_PRESETS}
    assert IDE_HOST_BUNDLE["name"] in names


@pytest.mark.asyncio
async def test_scheduler_status_shape():
    from aiwatcher_mcp.scheduler import get_scheduler_status

    status = get_scheduler_status()
    assert "running" in status
    assert "jobs" in status
    assert isinstance(status["jobs"], list)
    assert status["feed_poll_interval_minutes"] >= 1
