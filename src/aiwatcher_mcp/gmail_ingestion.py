"""
Gmail / Alpha Signal email ingestion.
Pulls unread emails from the configured sender via Gmail MCP REST API,
extracts article links, and inserts them as feed items.

This module is called by the scheduler if GMAIL_ENABLED=true.
It is NOT a replacement for RSS — it supplements it with newsletter content
that may not have a public feed (e.g. Alpha Signal, Import AI emails).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, upsert_item

log = logging.getLogger(__name__)

_EMAIL_FEED_ID: int | None = None


async def _get_or_create_email_feed(sender_label: str) -> int:
    """Ensure an 'email' type feed exists for Alpha Signal, return its id."""
    global _EMAIL_FEED_ID
    if _EMAIL_FEED_ID is not None:
        return _EMAIL_FEED_ID

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='email'",
            (f"Email: {sender_label}",),
        ) as cur:
            row = await cur.fetchone()

        if row:
            _EMAIL_FEED_ID = row["id"]
            return _EMAIL_FEED_ID

        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            (f"Email: {sender_label}", sender_label, "email"),
        )
        await db.commit()
        _EMAIL_FEED_ID = cur.lastrowid
        log.info("Created email feed id=%d for %s", _EMAIL_FEED_ID, sender_label)
        return _EMAIL_FEED_ID


def _extract_links_from_html(html: str) -> list[dict[str, str]]:
    """Pull (title, url) pairs from newsletter HTML."""
    soup = BeautifulSoup(html, "lxml")
    links = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        url: str = a["href"]
        if not url.startswith("http"):
            continue
        # Skip unsubscribe/tracking/social junk
        skip_patterns = ["unsubscribe", "click.", "track.", "twitter.com",
                          "linkedin.com", "facebook.com", "mailto:", "utm_"]
        if any(p in url.lower() for p in skip_patterns):
            continue
        title = a.get_text(strip=True) or url[:80]
        if len(title) < 8:  # too short to be a real headline
            continue
        key = url.split("?")[0]  # dedup on base URL
        if key not in seen:
            seen.add(key)
            links.append({"title": title, "url": url})
    return links[:30]  # cap per email


async def poll_gmail_alphasignal() -> int:
    """
    Fetch recent Alpha Signal emails via Gmail MCP REST API and
    insert extracted links as items. Returns new item count.
    """
    cfg = get_settings()
    if not cfg.gmail_enabled or not cfg.gmail_mcp_url:
        return 0

    feed_id = await _get_or_create_email_feed(cfg.alphasignal_sender)
    new_count = 0

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Gmail MCP REST: search unread from Alpha Signal
            resp = await client.get(
                f"{cfg.gmail_mcp_url}/api/v1/messages",
                params={
                    "q": f"from:{cfg.alphasignal_sender} is:unread",
                    "max_results": 10,
                },
            )
            resp.raise_for_status()
            messages: list[dict] = resp.json().get("messages", [])

        for msg in messages:
            msg_id = msg.get("id", "")
            subject = msg.get("subject", "(no subject)")
            date_str = msg.get("date")
            html_body = msg.get("body_html", "") or msg.get("snippet", "")

            if not html_body:
                continue

            links = _extract_links_from_html(html_body)
            pub_at = None
            if date_str:
                try:
                    pub_at = datetime.fromisoformat(date_str).isoformat()
                except Exception:
                    pub_at = None

            for link in links:
                guid = hashlib.sha256(
                    f"gmail:{msg_id}:{link['url']}".encode()
                ).hexdigest()[:32]
                item = {
                    "guid": guid,
                    "title": link["title"],
                    "url": link["url"],
                    "summary": f"Via Alpha Signal email: {subject}",
                    "content_html": None,
                    "published_at": pub_at,
                    "tags": ["alpha-signal", "newsletter"],
                }
                if await upsert_item(feed_id, item):
                    new_count += 1

            # Mark email as read in Gmail (best-effort)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        f"{cfg.gmail_mcp_url}/api/v1/messages/{msg_id}/read",
                    )
            except Exception:
                pass

    except Exception as exc:
        log.error("Gmail Alpha Signal poll failed: %s", exc)

    log.info("Gmail Alpha Signal: %d new items extracted", new_count)
    return new_count
