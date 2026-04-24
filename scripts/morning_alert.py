"""
Standalone 5am alert script — runs as a Windows Scheduled Task.
Works independently of Claude Desktop / MCP transport.

Usage: uv run python scripts/morning_alert.py

The Windows Scheduled Task (see scripts/install_task.ps1) calls this
directly at 04:55 UTC. It hits the aiwatcher backend REST API if running,
or does a direct DB check + TTS if the backend is offline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Resolve repo root so we can find .env and the src package
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(REPO_ROOT / "data" / "morning_alert.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("morning_alert")


async def _tts(text: str) -> None:
    """Try speechops HTTP, then Windows SAPI5."""
    import httpx
    from aiwatcher_mcp.config import get_settings
    cfg = get_settings()
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.post(
                f"{cfg.speechops_http_url}/api/v1/tts",
                json={"text": text, "provider": "elevenlabs"},
            )
            r.raise_for_status()
            log.info("TTS via speechops OK")
            return
    except Exception as exc:
        log.warning("speechops TTS failed (%s) — falling back to SAPI5", exc)

    # SAPI5 fallback
    safe = text.replace('"', "'").replace("`", "'")
    cmd = (
        f'Add-Type -AssemblyName System.Speech; '
        f'$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        f'$s.Rate=1; $s.Speak("{safe}")'
    )
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-Command", cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.wait_for(proc.wait(), timeout=45)
    log.info("SAPI5 TTS complete")


async def _toast(title: str, message: str) -> None:
    """Windows 10/11 toast notification via PowerShell."""
    script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('{title}')) | Out-Null
$template.GetElementsByTagName('text')[1].AppendChild($template.CreateTextNode('{message[:80]}')) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AIWatcher').Show($toast)
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=10)
    except Exception as exc:
        log.warning("Toast notification failed: %s", exc)


async def _try_backend_alerts() -> list[str]:
    """Hit the running backend REST API to trigger alert pipeline."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("http://localhost:10946/api/alerts/check")
            r.raise_for_status()
            data = r.json()
            return data.get("alerted", [])
    except Exception as exc:
        log.info("Backend not reachable (%s) — going direct", exc)
        return []


async def _direct_db_alerts() -> list[str]:
    """Bypass backend — read DB directly and fire alerts."""
    # Load .env manually since we're running standalone
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    from aiwatcher_mcp.database import init_db, get_alert_candidates, mark_sent_robofang
    from aiwatcher_mcp.alerting import fire_robofang_alert
    from aiwatcher_mcp.config import get_settings

    cfg = get_settings()
    await init_db()
    candidates = await get_alert_candidates(cfg.alert_threshold)
    if not candidates:
        return []

    alerted = []
    for item in candidates:
        ok = await fire_robofang_alert(item)
        if ok:
            await mark_sent_robofang(item["id"])
            alerted.append(item["title"])
    return alerted


async def main() -> None:
    log.info("Morning alert check starting")

    # Try backend first (preferred — keeps everything in one process)
    alerted = await _try_backend_alerts()

    # If backend was down, go direct
    if not alerted:
        alerted = await _direct_db_alerts()

    if not alerted:
        log.info("No critical items — nothing to alert")
        return

    count = len(alerted)
    log.warning("ALERT: %d critical items", count)

    # TTS wake-up
    speech = (
        f"Sandra. AIWatcher alert. {count} critical AI news item{'s' if count > 1 else ''}. "
        f"Top item: {alerted[0][:120]}. Check your dashboard."
    )
    await _tts(speech)

    # Toast notification
    await _toast(
        f"AIWatcher — {count} Critical Alert{'s' if count > 1 else ''}",
        alerted[0][:80],
    )

    log.info("Alert pipeline complete for %d items", count)


if __name__ == "__main__":
    asyncio.run(main())
