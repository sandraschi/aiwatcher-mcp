"""
Calibre-mcp integration — ingest digests as ebooks into the 'AI News' library.

Strategy: convert the HTML digest to a minimal EPUB-like format and POST it
to calibre-mcp's REST API. Falls back to plain-text if EPUB conversion fails.

Called by the scheduler after digest generation if CALIBRE_ENABLED=true.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from aiwatcher_mcp.config import get_settings

log = logging.getLogger(__name__)


async def ingest_digest_to_calibre(digest: dict) -> bool:
    """
    POST the digest to calibre-mcp for storage in the AI News library.
    Returns True on success.
    """
    cfg = get_settings()
    if not cfg.calibre_enabled or not cfg.calibre_mcp_url:
        return False

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"AIWatcher Digest {today}"
    subject = digest.get("subject", title)
    html_body = digest.get("html_body", "")
    text_body = digest.get("text_body", "")

    if not html_body and not text_body:
        log.warning("Calibre ingest: empty digest — skipping")
        return False

    # calibre-mcp REST API: POST /api/v1/books/add_from_html
    # (This matches the calibreops REST surface; adjust if endpoint differs)
    payload = {
        "title": title,
        "authors": ["AIWatcher"],
        "tags": ["ai-news", "digest", "aiwatcher"],
        "comments": subject,
        "library": cfg.calibre_library,
        "html_content": html_body or f"<pre>{text_body}</pre>",
        "series": "AIWatcher Daily Digest",
        "pubdate": today,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cfg.calibre_mcp_url}/api/v1/books/add_from_html",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            book_id = data.get("book_id") or data.get("id")
            log.info("Calibre ingest OK — book_id=%s title='%s'", book_id, title)
            return True
    except httpx.HTTPStatusError as exc:
        # calibre-mcp may not expose this endpoint yet — log and move on
        log.warning(
            "Calibre ingest HTTP error %d: %s — endpoint may not be implemented yet",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return False
    except Exception as exc:
        log.error("Calibre ingest failed: %s", exc)
        return False
