"""
HN front-page + watchlist ingestion - discovery for release-velocity stories.

Motivation (issue #11): Strata (HN item 49953495, 781 pts / 350 comments)
bypassed every hnrss keyword feed because its title holds none of the
watched words. Keyword RSS is the dumb pipe; this module is the scored
complement: Algolia front-page (machine fields) + watchlist terms +
GitHub star-velocity enrichment for linked repos.

Mirrors huggingface_ingestion.py patterns: runtime watchlist override,
dedicated feed rows (feed_type='hn'), scrubber gating, success/failure
accounting. No scraping, no comment harvesting, no user tracking.

Comment threads are read-through only: fetch_hn_comments() pulls one
thread from Algolia when the user opens it, keeps it in a short
in-memory TTL cache, and never writes it to the DB.
"""

from __future__ import annotations

import html
import logging
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_failure, record_feed_success, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
_GITHUB_API_BASE = "https://api.github.com"

_RUNTIME_HN_WATCHLIST: list[str] | None = None

# repo full_name -> (day_iso, payload). Unauthenticated GH limit is 60 req/hr;
# per-story enrichment must never become a poll loop.
_GH_CACHE: dict[str, tuple[str, dict[str, Any]]] = {}

_GH_URL_RE = re.compile(r"github\.com/([^/\s?#]+)/([^/\s?#]+)", re.IGNORECASE)


def get_effective_hn_watchlist() -> list[str]:
    if _RUNTIME_HN_WATCHLIST is not None:
        return list(_RUNTIME_HN_WATCHLIST)
    return get_settings().parsed_hn_watchlist()


def set_runtime_hn_watchlist(watchlist: list[str] | None) -> None:
    global _RUNTIME_HN_WATCHLIST
    _RUNTIME_HN_WATCHLIST = list(watchlist) if watchlist is not None else None


async def _get_or_create_hn_feed(name: str, url: str) -> int:
    """Ensure an 'hn' type feed row exists, return its id.

    Lookup key is (name, feed_type); the url column is UNIQUE, so each
    feed needs its own url. IntegrityError on INSERT falls back to
    re-SELECT (concurrent schedulers racing the same creation).
    """
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='hn'",
            (name,),
        ) as cur:
            row = await cur.fetchone()
        if row:
            return int(row["id"])
        try:
            cur = await db.execute(
                "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                (name, url, "hn"),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            async with db.execute(
                "SELECT id FROM feeds WHERE name=? AND feed_type='hn'",
                (name,),
            ) as cur:
                row = await cur.fetchone()
            if row:
                return int(row["id"])
            raise
        log.info("Created hn feed id=%d (%s)", cur.lastrowid, name)
        return int(cur.lastrowid or 0)


def _story_meets_gate(
    story: dict[str, Any],
    *,
    min_points: int,
    min_star_velocity: float,
    watchlist_hit: bool,
    star_velocity: float,
) -> bool:
    points = int(story.get("points") or 0)
    if watchlist_hit:
        return True
    if points >= min_points:
        return True
    return star_velocity >= min_star_velocity


