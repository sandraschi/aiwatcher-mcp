"""CurrentAI sovereignty briefing — used by the daily digest scheduler job.

Thin wrapper over the currentai fetcher/store/differ: refresh the stack map,
flag concentration risk, and produce a markdown section for the digest.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def refresh_and_check() -> dict[str, Any]:
    """Fetch the latest CurrentAI stack map and store a new snapshot if changed.

    Returns {"new_snapshot": bool, "flags": [...], "commit": str|None}.
    """
    from .differ import diff_snapshots
    from .fetcher import fetch_normalized_products
    from .store import get_latest, load_snapshot, save_snapshot

    records, commit_sha = await fetch_normalized_products()
    if not records:
        return {"new_snapshot": False, "flags": [], "commit": None}

    short = commit_sha[:8]
    latest = get_latest()
    if latest and (latest.get("commit") or "").startswith(short):
        return {"new_snapshot": False, "flags": [], "commit": short}

    flags: list[str] = []
    if latest:
        prev = load_snapshot()
        if prev:
            prev_data, _ = prev
            diff = diff_snapshots(prev_data, {"commit": commit_sha, "products": records})
            if not diff.get("is_empty", True):
                flags = diff.get("changes", []) or []
                logger.info("CurrentAI diff: %d change flags", len(flags))

    save_snapshot(records, commit_sha)
    return {"new_snapshot": True, "flags": flags, "commit": short}


async def generate_sovereignty_section() -> str:
    """Markdown sovereignty section from the latest snapshot's gap report."""
    from .differ import gap_report
    from .store import get_latest, load_snapshot

    latest = get_latest()
    if not latest:
        return ""
    snap = load_snapshot()
    if not snap:
        return ""
    data, _ = snap

    report = gap_report(data.get("products", []))
    layers = report.get("layers", {}) if isinstance(report, dict) else {}
    if not layers:
        return ""

    lines = [
        "## AI Stack Sovereignty (CurrentAI map)",
        "",
        "Open-weight coverage per stack layer:",
        "",
    ]
    for layer, info in sorted(layers.items()):
        lines.append(
            f"- **{layer}**: {info.get('open', 0)} open / "
            f"{info.get('openish', 0)} open-ish / {info.get('closed', 0)} closed"
        )
    if report.get("concentration_risk"):
        lines.append("")
        lines.append("⚠️ Concentration risk: fewer than 3 fully-open products in a layer.")
    return "\n".join(lines)


async def push_to_memops(section: str) -> bool:
    """Append the sovereignty section to the memops daily note (best-effort)."""
    import httpx

    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()
    if not cfg.memops_url:
        logger.info("memops_url not configured — sovereignty section not pushed")
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{cfg.memops_url.rstrip('/')}/api/v1/notes",
                json={"title": "CurrentAI Sovereignty", "content": section},
            )
            return resp.status_code in (200, 201)
    except httpx.HTTPError as exc:
        logger.warning("Failed to push sovereignty section to memops: %s", exc)
        return False
