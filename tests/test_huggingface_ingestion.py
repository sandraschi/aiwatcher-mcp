"""Tests for Hugging Face author watchlist ingestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _hf_env(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_ENABLED", "true")
    monkeypatch.setenv("HF_WATCHLIST", "Jackrong")
    monkeypatch.setenv("HF_INCLUDE_PAPERS", "false")
    monkeypatch.setenv("HF_INCLUDE_MODELS", "false")
    monkeypatch.setenv("HF_INCLUDE_MODIFIED", "false")
    monkeypatch.setenv("HF_INCLUDE_TRENDING", "false")
    monkeypatch.setenv("HF_DISCOVERY_ENABLED", "false")
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    import aiwatcher_mcp.huggingface_ingestion as hi

    hi._FEED_CACHE.clear()
    hi.set_runtime_hf_watchlist(None)
    yield
    cfg_mod._settings = None
    hi._FEED_CACHE.clear()
    hi.set_runtime_hf_watchlist(None)


def test_hf_watchlist_parsed_from_env():
    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()
    assert cfg.parsed_hf_watchlist() == ["Jackrong"]


def test_runtime_hf_watchlist_override():
    from aiwatcher_mcp.huggingface_ingestion import (
        get_effective_hf_watchlist,
        set_runtime_hf_watchlist,
    )

    set_runtime_hf_watchlist(["Qwen", "bartowski"])
    assert get_effective_hf_watchlist() == ["Qwen", "bartowski"]


def test_has_real_weights_requires_size_floor():
    from aiwatcher_mcp.huggingface_ingestion import _has_real_weights

    empty = {
        "siblings": [{"rfilename": "model.safetensors", "size": 100}],
        "cardData": {},
    }
    assert _has_real_weights(empty, 1_000_000) is False

    weighted = {
        "siblings": [{"rfilename": "model-Q4_K_M.gguf", "size": 5_000_000_000}],
        "cardData": {},
    }
    assert _has_real_weights(weighted, 1_000_000) is True

    card_only = {"siblings": [], "cardData": {"base_model": "Qwen/Qwopus-27B"}}
    assert _has_real_weights(card_only, 1_000_000) is True


def test_cluster_key_uses_base_model():
    from aiwatcher_mcp.huggingface_ingestion import _cluster_key

    quant = {
        "modelId": "bartowski/Qwopus-27B-GGUF",
        "cardData": {"base_model": "Jackrong/Qwopus-27B-v4"},
    }
    base = {"modelId": "Jackrong/Qwopus-27B-v4", "cardData": {}}
    assert _cluster_key(quant) == _cluster_key(base)


@pytest.mark.asyncio
async def test_poll_watchlist_clusters_quants(fresh_db):
    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface

    base_model = {
        "modelId": "Jackrong/Qwopus-27B-v4",
        "createdAt": "2026-07-27T10:00:00Z",
        "description": "New drop",
        "tags": ["llm"],
        "siblings": [{"rfilename": "model.safetensors", "size": 50_000_000_000}],
        "cardData": {"language": ["en"]},
    }
    quant = {
        "modelId": "bartowski/Qwopus-27B-v4-GGUF",
        "createdAt": "2026-07-27T11:00:00Z",
        "tags": ["gguf"],
        "siblings": [{"rfilename": "Qwopus-Q4_K_M.gguf", "size": 15_000_000_000}],
        "cardData": {"base_model": "Jackrong/Qwopus-27B-v4"},
    }
    placeholder = {
        "modelId": "Jackrong/empty-placeholder",
        "createdAt": "2026-07-27T09:00:00Z",
        "siblings": [],
        "cardData": {},
    }

    mock_client = AsyncMock()

    def _mock_get(url, params=None):
        resp = MagicMock()
        resp.status_code = 200
        if params and params.get("author") == "Jackrong":
            resp.json.return_value = [placeholder, base_model, quant]
        else:
            resp.json.return_value = []
        return resp

    mock_client.get = AsyncMock(side_effect=_mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("aiwatcher_mcp.huggingface_ingestion.httpx.AsyncClient", return_value=mock_client):
        results = await poll_huggingface()

    assert results.get("watchlist") == 1

    from aiwatcher_mcp.database import get_db

    async with (
        get_db() as db,
        db.execute("SELECT title, summary FROM items WHERE feed_id IS NOT NULL") as cur,
    ):
        rows = await cur.fetchall()

    assert len(rows) == 1
    assert "Qwopus-27B-v4" in rows[0]["title"]
    assert "+1 quants" in rows[0]["title"]
    assert "bartowski/Qwopus-27B-v4-GGUF" in rows[0]["summary"]
    assert "empty-placeholder" not in rows[0]["summary"]


@pytest.mark.asyncio
async def test_poll_disabled_returns_empty(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("HUGGINGFACE_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface

    assert await poll_huggingface() == {}