def _parse_github_repo(url: str | None) -> str | None:
    if not url:
        return None
    match = _GH_URL_RE.search(url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    if owner in ("settings", "orgs", "search", "marketplace"):
        return None
    return f"{owner}/{repo}"


async def _github_star_velocity(
    client: httpx.AsyncClient, full_name: str
) -> tuple[float, dict[str, Any]]:
    """stars/day for a repo, cached per UTC day. Never raises - returns (0.0, {})."""
    today = datetime.now(UTC).date().isoformat()
    cached = _GH_CACHE.get(full_name)
    if cached and cached[0] == today:
        payload = cached[1]
    else:
        try:
            resp = await client.get(f"{_GITHUB_API_BASE}/repos/{full_name}")
            resp.raise_for_status()
            payload = resp.json()
            _GH_CACHE[full_name] = (today, payload)
        except Exception as exc:
            log.debug("GH enrichment failed for %s: %s", full_name, exc)
            return 0.0, {}
    try:
        stars = int(payload.get("stargazers_count") or 0)
        created = payload.get("created_at") or ""
        born = datetime.fromisoformat(created.replace("Z", "+00:00"))
        age_days = max((datetime.now(UTC) - born).days, 1)
        return stars / age_days, payload
    except Exception:
        return 0.0, {}


def _story_to_item(
    story: dict[str, Any],
    *,
    star_velocity: float,
    gh_stars: int | None,
    source_tag: str,
) -> dict[str, Any]:
    object_id = str(story.get("objectID") or "")
    title = story.get("title") or "(no title)"
    url = story.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
    points = int(story.get("points") or 0)
    comments = int(story.get("num_comments") or 0)
    author = story.get("author") or "unknown"
    bits = [f"HN: {points} points, {comments} comments, by {author}."]
    if gh_stars is not None:
        bits.append(f"GitHub: {gh_stars} stars ({star_velocity:.0f}/day).")
    story_text = (story.get("story_text") or "").strip()
    if story_text and not story.get("url"):
        bits.append(story_text[:2000])
    bits.append(f"Comments: https://news.ycombinator.com/item?id={object_id}")
    return {
        "guid": f"hn:{object_id}",
        "title": title,
        "url": url,
        "summary": " ".join(bits),
        "content_html": None,
        "published_at": story.get("created_at"),
        "tags": ["hn", source_tag],
    }


async def _ingest_stories(
    client: httpx.AsyncClient,
    feed_id: int,
    stories: list[dict[str, Any]],
    *,
    source_tag: str,
    watchlist_hit: bool,
) -> int:
    cfg = get_settings()
    new_count = 0
    for story in stories:
        if not story.get("objectID"):
            continue
        full_name = _parse_github_repo(story.get("url"))
        star_velocity = 0.0
        gh_stars: int | None = None
        if full_name:
            star_velocity, payload = await _github_star_velocity(client, full_name)
            if payload:
                gh_stars = int(payload.get("stargazers_count") or 0)
        if not _story_meets_gate(
            story,
            min_points=cfg.hn_min_points,
            min_star_velocity=cfg.hn_min_star_velocity,
            watchlist_hit=watchlist_hit,
            star_velocity=star_velocity,
        ):
            continue
        item = _story_to_item(
            story,
            star_velocity=star_velocity,
            gh_stars=gh_stars,
            source_tag=source_tag,
        )
        result, reason = Scrubber().check_item(item)
        if result in ("spam", "scam"):
            log.info("HN scrubber blocked '%s' [%s]: %s", item["title"][:60], result, reason)
            continue
        if await upsert_item(feed_id, item):
            new_count += 1
    return new_count


async def poll_hn_frontpage() -> dict[str, int]:
    """
    Poll HN front page (Algolia) + watchlist terms, enrich GH-linked
    stories with star velocity. Returns {"frontpage": n, "watchlist": m}.
    """
    cfg = get_settings()
    if not cfg.hn_enabled:
        return {}
    results: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        feed_id = await _get_or_create_hn_feed("HN Front Page", "https://hnrss.org/frontpage")
        try:
            resp = await client.get(f"{_ALGOLIA_BASE}/search", params={"tags": "front_page"})
            resp.raise_for_status()
            stories = resp.json().get("hits", [])
            results["frontpage"] = await _ingest_stories(
                client, feed_id, stories, source_tag="hn-frontpage", watchlist_hit=False
            )
            await record_feed_success(feed_id)
            log.info("HN frontpage: %d new stories", results["frontpage"])
        except Exception as exc:
            log.error("HN frontpage poll failed: %s", exc)
            await record_feed_failure(feed_id, str(exc))
            results["frontpage"] = 0

        watchlist = get_effective_hn_watchlist()
        if watchlist:
            wl_feed_id = await _get_or_create_hn_feed(
                "HN Watchlist", "https://hn.algolia.com/api/v1/search_by_date"
            )
            wl_total = 0
            for term in watchlist:
                try:
                    resp = await client.get(
                        f"{_ALGOLIA_BASE}/search_by_date",
                        params={"query": term, "tags": "story"},
                    )
                    resp.raise_for_status()
                    stories = resp.json().get("hits", [])
                    wl_total += await _ingest_stories(
                        client,
                        wl_feed_id,
                        stories,
                        source_tag="hn-watchlist",
                        watchlist_hit=True,
                    )
                except Exception as exc:
                    log.warning("HN watchlist poll failed for term '%s': %s", term, exc)
            await record_feed_success(wl_feed_id)
            results["watchlist"] = wl_total
            log.info("HN watchlist (%d terms): %d new stories", len(watchlist), wl_total)

    if results:
        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()
    return results


# ── On-demand comment threads (never persisted) ────────────────────────────────

_COMMENTS_TTL_S = 300.0
_COMMENTS_MAX_DEPTH = 8
_COMMENTS_MAX_NODES = 1500
# item_id -> (monotonic fetch time, trimmed tree)
_COMMENTS_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}

