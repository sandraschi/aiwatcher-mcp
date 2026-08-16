"""Tests for Intel hub digest publishing (date sanity + payload)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from aiwatcher_mcp.intel_hub_client import publish_digest_to_hub


def _vienna_today() -> str:
    try:
        return datetime.now(ZoneInfo("Europe/Vienna")).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


@pytest.mark.asyncio
async def test_hub_title_always_carries_today_date(monkeypatch):
    """A hallucinated/stale LLM subject must never reach the hub title."""
    captured: dict = {}

    async def _fake_publish(**kwargs):
        captured.update(kwargs)
        return {"success": True, "report_id": kwargs.get("report_id")}

    monkeypatch.setattr("aiwatcher_mcp.intel_hub_client.publish_to_intel_hub", _fake_publish)

    stale = {
        "subject": "AIWatcher daily digest - 2025-08-26",
        "html_body": "<p>x</p>",
        "text_body": "t",
    }
    out = await publish_digest_to_hub(stale)
    assert out["success"] is True
    assert _vienna_today() in captured["title"]
    assert "2025-08-26" not in captured["title"]
    assert captured["report_id"] == "daily-digest"


@pytest.mark.asyncio
async def test_hub_title_keeps_correct_llm_subject(monkeypatch):
    captured: dict = {}

    async def _fake_publish(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr("aiwatcher_mcp.intel_hub_client.publish_to_intel_hub", _fake_publish)

    good = {"subject": f"AIWatcher Daily Digest - {_vienna_today()}", "html_body": "<p>x</p>"}
    await publish_digest_to_hub(good)
    assert captured["title"] == good["subject"]
    assert "Daily Digest" in captured["title"]
