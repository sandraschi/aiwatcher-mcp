"""
Scheduler — APScheduler jobs for feed polling, distillation, digest, alerts, retention.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from aiwatcher_mcp.config import get_settings

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _job_poll_feeds() -> None:
    from aiwatcher_mcp.ingestion import poll_all_feeds
    results = await poll_all_feeds()
    total = sum(results.values())
    log.info("Scheduled poll complete: %d new items across %d feeds", total, len(results))


async def _job_distill() -> None:
    from aiwatcher_mcp.distillation import distill_items
    count = await distill_items(batch_size=50)
    log.info("Scheduled distillation: %d items processed", count)


async def _job_alerts() -> None:
    from aiwatcher_mcp.alerting import process_alerts
    alerted = await process_alerts()
    if alerted:
        log.warning("Alert job fired for %d items: %s", len(alerted), alerted[:3])


async def _job_daily_digest() -> None:
    from aiwatcher_mcp.calibre_integration import ingest_digest_to_calibre
    from aiwatcher_mcp.distillation import generate_digest
    from aiwatcher_mcp.email_delivery import send_digest
    from aiwatcher_mcp.intel_hub_client import publish_digest_to_hub
    digest = await generate_digest(hours=24)
    await send_digest(digest)
    await ingest_digest_to_calibre(digest)
    hub = await publish_digest_to_hub(digest, hours=24)
    if hub.get("success"):
        log.info("Digest published to Intel Hub: %s", hub.get("url_path", "/"))
    else:
        log.warning("Intel Hub publish skipped: %s", hub.get("message", "?"))


async def _job_sync_interests() -> None:
    from aiwatcher_mcp.update_interests import sync_interests_from_config

    await sync_interests_from_config()


async def _job_poll_huggingface() -> None:
    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface
    results = await poll_huggingface()
    total = sum(results.values())
    if total:
        log.info("HuggingFace poll complete: %d new items across %d categories", total, len(results))


async def _job_poll_readly() -> None:
    from aiwatcher_mcp.readly_ingestion import get_effective_readly_watchlist, poll_readly_articles

    cfg = get_settings()
    if not cfg.readly_enabled or not get_effective_readly_watchlist():
        return
    count = await poll_readly_articles()
    log.info("Scheduled readly poll: %d new articles", count)


async def _job_retention() -> None:
    """Delete old low-urgency items to keep the DB from growing unbounded."""
    cfg = get_settings()
    from aiwatcher_mcp.database import expire_old_items
    deleted = await expire_old_items(retention_days=cfg.item_retention_days)
    if deleted:
        log.info("Retention job: deleted %d items older than %d days", deleted, cfg.item_retention_days)


async def validate_distillation_model() -> None:
    """
    Probe the configured LLM provider on startup with a minimal request.
    Logs a clear warning if unreachable — does not block startup.
    """
    cfg = get_settings()
    provider = cfg.llm_provider.lower()
    log.info("Validating LLM provider '%s' / model '%s'...", provider, cfg.distillation_model)
    try:
        if provider == "anthropic":
            if not cfg.anthropic_api_key:
                log.warning(
                    "ANTHROPIC_API_KEY is not set — distillation will fail at runtime."
                )
                return
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
            await client.messages.create(
                model=cfg.distillation_model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            import openai
            base_url = cfg.llm_base_url
            if not base_url:
                base_url = (
                    "http://localhost:11434/v1" if provider == "ollama"
                    else "http://localhost:1234/v1"
                )
            client = openai.AsyncOpenAI(api_key="not-needed", base_url=base_url)
            await client.chat.completions.create(
                model=cfg.distillation_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        log.info("LLM provider '%s' OK (model: %s)", provider, cfg.distillation_model)
    except Exception as exc:
        log.warning(
            "LLM provider '%s' validation failed: %s — "
            "distillation will not work until this is resolved.",
            provider, exc,
        )


def start_scheduler() -> None:
    cfg = get_settings()
    sched = get_scheduler()

    # Feed poll: every N minutes
    sched.add_job(
        _job_poll_feeds,
        trigger=IntervalTrigger(minutes=cfg.feed_poll_interval_minutes),
        id="poll_feeds",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Distillation: every N hours
    sched.add_job(
        _job_distill,
        trigger=IntervalTrigger(hours=cfg.distillation_interval_hours),
        id="distill",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # Alert check: daily at configured UTC time (default 04:55 = 5am Vienna)
    sched.add_job(
        _job_alerts,
        trigger=CronTrigger(
            hour=cfg.alert_hour_utc,
            minute=cfg.alert_minute_utc,
            timezone="UTC",
        ),
        id="alerts",
        replace_existing=True,
    )

    # Daily digest email: 06:00 UTC = 7am Vienna
    sched.add_job(
        _job_daily_digest,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="daily_digest",
        replace_existing=True,
    )

    # Retention: daily at 03:00 UTC (off-peak, before alert job)
    sched.add_job(
        _job_retention,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="retention",
        replace_existing=True,
    )

    # Interest bundles: daily 02:00 UTC (before retention)
    sched.add_job(
        _job_sync_interests,
        trigger=CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="sync_interests",
        replace_existing=True,
    )

    # HuggingFace poll: every N minutes
    if cfg.huggingface_enabled:
        sched.add_job(
            _job_poll_huggingface,
            trigger=IntervalTrigger(minutes=cfg.hf_poll_interval_minutes),
            id="huggingface_poll",
            replace_existing=True,
            misfire_grace_time=120,
        )

    if cfg.readly_enabled and cfg.parsed_readly_watchlist():
        sched.add_job(
            _job_poll_readly,
            trigger=IntervalTrigger(hours=cfg.readly_poll_interval_hours),
            id="readly_poll",
            replace_existing=True,
            misfire_grace_time=600,
        )

    sched.start()
    log.info(
        "Scheduler started — poll every %dm, distill every %dh, alerts at %02d:%02dZ, "
        "retention + sync_interests daily, readly every %dh (if watchlist), digest cache TTL %dm",
        cfg.feed_poll_interval_minutes,
        cfg.distillation_interval_hours,
        cfg.alert_hour_utc,
        cfg.alert_minute_utc,
        cfg.readly_poll_interval_hours if cfg.readly_enabled and cfg.parsed_readly_watchlist() else 0,
        cfg.digest_cache_ttl_minutes,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("Scheduler stopped")
