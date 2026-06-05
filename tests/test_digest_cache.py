"""Tests for digest TTL cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_cached_digest_within_ttl(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod
    from aiwatcher_mcp.database import get_cached_digest, save_digest

    monkeypatch.setenv("DIGEST_CACHE_TTL_MINUTES", "120")
    cfg_mod._settings = None

    await save_digest(
        html_body="<p>cached</p>",
        text_body="cached",
        item_count=3,
        period_hours=24,
    )

    hit = await get_cached_digest(24, 120)
    assert hit is not None
    assert hit.get("_cached") is True
    assert "cached" in hit["html_body"]


@pytest.mark.asyncio
async def test_generate_digest_uses_cache(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod
    from aiwatcher_mcp.database import save_digest
    from aiwatcher_mcp.distillation import generate_digest

    monkeypatch.setenv("DIGEST_CACHE_TTL_MINUTES", "120")
    cfg_mod._settings = None

    await save_digest(
        html_body="<p>from-db</p>",
        text_body="from-db",
        item_count=1,
        period_hours=24,
    )

    llm = AsyncMock(side_effect=AssertionError("LLM should not run on cache hit"))
    with patch("aiwatcher_mcp.distillation._get_llm_response", llm):
        result = await generate_digest(hours=24)

    assert result.get("_cached") is True
    assert "from-db" in result["html_body"]
    llm.assert_not_called()
