"""
Email delivery - HTML digest to Sandra + Steve.
Tries email-mcp HTTP first, falls back to SMTP.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db

log = logging.getLogger(__name__)


async def send_digest(digest: dict[str, Any]) -> bool:
    cfg = get_settings()
    if not cfg.email_enabled:
        log.info("Email delivery disabled - skipping digest send")
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

    # Discord digest post (independent of email outcome)
    discord_ok = await post_digest_to_discord(digest)

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
                    datetime.now(UTC).isoformat(),
                    json.dumps(recipients),
                ),
            )
            await db.commit()

    if success and discord_ok:
        log.info("Digest delivered: email to %s + Discord post", recipients)
    return success


async def post_digest_to_discord(digest: dict[str, Any]) -> bool:
    """Post a compact digest summary to the configured Discord channel via discord-mcp REST.

    Opt-in: requires DISCORD_MCP_URL and DISCORD_DIGEST_CHANNEL_ID. Discord caps
    messages at 2000 chars - the summary is truncated to fit.
    """
    cfg = get_settings()
    if not (cfg.discord_mcp_url and cfg.discord_digest_channel_id):
        return False

    text = (digest.get("text_body") or "").strip()
    if not text:
        log.info("Discord post skipped: digest has no text body")
        return False

    subject = digest.get("subject", "Daily Digest")
    content = f"**Daily AIWatcher Digest** - {subject}\n\n{text[:1900]}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{cfg.discord_mcp_url.rstrip('/')}/api/v1/channels/{cfg.discord_digest_channel_id}/messages",
                json={"content": content},
            )
            resp.raise_for_status()
            log.info("Digest posted to Discord channel %s", cfg.discord_digest_channel_id)
            return True
    except Exception as exc:
        log.warning("Discord digest post failed: %s", exc)
        return False


async def _send_via_email_mcp(
    url: str, subject: str, html: str, text: str, recipients: list[str]
) -> bool:
    """Call email-mcp REST endpoint."""
    cfg = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{url}/api/send",
                json={
                    "to": recipients,
                    "subject": subject,
                    "body": text,
                    "html": html,
                },
                auth=(cfg.email_mcp_user, cfg.email_mcp_password),
            )
            resp.raise_for_status()
            log.info("Digest sent via email-mcp to %s", recipients)
            return True
    except Exception as exc:
        log.warning("email-mcp delivery failed: %s", exc)
        return False


async def _send_via_smtp(subject: str, html: str, text: str, recipients: list[str]) -> bool:
    """Direct SMTP delivery using aiosmtplib."""
    cfg = get_settings()
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        import aiosmtplib

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
