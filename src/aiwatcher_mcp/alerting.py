"""
Alerting — robofang integration, speechops TTS wake-up, Windows toast.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_alert_candidates, mark_sent_robofang

log = logging.getLogger(__name__)

# Per-process alert routing counters (since daemon start). Serves BUG-024 hardening:
# "alerts fired" must be distinguishable from "alerts routed" - a rising *_fail or
# *_fallback while *_ok stays flat means the fleet channel is dead again.
_channel_stats: dict[str, int] = {
    "robofang_ok": 0,
    "robofang_fail": 0,
    "tts_ok": 0,
    "tts_fallback": 0,
    "tts_fail": 0,
}


def get_alert_channel_stats() -> dict[str, int]:
    """Return a copy of the per-process alert routing counters."""
    return dict(_channel_stats)


async def fire_robofang_alert(item: dict) -> bool:
    """POST a BREAKING item to robofang Council bridge."""
    cfg = get_settings()
    if not cfg.robofang_enabled:
        return False
    payload = {
        "source": "aiwatcher-mcp",
        "event": "BREAKING_AI_NEWS",
        "urgency": item.get("urgency_score", 0),
        "title": item["title"],
        "url": item.get("url", ""),
        "summary": item.get("distilled_summary") or item.get("summary", ""),
        "tags": json.loads(item.get("tags") or "[]"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{cfg.robofang_backend_url}/api/v1/events",
                json=payload,
            )
            resp.raise_for_status()
            log.info("Robofang alerted: '%s'", item["title"][:60])
            _channel_stats["robofang_ok"] += 1
            return True
    except Exception as exc:
        log.warning("Robofang alert failed: %s", exc)
        _channel_stats["robofang_fail"] += 1
        return False


async def fire_speechops_tts(text: str) -> bool:
    """Call speechops HTTP backend to synthesize & play TTS."""
    cfg = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # speechops exposes a REST endpoint for TTS
            resp = await client.post(
                f"{cfg.speechops_http_url}/api/v1/tts",
                # provider "windows" = speech-mcp SAPI5; "elevenlabs" needs a key and
                # silently fails -> fallback. The wake-up text is short; SAPI is fine.
                json={"text": text, "provider": "windows"},
            )
            resp.raise_for_status()
            log.info("TTS fired via speechops")
            _channel_stats["tts_ok"] += 1
            return True
    except Exception as exc:
        log.warning("speechops TTS failed (%s), falling back to Windows SAPI", exc)
        ok = await _windows_tts_fallback(text)
        if ok:
            _channel_stats["tts_fallback"] += 1
        else:
            _channel_stats["tts_fail"] += 1
        return ok


async def _windows_tts_fallback(text: str) -> bool:
    """PowerShell SAPI5 as last-resort wake-up."""
    import asyncio

    safe = text.replace('"', "'").replace("`", "'")
    cmd = f'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak("{safe}")'
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-Command",
            cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=30)
        return True
    except Exception as exc:
        log.error("Windows SAPI fallback failed: %s", exc)
        return False


async def process_alerts() -> list[str]:
    """
    Find unalerted critical items, fire robofang + TTS if warranted.
    Called by the 04:55 UTC scheduled job.
    Returns list of alerted item titles.
    """
    cfg = get_settings()
    candidates = await get_alert_candidates(cfg.alert_threshold)
    if not candidates:
        log.info("No alert candidates above threshold %.1f", cfg.alert_threshold)
        return []

    alerted: list[str] = []
    for item in candidates:
        fired = await fire_robofang_alert(item)
        if fired:
            await mark_sent_robofang(item["id"])
            alerted.append(item["title"])

    if alerted:
        count = len(alerted)
        wake_text = (
            f"Sandra. AIWatcher has {count} critical AI news alert{'s' if count > 1 else ''}. "
            f"First item: {alerted[0][:120]}. Check your dashboard immediately."
        )
        await fire_speechops_tts(wake_text)

    return alerted
