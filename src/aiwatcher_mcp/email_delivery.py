"""
Email delivery — HTML digest to Sandra + Steve.
Tries email-mcp HTTP first, falls back to SMTP.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db

log = logging.getLogger(__name__)


async def send_digest(digest: dict[str, Any]) -> bool:
    cfg = get_settings()
    if not cfg.email_enabled:
        log.info("Email delivery disabled — skipping digest send")
        return False

    recipients = [r.strip() for r in cfg.email_recipients.split(",") if r.strip()]
    subject = f"{cfg.email_subject_prefix} {digest.get('subject', 'Daily Digest')}"

    success = False

    # Try email-mcp first if configured
    if cfg.email_mcp_url:
        success = await _send_via_email_mcp(
            cfg.email_mcp_url, subject, digest["html_body"], digest["text_body"], recipients
        )

    # Fallback to direct SMTP
    if not success and cfg.smtp_host:
        success = await _send_via_smtp(
            subject, digest["html_body"], digest["text_body"], recipients
        )

    if success:
        # Record in digests table
        async with get_db() as db:
            await db.execute(
                """INSERT INTO digests (period_from, period_to, html_body, text_body,
                   item_count, sent_at, recipients)
                   VALUES (datetime('now', '-24 hours'), datetime('now'),
                   ?, ?, ?, ?, ?)""",
                (
                    digest["html_body"],
                    digest["text_body"],
                    digest.get("item_count", 0),
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(recipients),
                ),
            )
            await db.commit()

    return success


async def _send_via_email_mcp(
    url: str, subject: str, html: str, text: str, recipients: list[str]
) -> bool:
    """Call email-mcp REST endpoint."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{url}/api/v1/send",
                json={
                    "to": recipients,
                    "subject": subject,
                    "html_body": html,
                    "text_body": text,
                },
            )
            resp.raise_for_status()
            log.info("Digest sent via email-mcp to %s", recipients)
            return True
    except Exception as exc:
        log.warning("email-mcp delivery failed: %s", exc)
        return False


async def _send_via_smtp(
    subject: str, html: str, text: str, recipients: list[str]
) -> bool:
    """Direct SMTP delivery using aiosmtplib."""
    cfg = get_settings()
    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.smtp_from
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=cfg.smtp_host,
            port=cfg.smtp_port,
            username=cfg.smtp_user,
            password=cfg.smtp_password,
            start_tls=True,
        )
        log.info("Digest sent via SMTP to %s", recipients)
        return True
    except Exception as exc:
        log.error("SMTP delivery failed: %s", exc)
        return False
