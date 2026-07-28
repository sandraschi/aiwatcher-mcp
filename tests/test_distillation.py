"""
Integration tests for distillation.py — LLM scoring and digest generation.
LLM calls mocked; DB uses temp file (shared connections).
Tests force LLM_PROVIDER=anthropic to match the mocked client.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_SCORE_JSON = {
    "relevance_score": 9.0,
    "urgency_score": 8.5,
    "tags": ["claude", "anthropic", "release"],
    "summary": "Anthropic releases Claude 5 with significant capability improvements.",
    "reason": "Direct tooling impact for Sandra's fleet.",
}
MOCK_SCORE_RESPONSE = json.dumps(MOCK_SCORE_JSON)

MOCK_DIGEST_RESPONSE = json.dumps(
    {
        "subject": "AIWatcher Digest \u2014 1 item",
        "html_body": "<html><body>Test digest</body></html>",
        "text_body": "Test digest plain text",
    }
)


@pytest.fixture(autouse=True)
async def distill_test_state(fresh_db):
    import aiwatcher_mcp.config as cfg_mod
    import aiwatcher_mcp.distillation as dist_mod

    dist_mod._DISTILL_SEMAPHORE = None
    cfg_mod._settings = None


@pytest.fixture(autouse=True)
def _force_anthropic_provider(monkeypatch):
    """All distillation tests use Anthropic — the only provider we can mock cleanly."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("CLOUD_PROVIDERS_ALLOWED", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DISTILLATION_FLASH_ENABLED", "false")
    # Prevent _get_llm_response from hanging on ollama/lmstudio fallback when mock fails
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "deepseek-v4-flash")
    # Reset cached settings singleton so new env takes effect
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None


async def _insert_test_item() -> int:
    """Insert a single undistilled item; returns its id."""
    from aiwatcher_mcp.database import get_bundles, get_db, link_feed_to_bundle, upsert_item

    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO feeds(name, url) VALUES (?,?)",
            ("Test Feed", "https://example.com/rss"),
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM feeds WHERE url=?", ("https://example.com/rss",)
        ) as c:
            row = await c.fetchone()
            feed_id = row[0]

    bundles = await get_bundles(enabled_only=True)
    assert bundles, "Expected at least one enabled bundle from init_db presets"
    await link_feed_to_bundle(feed_id, bundles[0]["id"])

    inserted = await upsert_item(
        feed_id,
        {
            "guid": "test-guid-001",
            "title": "Claude 5 Released",
            "url": "https://example.com/claude-5",
            "summary": "Major capability release from Anthropic.",
            "content_html": None,
            "published_at": None,
            "tags": [],
        },
    )
    assert inserted

    async with get_db() as db, db.execute("SELECT id FROM items WHERE guid='test-guid-001'") as cur:
        row = await cur.fetchone()
        return row[0]


def _make_anthropic_mock(response_text: str) -> MagicMock:
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)
    return mock_client


@pytest.mark.asyncio
async def test_distill_items_processes_undistilled():
    await _insert_test_item()

    with patch("anthropic.AsyncAnthropic", return_value=_make_anthropic_mock(MOCK_SCORE_RESPONSE)):
        from aiwatcher_mcp.distillation import distill_items

        processed = await distill_items(batch_size=5)

    assert processed == 1


@pytest.mark.asyncio
async def test_distill_items_returns_zero_when_nothing_pending():
    from aiwatcher_mcp.distillation import distill_items

    result = await distill_items(batch_size=10)
    assert result == 0


@pytest.mark.asyncio
async def test_distill_items_survives_llm_error():
    await _insert_test_item()

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        from aiwatcher_mcp.distillation import distill_items

        processed = await distill_items(batch_size=5)

    assert processed == 0


@pytest.mark.asyncio
async def test_distill_strips_markdown_fences():
    await _insert_test_item()

    fenced = f"```json\n{MOCK_SCORE_RESPONSE}\n```"
    with patch("anthropic.AsyncAnthropic", return_value=_make_anthropic_mock(fenced)):
        from aiwatcher_mcp.distillation import distill_items

        processed = await distill_items(batch_size=5)

    assert processed == 1


@pytest.mark.asyncio
async def test_generate_digest_returns_fallback_when_no_items():
    from aiwatcher_mcp.distillation import generate_digest

    result = await generate_digest(hours=24)
    assert "subject" in result
    assert result["subject"] == "No news today"


@pytest.mark.asyncio
async def test_build_fallback_digest_structure():
    from aiwatcher_mcp.distillation import _build_fallback_digest

    items = [
        {
            "title": "Item One",
            "url": "https://example.com/1",
            "urgency": 9.0,
            "relevance": 8.0,
            "source": "Test",
            "summary": "Summary one.",
            "tags": [],
        },
        {
            "title": "Item Two",
            "url": "https://example.com/2",
            "urgency": 5.0,
            "relevance": 6.0,
            "source": "Test",
            "summary": "Summary two.",
            "tags": [],
        },
    ]
    result = _build_fallback_digest(items, hours=24)

    assert "subject" in result
    assert "html_body" in result
    assert "text_body" in result
    assert "Item One" in result["html_body"]
    assert "Item Two" in result["text_body"]