_ALLOWED_TAGS = {"p", "i", "em", "b", "strong", "pre", "code", "br", "a"}
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "template"}


class HnCommentsError(Exception):
    """Upstream failure fetching a thread; status is the HTTP code to return."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class _CommentSanitizer(HTMLParser):
    """Allowlist re-serializer for HN comment HTML.

    Text is re-escaped, only _ALLOWED_TAGS survive (without attributes),
    and <a> keeps an http(s) href only, forced to open in a new tab.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open_a = 0
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth or tag not in _ALLOWED_TAGS:
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag == "a":
            href = next((v for k, v in attrs if k == "href" and v), "").strip()
            if not re.match(r"^https?://", href, re.IGNORECASE):
                return
            self.open_a += 1
            self.out.append(
                f'<a href="{html.escape(href, quote=True)}" '
                'target="_blank" rel="noopener noreferrer nofollow">'
            )
            return
        self.out.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth = max(self._drop_depth - 1, 0)
            return
        if self._drop_depth or tag not in _ALLOWED_TAGS or tag == "br":
            return
        if tag == "a":
            if not self.open_a:
                return
            self.open_a -= 1
        self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.out.append(html.escape(data, quote=False))


def sanitize_comment_html(raw: str | None) -> str:
    """Reduce HN comment HTML to a safe allowlisted subset."""
    if not raw:
        return ""
    parser = _CommentSanitizer()
    parser.feed(raw)
    parser.close()
    return "".join(parser.out) + "</a>" * parser.open_a


def _trim_comment(node: dict[str, Any], depth: int, budget: list[int]) -> dict[str, Any] | None:
    """Algolia item node -> {id, author, created_at, text, children}. None if pruned."""
    kids_raw = [k for k in node.get("children") or [] if k.get("type") in (None, "comment")]
    children: list[dict[str, Any]] = []
    truncated = False
    if depth < _COMMENTS_MAX_DEPTH:
        for kid in kids_raw:
            if budget[0] <= 0:
                truncated = True
                break
            trimmed = _trim_comment(kid, depth + 1, budget)
            if trimmed is not None:
                children.append(trimmed)
    elif kids_raw:
        truncated = True
    text = sanitize_comment_html(node.get("text"))
    if not text and not node.get("author") and not children:
        return None  # deleted leaf
    budget[0] -= 1
    return {
        "id": node.get("id"),
        "author": node.get("author") or "[deleted]",
        "created_at": node.get("created_at"),
        "text": text,
        "children": children,
        "truncated": truncated,
    }


async def fetch_hn_comments(item_id: int, *, force: bool = False) -> dict[str, Any]:
    """Fetch one HN thread from Algolia on demand, trimmed + sanitized.

    Cached in memory for _COMMENTS_TTL_S; never written to the DB.
    Raises HnCommentsError on upstream failure.
    """
    now = time.monotonic()
    cached = _COMMENTS_CACHE.get(item_id)
    if cached and not force and now - cached[0] < _COMMENTS_TTL_S:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{_ALGOLIA_BASE}/items/{item_id}")
    except httpx.HTTPError as exc:
        raise HnCommentsError(f"Algolia unreachable: {exc}", 502) from exc
    if resp.status_code == 404:
        raise HnCommentsError(f"HN item {item_id} not found", 404)
    if resp.status_code >= 400:
        raise HnCommentsError(f"Algolia returned HTTP {resp.status_code}", 502)
    root = resp.json()

    budget = [_COMMENTS_MAX_NODES]
    comments: list[dict[str, Any]] = []
    truncated = False
    for kid in root.get("children") or []:
        if budget[0] <= 0:
            truncated = True
            break
        trimmed = _trim_comment(kid, 1, budget)
        if trimmed is not None:
            comments.append(trimmed)

    tree = {
        "id": item_id,
        "title": root.get("title") or "",
        "url": root.get("url"),
        "author": root.get("author"),
        "points": root.get("points"),
        "created_at": root.get("created_at"),
        "story_text": sanitize_comment_html(root.get("text")),
        "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
        "comment_count": _COMMENTS_MAX_NODES - budget[0],
        "max_depth": _COMMENTS_MAX_DEPTH,
        "truncated": truncated,
        "comments": comments,
    }
    _COMMENTS_CACHE[item_id] = (now, tree)
    if len(_COMMENTS_CACHE) > 64:
        oldest = min(_COMMENTS_CACHE, key=lambda k: _COMMENTS_CACHE[k][0])
        _COMMENTS_CACHE.pop(oldest, None)
    return tree
