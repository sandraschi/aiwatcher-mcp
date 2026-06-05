"""Prometheus text exposition for fleet monitoring."""

from __future__ import annotations

from typing import Any


def format_prometheus(stats: dict[str, Any], *, scheduler_running: bool) -> str:
    """Minimal counters/gauges — no external prometheus_client dependency."""
    lines = [
        "# HELP aiwatcher_up Backend process responding.",
        "# TYPE aiwatcher_up gauge",
        "aiwatcher_up 1",
        "# HELP aiwatcher_scheduler_running APScheduler running flag.",
        "# TYPE aiwatcher_scheduler_running gauge",
        f"aiwatcher_scheduler_running {1 if scheduler_running else 0}",
        "# HELP aiwatcher_active_feeds Enabled feeds.",
        "# TYPE aiwatcher_active_feeds gauge",
        f"aiwatcher_active_feeds {stats.get('active_feeds', 0)}",
        "# HELP aiwatcher_items_total All items in DB.",
        "# TYPE aiwatcher_items_total gauge",
        f"aiwatcher_items_total {stats.get('total_items', 0)}",
        "# HELP aiwatcher_items_last_24h Items fetched in last 24h.",
        "# TYPE aiwatcher_items_last_24h gauge",
        f"aiwatcher_items_last_24h {stats.get('items_last_24h', 0)}",
        "# HELP aiwatcher_unread_items Unread items.",
        "# TYPE aiwatcher_unread_items gauge",
        f"aiwatcher_unread_items {stats.get('unread_items', 0)}",
        "# HELP aiwatcher_critical_items Items with urgency >= 8.5.",
        "# TYPE aiwatcher_critical_items gauge",
        f"aiwatcher_critical_items {stats.get('critical_items', 0)}",
        "# HELP aiwatcher_degraded_feeds Feeds with consecutive failures.",
        "# TYPE aiwatcher_degraded_feeds gauge",
        f"aiwatcher_degraded_feeds {stats.get('degraded_feeds', 0)}",
    ]
    return "\n".join(lines) + "\n"
