"""
Hugging Face ingestion — author watchlist, discovery, papers, and model drops.

Upstream signal: HF model API sorted by createdAt catches new repos hours before
RSS/Alpha Signal. Weight gating avoids empty placeholders; base_model clustering
collapses quant floods into one digest item.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.database import get_db, record_feed_failure, record_feed_success, upsert_item
from aiwatcher_mcp.scrubber import Scrubber

log = logging.getLogger(__name__)

_HF_API_BASE = "https://huggingface.co/api"
_WEIGHT_EXTENSIONS = (".safetensors", ".gguf")

_FEED_CACHE: dict[str, int] = {}
_RUNTIME_HF_WATCHLIST: list[str] | None = None


def get_effective_hf_watchlist() -> list[str]:
    if _RUNTIME_HF_WATCHLIST is not None:
        return list(_RUNTIME_HF_WATCHLIST)
    return get_settings().parsed_hf_watchlist()


def set_runtime_hf_watchlist(watchlist: list[str] | None) -> None:
    global _RUNTIME_HF_WATCHLIST
    _RUNTIME_HF_WATCHLIST = watchlist


def _hf_headers() -> dict[str, str]:
    token = get_settings().hf_token.strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _model_id(model: dict[str, Any]) -> str:
    return str(model.get("modelId") or model.get("id") or "")


def _has_real_weights(model: dict[str, Any], min_bytes: int) -> bool:
    """Gate alerts: require real weight files or a populated model card."""
    siblings = model.get("siblings") or []
    for sibling in siblings:
        name = str(sibling.get("rfilename") or "")
        if not any(name.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
            continue
        size = int(sibling.get("size") or 0)
        if size >= min_bytes:
            return True

    card = model.get("cardData") or {}
    if isinstance(card, dict) and (card.get("base_model") or card.get("language")):
        return True
    return bool(model.get("description"))


def _cluster_key(model: dict[str, Any]) -> str:
    card = model.get("cardData") or {}
    base = card.get("base_model") if isinstance(card, dict) else None
    if base:
        return f"base:{base}"
    mid = _model_id(model)
    # Canonical repo without base_model — key by modelId so derivatives join this cluster
    return f"base:{mid}" if mid else "model:unknown"


def _cluster_models(models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        key = _cluster_key(model)
        clusters.setdefault(key, []).append(model)
    return clusters


def _pick_primary(
    cluster: list[dict[str, Any]], min_bytes: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base_ids = {
        (m.get("cardData") or {}).get("base_model")
        for m in cluster
        if isinstance(m.get("cardData"), dict) and (m.get("cardData") or {}).get("base_model")
    }
    for model in cluster:
        if _model_id(model) in base_ids:
            derivatives = [m for m in cluster if _model_id(m) != _model_id(model)]
            return model, derivatives

    weighted = [m for m in cluster if _has_real_weights(m, min_bytes)]
    pool = weighted or cluster
    pool = sorted(pool, key=lambda m: m.get("createdAt") or "")
    primary = pool[0]
    derivatives = [m for m in cluster if _model_id(m) != _model_id(primary)]
    return primary, derivatives


def _format_size(num_bytes: int) -> str:
    if num_bytes >= 1_000_000_000:
        return f"{num_bytes / 1_000_000_000:.1f}GB"
    if num_bytes >= 1_000_000:
        return f"{num_bytes / 1_000_000:.0f}MB"
    if num_bytes >= 1_000:
        return f"{num_bytes / 1_000:.0f}KB"
    return f"{num_bytes}B"


def _largest_weight_label(model: dict[str, Any]) -> str:
    siblings = model.get("siblings") or []
    best_name = ""
    best_size = 0
    for sibling in siblings:
        name = str(sibling.get("rfilename") or "")
        if not any(name.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
            continue
        size = int(sibling.get("size") or 0)
        if size > best_size:
            best_size = size
            best_name = name
    if best_name and best_size:
        return f"{best_name} ({_format_size(best_size)})"
    return _model_id(model)


def _build_cluster_summary(primary: dict[str, Any], derivatives: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    description = primary.get("description") or ""
    if description:
        parts.append(str(description))

    likes = primary.get("likes", 0)
    downloads = primary.get("downloads", 0)
    if likes or downloads:
        parts.append(f"{likes} likes · {downloads} downloads")

    if derivatives:
        lines = [f"- {_model_id(d)}: {_largest_weight_label(d)}" for d in derivatives[:12]]
        if len(derivatives) > 12:
            lines.append(f"- … and {len(derivatives) - 12} more quant variants")
        parts.append(f"Quant variants ({len(derivatives)}):\n" + "\n".join(lines))

    card = primary.get("cardData") or {}
    base = card.get("base_model") if isinstance(card, dict) else None
    if base and _model_id(primary) != base:
        parts.append(f"Base model: {base}")

    return "\n\n".join(parts)


async def _get_or_create_hf_feed(name: str, category: str) -> int:
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
        feed_id = int(cur.lastrowid or 0)
        _FEED_CACHE[key] = feed_id
        log.info("Created huggingface feed id=%d name=%s", feed_id, name)
        return int(feed_id or 0)


def _hf_item(
    feed_id: int,
    guid_prefix: str,
    title: str,
    url: str,
    summary: str | None,
    published_at: str | None,
    tags: list[str],
    *,
    cluster_key: str | None = None,
) -> dict[str, Any]:
    guid_source = cluster_key or url
    guid = hashlib.sha256(f"{guid_prefix}:{guid_source}".encode()).hexdigest()[:32]
    return {
        "guid": guid,
        "title": title,
        "url": url,
        "summary": summary,
        "content_html": None,
        "published_at": published_at,
        "tags": tags + ["huggingface", guid_prefix],
    }


async def _ingest_model_clusters(
    feed_id: int,
    models: list[dict[str, Any]],
    guid_prefix: str,
    extra_tags: list[str],
) -> int:
    cfg = get_settings()
    min_bytes = cfg.hf_min_weight_bytes
    scrubber = Scrubber()
    new_count = 0

    gated = [m for m in models if _has_real_weights(m, min_bytes)]
    skipped = len(models) - len(gated)
    if skipped:
        log.debug("HF: skipped %d models without weights/card", skipped)

    for _key, cluster in _cluster_models(gated).items():
        primary, derivatives = _pick_primary(cluster, min_bytes)
        model_id = _model_id(primary)
        if not model_id:
            continue

        title = model_id
        if derivatives:
            title = f"{model_id} (+{len(derivatives)} quants)"

        url = f"https://huggingface.co/{model_id}"
        summary = _build_cluster_summary(primary, derivatives)
        published = primary.get("createdAt") or primary.get("lastModified")
        tags = list(primary.get("tags") or [])
        pipeline_tag = primary.get("pipeline_tag")
        if pipeline_tag:
            tags.append(f"pipeline:{pipeline_tag}")
        author = model_id.split("/")[0] if "/" in model_id else ""
        if author:
            tags.append(f"hf-author:{author}")
        card = primary.get("cardData") or {}
        base = card.get("base_model") if isinstance(card, dict) else None
        if base:
            tags.append(f"hf-base:{base}")
        tags.extend(extra_tags + ["hf-model", "hf-cluster"])

        item = _hf_item(
            feed_id,
            guid_prefix,
            title,
            url,
            summary,
            published,
            tags,
            cluster_key=_cluster_key(primary),
        )

        result, _reason = scrubber.check_item(item)
        if result in ("spam", "scam"):
            continue

        if await upsert_item(feed_id, item):
            new_count += 1

    return new_count


async def poll_huggingface() -> dict[str, int]:
    """Poll enabled Hugging Face sources. Returns {category: new_count}."""
    cfg = get_settings()
    if not cfg.huggingface_enabled:
        return {}

    results: dict[str, int] = {}
    headers = _hf_headers()
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        watchlist = get_effective_hf_watchlist()
        if watchlist:
            results["watchlist"] = await _poll_author_watchlist(client, watchlist)
        if cfg.hf_discovery_enabled:
            results["discovery"] = await _poll_discovery(client)
        if cfg.hf_include_papers:
            results["papers"] = await _poll_daily_papers(client)
        if cfg.hf_include_models:
            results["models"] = await _poll_new_models(client)
        if cfg.hf_include_modified:
            results["modified"] = await _poll_modified_models(client)
        if cfg.hf_include_trending:
            results["trending"] = await _poll_trending(client)

    if results:
        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()

    return results


async def _poll_author_watchlist(client: httpx.AsyncClient, authors: list[str]) -> int:
    """Poll followed authors by createdAt — upstream of RSS/Alpha Signal."""
    feed_id = await _get_or_create_hf_feed("HuggingFace Author Watchlist", "watchlist")
    cfg = get_settings()
    all_models: list[dict[str, Any]] = []

    for author in authors:
        try:
            resp = await client.get(
                f"{_HF_API_BASE}/models",
                params={
                    "author": author,
                    "sort": "createdAt",
                    "direction": "-1",
                    "full": "true",
                    "limit": cfg.hf_poll_max_per_author,
                },
            )
            resp.raise_for_status()
            models = resp.json()
            if isinstance(models, list):
                all_models.extend(models)
                log.debug("HF watchlist: %d models from author %s", len(models), author)
        except Exception as exc:
            log.warning("HF watchlist poll failed for author %s: %s", author, exc)

    try:
        new_count = await _ingest_model_clusters(
            feed_id,
            all_models,
            "watchlist",
            ["hf-watchlist"],
        )
        await record_feed_success(feed_id)
        log.info(
            "HuggingFace watchlist (%d authors): %d new clusters",
            len(authors),
            new_count,
        )
        return new_count
    except Exception as exc:
        log.error("HuggingFace watchlist ingest failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))
        return 0


async def _poll_discovery(client: httpx.AsyncClient) -> int:
    """Discovery channel: recent high-like models not tied to a fixed author list."""
    feed_id = await _get_or_create_hf_feed("HuggingFace Discovery", "discovery")
    cfg = get_settings()
    cutoff = datetime.now(tz=UTC) - timedelta(days=cfg.hf_discovery_max_age_days)

    try:
        resp = await client.get(
            f"{_HF_API_BASE}/models",
            params={
                "sort": "likes",
                "direction": "-1",
                "full": "true",
                "limit": cfg.hf_discovery_limit,
            },
        )
        resp.raise_for_status()
        models = resp.json()
        if not isinstance(models, list):
            models = []

        recent: list[dict[str, Any]] = []
        for model in models:
            created_raw = model.get("createdAt")
            if not created_raw:
                continue
            try:
                created = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            if created >= cutoff:
                recent.append(model)

        new_count = await _ingest_model_clusters(
            feed_id,
            recent,
            "discovery",
            ["hf-discovery"],
        )
        await record_feed_success(feed_id)
        log.info(
            "HuggingFace discovery: %d new clusters from %d candidates", new_count, len(recent)
        )
        return new_count
    except Exception as exc:
        log.error("HuggingFace discovery poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))
        return 0


async def _poll_daily_papers(client: httpx.AsyncClient) -> int:
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
                summary = (
                    f"{summary}\n\nAuthors: "
                    f"{', '.join(a if isinstance(a, str) else a.get('name', '') for a in authors)}"
                )

            item = _hf_item(
                feed_id,
                "paper",
                title,
                abs_url,
                summary,
                published,
                tags_list + ["hf-paper"],
            )

            result, _reason = Scrubber().check_item(item)
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
    """Global new model drops sorted by createdAt (not lastModified)."""
    feed_id = await _get_or_create_hf_feed("HuggingFace New Models", "models")

    try:
        resp = await client.get(
            f"{_HF_API_BASE}/models",
            params={"sort": "createdAt", "direction": "-1", "full": "true", "limit": 30},
        )
        resp.raise_for_status()
        models = resp.json()
        if not isinstance(models, list):
            models = []

        new_count = await _ingest_model_clusters(
            feed_id,
            models,
            "model",
            ["hf-global"],
        )
        await record_feed_success(feed_id)
        log.info("HuggingFace new models: %d new clusters", new_count)
        return new_count
    except Exception as exc:
        log.error("HuggingFace models poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))
        return 0


async def _poll_modified_models(client: httpx.AsyncClient) -> int:
    """Lower-priority signal: quant additions and card edits (lastModified)."""
    feed_id = await _get_or_create_hf_feed("HuggingFace Model Updates", "modified")

    try:
        resp = await client.get(
            f"{_HF_API_BASE}/models",
            params={"sort": "lastModified", "direction": "-1", "full": "true", "limit": 20},
        )
        resp.raise_for_status()
        models = resp.json()
        if not isinstance(models, list):
            models = []

        new_count = await _ingest_model_clusters(
            feed_id,
            models,
            "modified",
            ["hf-modified"],
        )
        await record_feed_success(feed_id)
        log.info("HuggingFace modified models: %d new clusters", new_count)
        return new_count
    except Exception as exc:
        log.error("HuggingFace modified poll failed: %s", exc)
        await record_feed_failure(feed_id, str(exc))
        return 0


async def _poll_trending(client: httpx.AsyncClient) -> int:
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

            result, _reason = Scrubber().check_item(item)
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
