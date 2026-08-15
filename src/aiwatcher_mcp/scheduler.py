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
    cfg = get_settings()
    from aiwatcher_mcp.distillation import distill_items
    from aiwatcher_mcp.llm_watchdog import resolve_llm_chain

    if cfg.llm_watchdog_enabled:
        resolved = await resolve_llm_chain()
        if resolved is None:
            log.error("Distillation SKIPPED — no LLM provider available")
            return

    count = await distill_items(batch_size=50)
    if count == 0:
        log.warning(
            "Distillation completed: 0 items processed (no undistilled items or all failed)"
        )
    else:
        log.info("Distillation completed: %d items processed", count)


async def _job_alerts() -> None:
    from aiwatcher_mcp.alerting import process_alerts

    alerted = await process_alerts()
    if alerted:
        log.warning("Alert job fired for %d items: %s", len(alerted), alerted[:3])


async def _job_currentai_sovereignty() -> None:
    """Refresh Current AI stack map and append sovereignty section to digest."""
    from aiwatcher_mcp.currentai.briefing import (
        generate_sovereignty_section,
        push_to_memops,
        refresh_and_check,
    )

    try:
        result = await refresh_and_check()
        if not result.get("new_snapshot"):
            log.info("Current AI: no new snapshot — skipping sovereignty check")
            return

        section = await generate_sovereignty_section()
        if section:
            await push_to_memops(section)
            log.info(
                "Current AI: sovereignty section pushed to memops (%d flags)",
                len(result.get("flags", [])),
            )
        else:
            log.info("Current AI: no diff — sovereignty section skipped")
    except Exception as exc:
        log.warning("Current AI sovereignty check failed: %s", exc)


async def _job_daily_digest() -> None:
    cfg = get_settings()
    from aiwatcher_mcp.calibre_integration import ingest_digest_to_calibre
    from aiwatcher_mcp.distillation import generate_digest
    from aiwatcher_mcp.email_delivery import send_digest
    from aiwatcher_mcp.intel_hub_client import publish_digest_to_hub
    from aiwatcher_mcp.llm_watchdog import resolve_llm_chain

    if cfg.llm_watchdog_enabled:
        resolved = await resolve_llm_chain()
        if resolved is None:
            log.error("Daily digest SKIPPED — no LLM provider available")
            return

    digest = await generate_digest(hours=24)
    await send_digest(digest)
    await ingest_digest_to_calibre(digest)
    hub = await publish_digest_to_hub(digest, hours=24)
    if hub.get("success"):
        log.info("Digest published to Intel Hub: %s", hub.get("url_path", "/"))
    else:
        log.warning("Intel Hub publish skipped: %s", hub.get("message", "?"))


async def _job_morning_news() -> None:
    from aiwatcher_mcp.inbox import publish_morning_news

    result = await publish_morning_news(hours=24, limit=20)
    if result.get("success"):
        log.info("Morning news published: %s", result.get("stable_url", "?"))
    else:
        log.warning("Morning news publish failed: %s", result.get("error", "?"))


async def _job_sync_interests() -> None:
    from aiwatcher_mcp.update_interests import sync_interests_from_config

    await sync_interests_from_config()


async def _job_poll_huggingface() -> None:
    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface

    results = await poll_huggingface()
    total = sum(results.values())
    if total:
        log.info(
            "HuggingFace poll complete: %d new items across %d categories", total, len(results)
        )


async def _job_poll_wikipedia() -> None:
    from aiwatcher_mcp.wikipedia_ingestion import poll_wikipedia

    results = await poll_wikipedia()
    total = sum(results.values())
    if total:
        log.info("Wikipedia poll complete: %d new items across %d categories", total, len(results))


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
        log.info(
            "Retention job: deleted %d items older than %d days", deleted, cfg.item_retention_days
        )


