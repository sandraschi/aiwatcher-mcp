"""
Scheduler — APScheduler jobs for feed polling, distillation, digest, alerts.
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


async def _job_gmail() -> None:
    from aiwatcher_mcp.gmail_ingestion import poll_gmail_alphasignal
    count = await poll_gmail_alphasignal()
    if count:
        log.info("Gmail job: %d new items from Alpha Signal", count)


async def _job_daily_digest() -> None:
    from aiwatcher_mcp.distillation import generate_digest
    from aiwatcher_mcp.email_delivery import send_digest
    from aiwatcher_mcp.calibre_integration import ingest_digest_to_calibre
    digest = await generate_digest(hours=24)
    await send_digest(digest)
    await ingest_digest_to_calibre(digest)


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

    # Gmail Alpha Signal: every hour if enabled
    sched.add_job(
        _job_gmail,
        trigger=IntervalTrigger(hours=1),
        id="gmail_alphasignal",
        replace_existing=True,
        misfire_grace_time=300,
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

    sched.start()
    log.info(
        "Scheduler started — poll every %dm, distill every %dh, alerts at %02d:%02dZ",
        cfg.feed_poll_interval_minutes,
        cfg.distillation_interval_hours,
        cfg.alert_hour_utc,
        cfg.alert_minute_utc,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("Scheduler stopped")
