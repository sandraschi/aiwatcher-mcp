"""Surge mode (P3) - high-urgency items fan out to the hub inbox immediately.

The daily digest is batch; surge is interrupt: any item scored with urgency
>= surge_threshold (default 8.5, same as the alert threshold) is pushed to the
hub agent inbox (P2 comm bus) the moment it is ingested or scored, instead of
waiting for the 04:30 UTC digest. Destination: SURGE_TO_ENTITY (default
"fritz" - the fleet agent); arxiv codehunt live drops already flow through
ingest_fleet_event, so they inherit the same fan-out.

The fan-out is best-effort: hub unreachable/token wrong must never fail the
ingest or scoring pipeline - failures are logged and swallowed.
"""

from __future__ import annotations

import logging

import httpx

from .config import get_settings

log = logging.getLogger(__name__)


async def surge_fanout(
    *,
    title: str,
    summary: str = "",
    urgency: float = 0.0,
    source: str = "aiwatcher",
    url: str = "",
) -> dict:
    """Push a high-urgency item to the hub inbox immediately.

    No-op unless urgency >= cfg.surge_threshold and cfg.surge_enabled.
    """
    cfg = get_settings()
    if not cfg.surge_enabled:
        return {"success": False, "skipped": "surge disabled"}
    if float(urgency) < float(cfg.surge_threshold):
        return {"success": False, "skipped": "below threshold"}

    body = (summary or title)[:4000]
    if url:
        body = f"{body}\n\n{url}"
    payload = {
        "to_entity": cfg.surge_to_entity,
        "from_entity": "aiwatcher",
        "subject": title[:200],
        "body": body,
    }
    headers = {"Authorization": f"Bearer {cfg.surge_hub_token}"} if cfg.surge_hub_token else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{cfg.surge_hub_url.rstrip('/')}/api/v1/inbox/send",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            mid = (data.get("message") or {}).get("id")
            log.info(
                "SURGE: urgency %.1f '%s' -> hub inbox %s (id %s)",
                urgency,
                title[:60],
                cfg.surge_to_entity,
                mid,
            )
            return {"success": True, "message_id": mid}
    except Exception as exc:
        log.warning("SURGE fan-out failed (%s) - ingest continues", exc)
        return {"success": False, "error": str(exc)}
