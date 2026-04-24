"""
Distillation — Claude API scoring, Sandra-persona summary, digest generation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import (
    get_undistilled_items,
    update_item_scores,
    get_recent_items,
    get_db,
)

log = logging.getLogger(__name__)

SANDRA_SYSTEM = """You are Sandra's AI news analyst. Sandra is a senior full-stack developer
in Vienna running a 135+ MCP server fleet (FastMCP 3.2), with active interests in:
- AI tooling (Claude, Cursor, Windsurf, Gemini, local LLMs)
- AI model releases and capability jumps
- Robotics and humanoids (Noetix Bumi, ROS2)
- Geopolitics of AI (China, EU regulation, US policy)
- Portfolio-relevant events: acquisitions, shutdowns, security vulnerabilities in AI infra
- MCP protocol ecosystem developments

Score each item 0–10 on RELEVANCE and URGENCY using these criteria:

RELEVANCE (0-10): How much does Sandra care?
  10 = directly affects her tooling/fleet/portfolio (e.g. Cursor acquired by xAI)
  8-9 = major AI capability release (GPT-6, Claude 5, Gemini 5)
  6-7 = significant ecosystem news (major funding, policy, robotics milestone)
  4-5 = interesting but not actionable
  0-3 = generic tech/business news with thin AI angle

URGENCY (0-10): How time-sensitive is the action?
  9-10 = BREAKING — needs immediate attention (acquisition, security breach, product shutdown)
  7-8 = High — Sandra should read within hours
  5-6 = Medium — daily digest worthy
  0-4 = Background — weekly roundup level

Respond ONLY with valid JSON, no markdown fences.
"""

ITEM_PROMPT = """Analyze this AI news item for Sandra:

Title: {title}
Source: {feed_name}
URL: {url}
Content: {content}

Return JSON:
{{
  "relevance_score": <float 0-10>,
  "urgency_score": <float 0-10>,
  "tags": [<list of 3-6 topic tags>],
  "summary": "<2-3 sentence Sandra-voice summary — direct, technical, no hype>",
  "reason": "<1 sentence why this scored as it did>"
}}"""

DIGEST_SYSTEM = """You are writing the AIWatcher daily digest for Sandra (Vienna, MCP fleet dev)
and her brother Steve (retired bank IT, Vienna). Both are technically literate but Steve
is less deep in the MCP/LLM weeds. Write in clear, direct prose — no bullet-point walls.
Sandra's voice: dry, precise, no hype. One subject line, one intro paragraph, then sections
by urgency tier. Always include: CRITICAL ALERTS (if any), TOP STORIES, PORTFOLIO WATCH,
TECH DEEP DIVE. Max 800 words. Return JSON with keys: subject, html_body, text_body."""


async def distill_items(batch_size: int = 20) -> int:
    """Score undistilled items with Claude. Returns count processed."""
    cfg = get_settings()
    if not cfg.anthropic_api_key:
        log.warning("No ANTHROPIC_API_KEY — skipping distillation")
        return 0

    items = await get_undistilled_items(batch_size)
    if not items:
        return 0

    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    processed = 0

    for item in items:
        content = item.get("summary") or item.get("content_html") or item.get("title", "")
        # Strip HTML tags crudely — BeautifulSoup would be cleaner
        content = content[:2000] if content else "(no content)"

        prompt = ITEM_PROMPT.format(
            title=item["title"],
            feed_name=item.get("feed_name", "Unknown"),
            url=item.get("url", ""),
            content=content,
        )

        try:
            msg = await client.messages.create(
                model=cfg.distillation_model,
                max_tokens=512,
                system=SANDRA_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            data = json.loads(raw)

            await update_item_scores(
                item_id=item["id"],
                relevance=float(data.get("relevance_score", 0)),
                urgency=float(data.get("urgency_score", 0)),
                summary=data.get("summary", ""),
                tags=data.get("tags", []),
            )
            processed += 1
            log.debug(
                "Scored '%s': R=%.1f U=%.1f",
                item["title"][:60],
                data.get("relevance_score", 0),
                data.get("urgency_score", 0),
            )
        except Exception as exc:
            log.error("Distillation error for item %d: %s", item["id"], exc)

    log.info("Distilled %d/%d items", processed, len(items))
    return processed


async def generate_digest(hours: int = 24) -> dict[str, Any]:
    """Generate HTML+text digest from recent scored items."""
    cfg = get_settings()
    items = await get_recent_items(hours=hours, limit=30)
    if not items:
        return {"subject": "No news today", "html_body": "", "text_body": ""}

    # Build item list for Claude
    item_list = []
    for i in items:
        item_list.append({
            "title": i["title"],
            "source": i.get("feed_name", ""),
            "url": i.get("url", ""),
            "urgency": i.get("urgency_score"),
            "relevance": i.get("relevance_score"),
            "summary": i.get("distilled_summary") or i.get("summary", ""),
            "tags": json.loads(i.get("tags") or "[]"),
        })

    prompt = f"""Create today's AIWatcher digest from these {len(item_list)} items:

{json.dumps(item_list, indent=2, ensure_ascii=False)[:8000]}

Recipients: Sandra (MCP fleet dev, Vienna) and Steve (retired bank IT, Vienna).
Return JSON with keys: subject (str), html_body (full HTML email string), text_body (plain text).
HTML must be self-contained with inline styles — it will be sent as email.
Use a dark-accented, clean design. Include urgency badges (CRITICAL/HIGH/MEDIUM).
"""

    if not cfg.anthropic_api_key:
        # Fallback: build basic digest without Claude
        return _build_fallback_digest(item_list, hours)

    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    try:
        msg = await client.messages.create(
            model=cfg.distillation_model,
            max_tokens=4096,
            system=DIGEST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        return json.loads(raw)
    except Exception as exc:
        log.error("Digest generation error: %s", exc)
        return _build_fallback_digest(item_list, hours)


def _build_fallback_digest(items: list[dict], hours: int) -> dict[str, Any]:
    """Plain fallback digest when Claude API unavailable."""
    subject = f"AIWatcher Digest — {len(items)} items from last {hours}h"
    rows = ""
    for i in items:
        u = i.get("urgency") or 0
        badge = "🔴 CRITICAL" if u >= 9 else "🟡 HIGH" if u >= 7 else "🔵 MEDIUM"
        rows += f"<tr><td>{badge}</td><td><a href='{i.get('url','')}' style='color:#f59e0b'>{i['title']}</a></td><td>{i.get('source','')}</td></tr>\n"

    html = f"""<!DOCTYPE html><html><body style='background:#09090b;color:#e4e4e7;font-family:Inter,sans-serif;padding:24px'>
<h1 style='color:#f59e0b'>AIWatcher Digest</h1>
<p>Last {hours} hours — {len(items)} items scored</p>
<table style='width:100%;border-collapse:collapse'>
<thead><tr><th style='text-align:left;color:#a1a1aa'>Priority</th><th style='text-align:left;color:#a1a1aa'>Title</th><th style='text-align:left;color:#a1a1aa'>Source</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>"""

    text = f"{subject}\n\n" + "\n".join(
        f"[{i.get('urgency') or 0:.0f}] {i['title']} — {i.get('url','')}" for i in items
    )
    return {"subject": subject, "html_body": html, "text_body": text}
