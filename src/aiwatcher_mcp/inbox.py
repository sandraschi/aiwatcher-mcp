"""Inbox — drop markdown analysis from opencode into the ingestion pipeline.

Files placed in the inbox dir (default `data/inbox/`) are picked up by
`inbox_scan` and ingested into the items table under a dedicated "Opencode
Analysis" feed. The `inbox_add` MCP tool accepts content directly.

Also provides ``publish_morning_news`` — renders top items as a pretty
dark-theme HTML page and publishes it to the Intel Reports Hub at a
stable URL (``report_id=morning-news``) you can bookmark in Firefox.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_success, upsert_item

log = logging.getLogger(__name__)

_INBOX_FEED_ID: int | None = None
_INBOX_FEED_NAME = "Opencode Analysis"
_INBOX_FEED_TYPE = "inbox"


async def _inbox_feed_id() -> int:
    global _INBOX_FEED_ID
    if _INBOX_FEED_ID is not None:
        return _INBOX_FEED_ID
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE feed_type=? AND name=?",
            (_INBOX_FEED_TYPE, _INBOX_FEED_NAME),
        ) as cur:
            row = await cur.fetchone()
        if row:
            _INBOX_FEED_ID = int(row["id"])
            return _INBOX_FEED_ID
        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            (_INBOX_FEED_NAME, "inbox://local/", _INBOX_FEED_TYPE),
        )
        await db.commit()
        _INBOX_FEED_ID = int(cur.lastrowid or 0)
        return _INBOX_FEED_ID


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML-style frontmatter from markdown content.

    Returns (metadata, body).
    """
    meta: dict[str, str] = {}
    body = content
    lines = content.split("\n", 20)
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines):
            if lines[end].strip() == "---":
                break
            m = re.match(r"(\w+):\s*(.+)", lines[end])
            if m:
                meta[m.group(1).lower()] = m.group(2).strip()
            end += 1
        if end < len(lines):
            body = "\n".join(lines[end + 1 :])
    return meta, body


def _detect_title(content: str, filename: str = "") -> str:
    """Extract title from frontmatter, first heading, or filename."""
    meta, body = _parse_frontmatter(content)
    if meta.get("title"):
        return meta["title"]
    first_line = body.strip().split("\n")[0] if body.strip() else ""
    if first_line.startswith("# "):
        return first_line[2:].strip()
    if filename:
        stem = Path(filename).stem
        if stem.endswith(".ingested"):
            stem = stem[: -len(".ingested")]
        return stem.replace("-", " ").replace("_", " ").strip().title()
    return "Untitled Analysis"


async def ingest_markdown(
    *,
    title: str,
    content: str,
    source: str = "opencode",
    tags: list[str] | None = None,
    url: str = "",
    urgency_hint: float | None = None,
) -> dict:
    """Ingest a markdown analysis item into the database under the Inbox feed.

    Parses frontmatter from content, creates a DB entry, and pre-scores it
    when urgency_hint is provided so it flows into distillation/digests.
    """
    meta, body = _parse_frontmatter(content)
    effective_title = title or meta.get("title", "Untitled Analysis")
    effective_tags = list(tags or [])

    if meta.get("tags"):
        effective_tags.extend(t.strip() for t in meta["tags"].split(",") if t.strip())
    if source:
        effective_tags.append(f"source:{source}")

    feed_id = await _inbox_feed_id()
    stamp = datetime.now(UTC).isoformat()

    guid_src = f"inbox:{effective_title}:{stamp}"
    guid = f"inbox:{hashlib.sha256(guid_src.encode()).hexdigest()[:24]}"

    body_text = (body or content)[:10000]

    item: dict[str, Any] = {
        "guid": guid,
        "title": effective_title[:500],
        "url": url or None,
        "summary": body_text[:800],
        "content_html": None,
        "published_at": stamp,
        "tags": list(set(effective_tags)),
    }

    if urgency_hint is not None:
        score = min(10.0, max(0.0, float(urgency_hint)))
        item["urgency_score"] = score
        item["relevance_score"] = score
        item["distilled_at"] = stamp
        item["distilled_summary"] = body_text[:2000]

    inserted = await upsert_item(feed_id, item)
    await record_feed_success(feed_id)

    log.info(
        "Inbox ingest %s: %s",
        "inserted" if inserted else "duplicate",
        effective_title[:80],
    )
    return {
        "success": True,
        "inserted": inserted,
        "guid": guid,
        "feed_id": feed_id,
        "source": source,
        "title": effective_title,
    }


