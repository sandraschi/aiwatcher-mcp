"""
Calibre-mcp integration — ingest digests as HTML books in the configured library.

Uses calibre-mcp webapp REST: POST /api/books/ with a temp .html file (manage_books add).
"""

from __future__ import annotations

import contextlib
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import mark_items_sent_calibre

log = logging.getLogger(__name__)


async def ingest_digest_to_calibre(digest: dict) -> bool:
    """
    Add the digest HTML to calibre-mcp. Returns True on success.
    Marks digest item_ids with sent_calibre when ingest succeeds.
    """
    cfg = get_settings()
    if not cfg.calibre_enabled or not cfg.calibre_mcp_url:
        return False

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    title = f"AIWatcher Digest {today}"
    subject = digest.get("subject", title)
    html_body = digest.get("html_body", "")
    text_body = digest.get("text_body", "")

    if not html_body and not text_body:
        log.warning("Calibre ingest: empty digest — skipping")
        return False

    body = html_body or f"<html><body><pre>{text_body}</pre></body></html>"
    base = cfg.calibre_mcp_url.rstrip("/")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            prefix=f"aiwatcher-digest-{today}-",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(body)
            tmp_path = Path(tmp.name)

        payload: dict = {
            "file_path": str(tmp_path),
            "fetch_metadata": False,
            "metadata": {
                "title": title,
                "authors": ["AIWatcher"],
                "tags": ["ai-news", "digest", "aiwatcher"],
                "comments": subject,
                "series": "AIWatcher Daily Digest",
                "pubdate": today,
            },
        }
        if cfg.calibre_library:
            payload["library_path"] = cfg.calibre_library

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{base}/api/books/", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("success") is False:
                log.warning(
                    "Calibre ingest tool error: %s",
                    data.get("error", data)[:300],
                )
                return False
            book_id = None
            if isinstance(data, dict):
                book_id = (
                    data.get("book_id")
                    or data.get("id")
                    or (data.get("result") or {}).get("book_id")
                )
            log.info("Calibre ingest OK — book_id=%s title='%s'", book_id, title)

        item_ids = digest.get("item_ids") or []
        if item_ids:
            await mark_items_sent_calibre([int(i) for i in item_ids])
        return True
    except httpx.HTTPStatusError as exc:
        log.warning(
            "Calibre ingest HTTP %d: %s — expected POST %s/api/books/",
            exc.response.status_code,
            exc.response.text[:200],
            base,
        )
        return False
    except Exception as exc:
        log.error("Calibre ingest failed: %s", exc)
        return False
    finally:
        if tmp_path and tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()
