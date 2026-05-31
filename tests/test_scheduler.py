"""
Tests for scheduler.py — job registration, lifecycle, and LLM validation.
DB uses temp file; HTTP/LLM calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
async def scheduler_test_state(fresh_db):
    import aiwatcher_mcp.scheduler as sched_mod

    sched_mod._scheduler = None


# ── get_scheduler / singleton ─────────────────────────────────────────────


def test_get_scheduler_creates_singleton():
    from aiwatcher_mcp.scheduler import get_scheduler

    s1 = get_scheduler()
    s2 = get_scheduler()

    assert s1 is s2
    assert not s1.running


# ── start_scheduler ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_scheduler_registers_five_jobs():
    from aiwatcher_mcp.scheduler import start_scheduler

    start_scheduler()

    from aiwatcher_mcp.scheduler import get_scheduler
    sched = get_scheduler()
    jobs = sched.get_jobs()
    job_ids = {j.id for j in jobs}

    assert sched.running
    assert len(jobs) == 5
    assert job_ids == {"poll_feeds", "distill", "alerts", "daily_digest", "retention"}


@pytest.mark.asyncio
async def test_start_scheduler_idempotent():
    """
    Calling start_scheduler() after stop_scheduler() should re-register all jobs.
    (Starting twice without stopping is not supported by APScheduler.)
    """
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    stop_scheduler()

    import aiwatcher_mcp.scheduler as sched_mod
    sched_mod._scheduler = None

    start_scheduler()

    from aiwatcher_mcp.scheduler import get_scheduler
    jobs = get_scheduler().get_jobs()
    assert len(jobs) == 5


# ── stop_scheduler ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_scheduler_shuts_down():
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    stop_scheduler()

    from aiwatcher_mcp.scheduler import get_scheduler
    assert not get_scheduler().running


@pytest.mark.asyncio
async def test_stop_scheduler_when_not_started():
    from aiwatcher_mcp.scheduler import stop_scheduler

    stop_scheduler()  # should not crash


@pytest.mark.asyncio
async def test_stop_scheduler_then_restart():
    """Stopping and restarting should create fresh jobs."""
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    stop_scheduler()

    # Re-init singleton (simulates fresh start)
    import aiwatcher_mcp.scheduler as sched_mod
    sched_mod._scheduler = None

    start_scheduler()

    from aiwatcher_mcp.scheduler import get_scheduler
    jobs = get_scheduler().get_jobs()
    assert len(jobs) == 5


# ── validate_distillation_model ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_anthropic_ok():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="ping")]
    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        from aiwatcher_mcp.scheduler import validate_distillation_model
        await validate_distillation_model()  # should not raise


@pytest.mark.asyncio
async def test_validate_anthropic_missing_key():
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    from aiwatcher_mcp.config import get_settings
    cfg = get_settings()
    cfg.anthropic_api_key = ""

    from aiwatcher_mcp.scheduler import validate_distillation_model
    await validate_distillation_model()  # should log warning, not raise


@pytest.mark.asyncio
async def test_validate_anthropic_api_error():
    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        from aiwatcher_mcp.scheduler import validate_distillation_model
        await validate_distillation_model()  # should log warning, not raise


@pytest.mark.asyncio
async def test_validate_ollama_ok():
    import os
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"

    from aiwatcher_mcp.config import get_settings
    cfg = get_settings()
    cfg.llm_provider = "ollama"
    cfg.llm_base_url = "http://localhost:11434/v1"

    mock_completion = MagicMock()
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        from aiwatcher_mcp.scheduler import validate_distillation_model
        await validate_distillation_model()


@pytest.mark.asyncio
async def test_validate_lmstudio_ok():
    import os
    os.environ["LLM_PROVIDER"] = "lmstudio"
    os.environ["LLM_BASE_URL"] = ""

    from aiwatcher_mcp.config import get_settings
    cfg = get_settings()
    cfg.llm_provider = "lmstudio"
    cfg.llm_base_url = ""

    mock_completion = MagicMock()
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        from aiwatcher_mcp.scheduler import validate_distillation_model
        await validate_distillation_model()


# ── Job functions (integration smoke tests) ──────────────────────────────


@pytest.mark.asyncio
async def test_job_poll_feeds_runs():
    from aiwatcher_mcp.scheduler import _job_poll_feeds

    with patch("aiwatcher_mcp.ingestion.poll_all_feeds", new=AsyncMock(return_value={})):
        await _job_poll_feeds()  # should not raise


@pytest.mark.asyncio
async def test_job_distill_runs():
    from aiwatcher_mcp.scheduler import _job_distill

    with patch("aiwatcher_mcp.distillation.distill_items", new=AsyncMock(return_value=0)):
        await _job_distill()


@pytest.mark.asyncio
async def test_job_alerts_runs():
    from aiwatcher_mcp.scheduler import _job_alerts

    with patch("aiwatcher_mcp.alerting.process_alerts", new=AsyncMock(return_value=[])):
        await _job_alerts()


@pytest.mark.asyncio
async def test_job_retention_runs():
    from aiwatcher_mcp.scheduler import _job_retention

    with patch("aiwatcher_mcp.database.expire_old_items", new=AsyncMock(return_value=0)):
        await _job_retention()
