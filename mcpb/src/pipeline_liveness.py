"""Pipeline liveness: detect stale China open-weight / arXiv ingestion loops."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db

log = logging.getLogger(__name__)

_EXPECTED_ARXIV_PORT = "10770"
_WRONG_ARXIV_PORT = "10719"


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


async def check_pipeline_liveness(*, stale_hours: int = 48) -> dict[str, Any]:
    """Return health + alerts when arXiv pull or upstream arxiv-mcp is broken/stale."""
    cfg = get_settings()
    stale_hours = max(1, int(stale_hours))
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)
    alerts: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    if cfg.arxiv_enabled:
        url = (cfg.arxiv_mcp_url or "").strip()
        if _WRONG_ARXIV_PORT in url:
            alerts.append(
                {
                    "severity": "critical",
                    "code": "ARXIV_MCP_WRONG_PORT",
                    "message": (
                        f"ARXIV_MCP_URL uses port {_WRONG_ARXIV_PORT}; "
                        f"arxiv-mcp serves on {_EXPECTED_ARXIV_PORT}"
                    ),
                    "detail": {"configured_url": url, "expected_port": _EXPECTED_ARXIV_PORT},
                }
            )
        if url:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.get(f"{url.rstrip('/')}/api/health")
                ok = resp.status_code == 200
                checks.append(
                    {
                        "name": "arxiv_mcp_health",
                        "ok": ok,
                        "url": url,
                        "status_code": resp.status_code,
                    }
                )
                if not ok:
                    alerts.append(
                        {
                            "severity": "critical",
                            "code": "ARXIV_MCP_UNHEALTHY",
                            "message": f"arxiv-mcp health check failed ({resp.status_code})",
                            "detail": {"url": url},
                        }
                    )
            except httpx.HTTPError as exc:
                checks.append({"name": "arxiv_mcp_health", "ok": False, "url": url})
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "ARXIV_MCP_UNREACHABLE",
                        "message": f"Cannot reach arxiv-mcp at {url}: {exc}",
                        "detail": {"url": url},
                    }
                )

        async with (
            get_db() as db,
            db.execute(
                """SELECT id, name, last_fetched, consecutive_failures, last_error, enabled
               FROM feeds WHERE feed_type='arxiv'"""
            ) as cur,
        ):
            arxiv_feeds = [dict(r) for r in await cur.fetchall()]

        checks.append({"name": "arxiv_feed_count", "count": len(arxiv_feeds)})

        for feed in arxiv_feeds:
            if not feed.get("enabled"):
                continue
            name = feed["name"]
            lf = _parse_ts(feed.get("last_fetched"))
            if lf is None:
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "ARXIV_FEED_NEVER_FETCHED",
                        "message": f"{name} has never recorded a successful poll",
                        "detail": {
                            "feed_id": feed["id"],
                            "last_error": feed.get("last_error"),
                            "failures": feed.get("consecutive_failures"),
                        },
                    }
                )
            elif lf < cutoff:
                age_h = round((datetime.now(UTC) - lf).total_seconds() / 3600, 1)
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "ARXIV_FEED_STALE",
                        "message": (
                            f"{name} last fetched {age_h}h ago "
                            f"(threshold {stale_hours}h) — arXiv pull may be dead"
                        ),
                        "detail": {
                            "feed_id": feed["id"],
                            "last_fetched": feed.get("last_fetched"),
                            "age_hours": age_h,
                            "last_error": feed.get("last_error"),
                        },
                    }
                )
            if (feed.get("consecutive_failures") or 0) > 0:
                alerts.append(
                    {
                        "severity": "warning",
                        "code": "ARXIV_FEED_FAILURES",
                        "message": (
                            f"{name} has {feed['consecutive_failures']} consecutive poll failures"
                        ),
                        "detail": {
                            "feed_id": feed["id"],
                            "last_error": feed.get("last_error"),
                        },
                    }
                )

    if cfg.vla_mcp_enabled and (cfg.vla_mcp_url or "").strip():
        vla_base = cfg.vla_mcp_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    f"{vla_base}/api/pipeline/liveness",
                    params={"stale_hours": stale_hours},
                )
            if resp.status_code == 200:
                vla_data = resp.json()
                checks.append({"name": "vla_mcp_pipeline", "ok": vla_data.get("healthy", False)})
                for alert in vla_data.get("alerts") or []:
                    alerts.append({**alert, "source": "vla_mcp"})
                for check in vla_data.get("checks") or []:
                    checks.append({**check, "source": "vla_mcp"})
            else:
                alerts.append(
                    {
                        "severity": "warning",
                        "code": "VLA_PIPELINE_PROBE_FAILED",
                        "source": "vla_mcp",
                        "message": f"vla-mcp pipeline liveness returned HTTP {resp.status_code}",
                        "detail": {"url": f"{vla_base}/api/pipeline/liveness"},
                    }
                )
        except httpx.HTTPError as exc:
            alerts.append(
                {
                    "severity": "warning",
                    "code": "VLA_PIPELINE_PROBE_FAILED",
                    "source": "vla_mcp",
                    "message": f"Cannot probe vla-mcp robotics pipeline: {exc}",
                    "detail": {"url": f"{vla_base}/api/pipeline/liveness"},
                }
            )

    upstream: dict[str, Any] | None = None
    if cfg.arxiv_enabled and (cfg.arxiv_mcp_url or "").strip():
        base = cfg.arxiv_mcp_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    f"{base}/api/pipeline/liveness",
                    params={"stale_hours": stale_hours},
                )
            if resp.status_code == 200:
                upstream = resp.json()
                for alert in upstream.get("alerts") or []:
                    alerts.append({**alert, "source": "arxiv_mcp"})
                for check in upstream.get("checks") or []:
                    checks.append({**check, "source": "arxiv_mcp"})
            else:
                alerts.append(
                    {
                        "severity": "critical",
                        "code": "ARXIV_PIPELINE_PROBE_FAILED",
                        "source": "arxiv_mcp",
                        "message": f"arxiv-mcp pipeline liveness returned HTTP {resp.status_code}",
                        "detail": {"url": f"{base}/api/pipeline/liveness"},
                    }
                )
        except httpx.HTTPError as exc:
            alerts.append(
                {
                    "severity": "critical",
                    "code": "ARXIV_PIPELINE_PROBE_FAILED",
                    "source": "arxiv_mcp",
                    "message": f"Cannot probe arxiv-mcp code-hunt pipeline: {exc}",
                    "detail": {"url": f"{base}/api/pipeline/liveness"},
                }
            )

    for alert in alerts:
        alert.setdefault("source", "aiwatcher_mcp")

    critical = [a for a in alerts if a.get("severity") == "critical"]
    warnings = [a for a in alerts if a.get("severity") == "warning"]
    healthy = len(critical) == 0

    if alerts:
        for a in alerts:
            if a.get("severity") == "critical":
                log.warning("Pipeline liveness [%s]: %s", a.get("code"), a.get("message"))

    return {
        "success": True,
        "healthy": healthy,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "checked_at": datetime.now(UTC).isoformat(),
        "service": "aiwatcher-mcp",
        "stale_hours": stale_hours,
        "arxiv_enabled": cfg.arxiv_enabled,
        "arxiv_mcp_url": cfg.arxiv_mcp_url if cfg.arxiv_enabled else None,
        "checks": checks,
        "alerts": alerts,
        "upstream": upstream,
    }