def inbox_dir() -> Path:
    cfg = get_settings()
    p = Path(cfg.inbox_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def scan_inbox() -> list[dict]:
    """Scan the inbox directory for new .md files and ingest each."""
    basedir = inbox_dir()
    results: list[dict] = []
    for f in sorted(basedir.glob("*.md")):
        if f.name.endswith(".ingested.md"):
            continue
        content = f.read_text(encoding="utf-8")
        title = _detect_title(content, f.name)
        result = await ingest_markdown(title=title, content=content, source="inbox-scan")
        if result.get("inserted"):
            f.rename(f.with_name(f.stem + ".ingested.md"))
        results.append(result)
    return results


_NEWS_CSS = """
:root{--bg:#0f172a;--card:#1e293b;--accent:#f59e0b;--text:#e2e8f0;--muted:#64748b;--border:#334155}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);padding:2rem 1rem;max-width:960px;margin:0 auto}
h1{font-size:1.75rem;font-weight:700;margin-bottom:0.25rem;display:flex;align-items:center;gap:0.75rem}
h1 span{font-size:0.875rem;color:var(--muted);font-weight:400}
.subtitle{color:var(--muted);margin-bottom:2rem;font-size:0.875rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:0.75rem;padding:1.25rem;margin-bottom:1rem;transition:border-color 0.15s}
.card:hover{border-color:var(--accent)}
.card h2{font-size:1.1rem;font-weight:600;margin-bottom:0.5rem;line-height:1.4}
.card h2 a{color:var(--text);text-decoration:none}
.card h2 a:hover{color:var(--accent)}
.meta{display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.5rem;font-size:0.8rem;align-items:center}
.badge{display:inline-block;padding:0.15rem 0.5rem;border-radius:999px;font-size:0.75rem;font-weight:500}
.badge-source{background:#1e3a5f;color:#93c5fd}
.badge-tag{background:#1a2e1a;color:#86efac}
.badge-urgency{background:var(--accent);color:#0f172a}
.summary{color:#cbd5e1;font-size:0.875rem;line-height:1.5}
.timestamp{color:var(--muted);font-size:0.75rem;margin-top:0.5rem}
.score-bar{display:flex;gap:0.5rem;margin-top:0.5rem;align-items:center}
.score-fill{height:4px;border-radius:2px;flex:1;background:var(--border);overflow:hidden}
.score-fill span{display:block;height:100%;border-radius:2px;background:var(--accent)}
.footer{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);color:var(--muted);font-size:0.8rem;display:flex;justify-content:space-between}
"""


def _render_news_html(items: list[dict]) -> str:
    """Render top items as a pretty dark-theme morning news page."""
    cards_html = ""
    for _i, item in enumerate(items, 1):
        title = item.get("title", "Untitled")
        url = item.get("url") or ""
        source = item.get("feed_name") or item.get("source", "unknown")
        summary = (item.get("distilled_summary") or item.get("summary", ""))[:300]
        urgency = item.get("urgency_score")
        tags_raw = item.get("tags") or item.get("bundle_tags") or "[]"
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw

        if not summary:
            summary = title

        tag_badges = "".join(f'<span class="badge badge-tag">{t}</span>' for t in (tags or [])[:4])
        urgency_badge = (
            f'<span class="badge badge-urgency">{urgency:.1f}</span>' if urgency is not None else ""
        )
        url_part = f'href="{url}" target="_blank" rel="noopener"' if url else ""
        title_html = f"<a {url_part}>{title}</a>" if url else title
        score_width = f"{min(urgency or 0, 10) * 10:.0f}%"
        score_bar = (
            f'<div class="score-bar"><span class="score-fill"><span style="width:{score_width}"></span></span></div>'
            if urgency is not None
            else ""
        )
        stamp = item.get("fetched_at", "")[:10]

        cards_html += f"""<div class="card">
<h2>{title_html}</h2>
<div class="meta">
<span class="badge badge-source">{source}</span>
{tag_badges}
{urgency_badge}
</div>
<div class="summary">{summary}</div>
<div class="timestamp">{stamp}</div>
{score_bar}
</div>"""

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morning News — {now[:10]}</title><style>{_NEWS_CSS}</style></head>
<body>
<h1>Morning News <span>{now[:10]}</span></h1>
<p class="subtitle">{len(items)} top items from the last 24 hours · aiwatcher-mcp</p>
{cards_html}
<div class="footer"><span>aiwatcher-mcp inbox</span><span>{now}</span></div>
</body>
</html>"""


async def publish_morning_news(
    hours: int = 24,
    limit: int = 20,
    skip_inbox: bool = False,
) -> dict:
    """Fetch top items from the last N hours and publish as a morning-news HTML page
    to the Intel Reports Hub at a stable URL (``report_id=morning-news``).

    Returns the hub URL the page is served at.
    """
    from aiwatcher_mcp.database import get_recent_items

    items = await get_recent_items(hours=hours, limit=limit, exclude_feed_ids=[25, 27])

    html = _render_news_html(items)

    cfg = get_settings()
    hub_url = cfg.intel_hub_url.rstrip("/")
    publish_url = f"{hub_url}/api/reports/publish"
    title = f"Morning News — {datetime.now(UTC).strftime('%Y-%m-%d')}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                publish_url,
                json={
                    "title": title,
                    "html": html,
                    "source": "aiwatcher",
                    "summary": f"{len(items)} items from the last {hours}h",
                    "tags": ["morning-news", "aiwatcher"],
                    "report_id": "morning-news",
                },
            )
            if resp.status_code != 200:
                log.error("Intel Hub publish failed: HTTP %s %s", resp.status_code, resp.text[:200])
                return {
                    "success": False,
                    "error": f"Hub returned HTTP {resp.status_code}",
                    "hub_url": hub_url,
                }

            result = resp.json()
            result["hub_url"] = hub_url
            result["stable_url"] = f"{hub_url}/reports/morning-news"
            result["item_count"] = len(items)
            log.info("Morning news published: %s/reports/morning-news", hub_url)
            return result
    except httpx.HTTPError as exc:
        log.error("Intel Hub unreachable for morning news: %s", exc)
        return {"success": False, "error": f"Hub unreachable: {exc}", "hub_url": hub_url}


async def list_inbox() -> dict:
    """List pending files + recently ingested items from DB."""
    basedir = inbox_dir()
    pending = sorted(basedir.glob("*.md"))
    ingested = sorted(basedir.glob("*.ingested.md"))

    feed_id = await _inbox_feed_id()
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id, title, fetched_at, distilled_at, tags FROM items WHERE feed_id=? ORDER BY id DESC LIMIT 20",
            (feed_id,),
        )
        db_items = [dict(r) for r in await cur.fetchall()]

    return {
        "pending_files": [f.name for f in pending if not f.name.endswith(".ingested.md")],
        "ingested_files": [f.name for f in ingested],
        "recent_db_items": [
            {
                "id": r["id"],
                "title": r["title"],
                "fetched_at": r["fetched_at"],
                "distilled_at": r["distilled_at"],
                "tags": json.loads(r["tags"]) if isinstance(r.get("tags"), str) else r.get("tags"),
            }
            for r in db_items
        ],
    }