async def validate_distillation_model() -> None:
    """
    Probe the configured LLM provider on startup.
    Uses the watchdog for auto-recovery and fallback.
    Logs clearly if unreachable — does not block startup.
    """
    cfg = get_settings()
    from aiwatcher_mcp.llm_watchdog import ensure_llm_available, resolve_llm_chain

    provider = cfg.llm_provider.lower()
    log.info("Validating LLM provider '%s' / model '%s'...", provider, cfg.distillation_model)

    ok = await ensure_llm_available(provider, cfg.distillation_model, cfg.llm_base_url or None)
    if ok:
        log.info("LLM provider '%s' OK (model: %s)", provider, cfg.distillation_model)
        return

    # Try fallback
    log.warning(
        "Primary LLM '%s/%s' unreachable on startup — trying fallback '%s/%s'",
        provider,
        cfg.distillation_model,
        cfg.llm_fallback_provider,
        cfg.llm_fallback_model,
    )
    resolved = await resolve_llm_chain()
    if resolved:
        log.info(
            "Startup LLM resolved via fallback: %s / %s",
            resolved.get("provider"),
            resolved.get("model"),
        )
    else:
        log.error(
            "ALL LLM providers unreachable at startup — distillation and morning news "
            "will be disabled until recovery. Primary: %s/%s, Fallback: %s/%s",
            provider,
            cfg.distillation_model,
            cfg.llm_fallback_provider,
            cfg.llm_fallback_model,
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

    # Daily digest email: 04:30 UTC = 6:30am Vienna. Off-peak (peak = 01-04, 06-10 UTC) —
    # DeepSeek fallback rung of the LLM chain costs 2.4-4.7x during peak.
    sched.add_job(
        _job_daily_digest,
        trigger=CronTrigger(hour=4, minute=30, timezone="UTC"),
        id="daily_digest",
        replace_existing=True,
    )

    # Morning news page: 05:00 UTC (after digest, stable URL overwrite)
    sched.add_job(
        _job_morning_news,
        trigger=CronTrigger(hour=5, minute=0, timezone="UTC"),
        id="morning_news",
        replace_existing=True,
    )

    # Retention: daily at 10:15 UTC (off-peak, after the morning jobs)
    sched.add_job(
        _job_retention,
        trigger=CronTrigger(hour=10, minute=15, timezone="UTC"),
        id="retention",
        replace_existing=True,
    )

    # Interest bundles: daily 10:30 UTC (before retention)
    sched.add_job(
        _job_sync_interests,
        trigger=CronTrigger(hour=10, minute=30, timezone="UTC"),
        id="sync_interests",
        replace_existing=True,
    )

    # Current AI stack map sovereignty check: daily 10:45 UTC
    sched.add_job(
        _job_currentai_sovereignty,
        trigger=CronTrigger(hour=10, minute=45, timezone="UTC"),
        id="currentai_sovereignty",
        replace_existing=True,
    )

    # Wikipedia poll: every N minutes
    if cfg.wikipedia_enabled:
        sched.add_job(
            _job_poll_wikipedia,
            trigger=IntervalTrigger(minutes=cfg.wikipedia_poll_interval_minutes),
            id="wikipedia_poll",
            replace_existing=True,
            misfire_grace_time=120,
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
        "retention + sync_interests + currentai daily, "
        "digest at 04:30Z, morning news at 05:00Z, "
        "readly every %dh (if watchlist), digest cache TTL %dm",
        cfg.feed_poll_interval_minutes,
        cfg.distillation_interval_hours,
        cfg.alert_hour_utc,
        cfg.alert_minute_utc,
        cfg.readly_poll_interval_hours
        if cfg.readly_enabled and cfg.parsed_readly_watchlist()
        else 0,
        cfg.digest_cache_ttl_minutes,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """JSON-safe scheduler snapshot for /api/scheduler and webapp Runs panel."""
    cfg = get_settings()
    sched = get_scheduler()
    jobs: list[dict] = []
    if sched.running:
        for job in sched.get_jobs():
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            jobs.append(
                {
                    "id": job.id,
                    "next_run": next_run,
                    "trigger": str(job.trigger),
                }
            )
        jobs.sort(key=lambda j: j["id"])
    return {
        "running": sched.running,
        "feed_poll_interval_minutes": cfg.feed_poll_interval_minutes,
        "distillation_interval_hours": cfg.distillation_interval_hours,
        "alert_hour_utc": cfg.alert_hour_utc,
        "alert_minute_utc": cfg.alert_minute_utc,
        "jobs": jobs,
    }
