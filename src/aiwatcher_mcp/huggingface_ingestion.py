"""
Hugging Face ingestion — polls HF daily papers, trending models, and new models.

Uses public HF APIs (no API key required for read):
  - /api/daily_papers — curated ML papers
  - /api/models?sort=lastModified — recently published models
  - /api/trending — trending models and spaces
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_failure, record_feed_success, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_HF_API_BASE = "https://huggingface.co/api"

_FEED_CACHE: dict[str, int] = {}


async def _get_or_create_hf_feed(name: str, category: str) -> int:
    """Ensure a 'huggingface' type feed exists, return its id."""
    key = f"hf:{category}:{name}"
    if key in _FEED_CACHE:
        return _FEED_CACHE[key]

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='huggingface'",
            (name,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            _FEED_CACHE[key] = row["id"]
            return row["id"]

        url = f"hf://{category}/{name.lower().replace(' ', '-')}"
        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
            (name, url, "huggingface"),
        )
        await db.commit()
        feed_id = cur.lastrowid
        _FEED_CACHE[key] = feed_id
        log.info("Created huggingface feed id=%d name=%s", feed_id, name)
        return feed_id


def _hf_item(
    feed_id: int,
    guid_prefix: str,
    title: str,
    url: str,
    summary: str | None,
    published_at: str | None,
    tags: list[str],
) -> dict:
    guid = hashlib.sha256(f"{guid_prefix}:{url}".encode()).hexdigest()[:32]
    return {
        "guid": guid,
        "title": title,
        "url": url,
        "summary": summary,
        "content_html": None,
        "published_at": published_at,
        "tags": tags + ["huggingface", guid_prefix],
    }


async def poll_huggingface() -> dict[str, int]:
    """
    Poll enabled Hugging Face sources (daily papers, models, trending).
    Returns {category: new_count}.
    """
    cfg = get_settings()
    if not cfg.huggingface_enabled:
        return {}

    results: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        if cfg.hf_include_papers:
            results["papers"] = await _poll_daily_papers(client)
        if cfg.hf_include_models:
            results["models"] = await _poll_new_models(client)
        if cfg.hf_include_trending:
            results["trending"] = await _poll_trending(client)

    if results:
        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()

    return results


async def _poll_daily_papers(client: httpx.AsyncClient) -> int:
    """Fetch daily papers from HF daily papers API."""
    feed_id = await _get_or_create_hf_feed("HuggingFace Daily Papers", "papers")
    new_count = 0

    try:
        resp = await client.get(f"{_HF_API_BASE}/daily_papers", params={"limit": 30})
        resp.raise_for_status()
        papers = resp.json()

        for paper in papers:
            title = paper.get("title", "")
            paper_id = paper.get("paper_id", "")
            abs_url = f"https://huggingface.co/papers/{paper_id}" if paper_id else ""
            summary = paper.get("summary", "") or ""
            published = paper.get("publishedAt") or paper.get("date")
            tags_list = paper.get("categories") or paper.get("tags", [])
            authors = paper.get("authors", [])
            if authors:
                summary = f"{summary}\n\nAuthors: {', '.join(a if isinstance(a, str) else a.get('name', '') for a in authors)}"

            item = _hf_item(
                feed_id,
                "paper",
                title,
                abs_url,
                summary,
                published,
                tags_list + ["hf-paper"],
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("HuggingFace papers: %d new items", new_count)
    except Exception as exc:
        log.error("HuggingFace papers poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count


async def _poll_new_models(client: httpx.AsyncClient) -> int:
    """Fetch recently published/updated models from HF."""
    feed_id = await _get_or_create_hf_feed("HuggingFace New Models", "models")
    new_count = 0

    try:
        resp = await client.get(
            f"{_HF_API_BASE}/models",
            params={"sort": "lastModified", "direction": "-1", "limit": 30},
        )
        resp.raise_for_status()
        models = resp.json()

        for model in models:
            model_id = model.get("modelId", "") or model.get("id", "")
            if not model_id:
                continue
            title = model_id
            url = f"https://huggingface.co/{model_id}"
            summary = model.get("description", "") or ""
            published = model.get("lastModified")
            tags_list = model.get("tags", [])
            pipeline_tag = model.get("pipeline_tag", "")
            if pipeline_tag:
                tags_list = list(tags_list) + [f"pipeline:{pipeline_tag}"]
            likes = model.get("likes", 0)
            downloads = model.get("downloads", 0)
            if likes or downloads:
                summary = f"{summary}\n\n{likes} likes · {downloads} downloads"

            item = _hf_item(
                feed_id,
                "model",
                title,
                url,
                summary,
                published,
                tags_list + ["hf-model"],
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("HuggingFace models: %d new items", new_count)
    except Exception as exc:
        log.error("HuggingFace models poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count


async def _poll_trending(client: httpx.AsyncClient) -> int:
    """Fetch trending models from HF."""
    feed_id = await _get_or_create_hf_feed("HuggingFace Trending", "trending")
    new_count = 0

    try:
        resp = await client.get(f"{_HF_API_BASE}/trending", params={"limit": 30})
        resp.raise_for_status()
        data = resp.json()
        entries = data if isinstance(data, list) else data.get("trending", [])

        for entry in entries:
            repo_id = entry.get("repoId", "") or entry.get("id", "")
            repo_type = entry.get("type", "model") or "model"
            if not repo_id:
                continue
            title = f"[{repo_type}] {repo_id}"
            url = f"https://huggingface.co/{repo_id}"
            summary = entry.get("description", "") or ""
            published = entry.get("lastModified")
            tags_list = entry.get("tags", [])
            likes = entry.get("likes", 0)
            downloads = entry.get("downloads", 0)
            if likes or downloads:
                summary = f"{summary}\n\n{likes} likes · {downloads} downloads"

            item = _hf_item(
                feed_id,
                "trending",
                title,
                url,
                summary,
                published,
                tags_list + ["hf-trending", repo_type],
            )

            result, reason = Scrubber().check_item(item)
            if result in ("spam", "scam"):
                continue

            if await upsert_item(feed_id, item):
                new_count += 1

        await record_feed_success(feed_id)
        log.info("HuggingFace trending: %d new items", new_count)
    except Exception as exc:
        log.error("HuggingFace trending poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))

    return new_count
