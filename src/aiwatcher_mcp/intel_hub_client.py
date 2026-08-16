"""Publish AIWatcher digests/reports to the Fleet Intel Reports Hub."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_HUB_PORT = 11027


def _ascii_normalize(text: str) -> str:
    """Replace em/en dashes and smart quotes with ASCII (LLM output hygiene)."""
    return (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _vienna_today() -> str:
    """Today's date in Europe/Vienna as YYYY-MM-DD (digest audience timezone)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Vienna")).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def hub_base_url() -> str:
    cfg = get_settings()
    return (cfg.intel_hub_url or f"http://127.0.0.1:{DEFAULT_HUB_PORT}").rstrip("/")


async def publish_to_intel_hub(
    *,
    title: str,
    html: str = "",
    markdown: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    report_id: str | None = None,
) -> dict[str, Any]:
    """POST digest/report HTML to Fritz Intel Hub."""
    if not title.strip():
        return {"success": False, "message": "title required"}
    if not html and not markdown:
        return {"success": False, "message": "html or markdown required"}

    payload: dict[str, Any] = {
        "title": title,
        "source": "aiwatcher",
        "html": html,
        "markdown": markdown,
        "summary": summary[:500],
        "tags": tags or ["aiwatcher", "digest"],
    }
    if report_id:
        payload["report_id"] = report_id

    url = f"{hub_base_url()}/api/reports/publish"
    cfg = get_settings()
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                url,
                json=payload,
                auth=(cfg.intel_hub_user, cfg.intel_hub_pass),
            )
            if resp.status_code == 200:
                data = resp.json()
                data["via"] = "http"
                return data
            return {
                "success": False,
                "via": "http",
                "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except httpx.HTTPError as exc:
        logger.warning("Intel hub publish failed: %s", exc)
        return {"success": False, "via": "http", "message": str(exc)}


async def publish_digest_to_hub(digest: dict[str, Any], *, hours: int = 24) -> dict[str, Any]:
    """Publish generate_digest() output to the hub."""
    # The LLM-generated subject can carry a hallucinated/stale date (it has no
    # clock). Pin the title server-side: if today's date is not in the subject,
    # use a deterministic one - the hub must never show a wrong date.
    today = _vienna_today()
    subject = _ascii_normalize(digest.get("subject") or f"AIWatcher Daily Digest - {today}")
    if today not in subject:
        subject = f"AIWatcher Daily Digest - {today}"
    html_body = digest.get("html_body") or ""
    text_body = _ascii_normalize((digest.get("text_body") or "")[:400])
    item_count = digest.get("item_count") or digest.get("count") or 0

    if not html_body:
        return {"success": False, "message": "digest has no html_body"}

    return await publish_to_intel_hub(
        title=subject,
        html=html_body,
        summary=f"{item_count} items \u00b7 {hours}h window - {text_body[:180]}",
        tags=["aiwatcher", "digest", f"{hours}h"],
        report_id="daily-digest",
    )
