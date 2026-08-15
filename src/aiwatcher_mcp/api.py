"""
FastAPI backend — REST API on port 10946.
Mounts FastMCP at /mcp, exposes /api/* for the React webapp.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.types import ASGIApp

from aiwatcher_mcp.api_auth import ApiKeyMiddleware
from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.fleet import discover_fleet_from_docs
from aiwatcher_mcp.server import mcp

log = logging.getLogger(__name__)
cfg = get_settings()

# Env var *name* fragments — values must not be returned verbatim from GET /api/env.
_ENV_NAME_SECRET_FRAGMENTS: tuple[str, ...] = (
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "API_KEY",
    "PRIVATE",
    "ANTHROPIC",
    "OPENAI",
    "SMTP_",
    "GMAIL_",
    "BEARER",
    "WEBHOOK",
    "AUTH",
)


def redact_env_dict(env: dict[str, str | None]) -> dict[str, str | None]:
    """Mask likely secrets for GET /api/env (fleet UI reads keys; values stay private)."""
    out: dict[str, str | None] = {}
    for key, val in env.items():
        if val is None:
            out[key] = None
            continue
        ku = key.upper()
        name_sensitive = (
            any(s in ku for s in _ENV_NAME_SECRET_FRAGMENTS)
            or ku.endswith("_KEY")
            or ku.endswith("_TOKEN")
        )
        sv = str(val).strip()
        value_sensitive = sv.startswith(("sk-", "sk_", "Bearer "))
        if name_sensitive or value_sensitive:
            out[key] = "***REDACTED***"
        else:
            out[key] = val
    return out


# Mounted MCP app — lifespan must run under the parent Starlette app so
# StreamableHTTP session manager starts (see FastMCP ASGI docs).
_mcp_http_app = mcp.http_app(path="/")


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app):
    from aiwatcher_mcp.database import init_db
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler, validate_distillation_model

    async with _mcp_http_app.router.lifespan_context(_mcp_http_app):
        log.info("aiwatcher-mcp backend starting on port %d", cfg.backend_port)
        await init_db()

        from aiwatcher_mcp.update_interests import sync_interests_from_config

        await sync_interests_from_config()

        from aiwatcher_mcp.database import get_stats

        stats = await get_stats()
        log.info(
            "DB probe OK — %d feeds, %d total items",
            stats["active_feeds"],
            stats["total_items"],
        )
        import os

        if os.environ.get("AIWATCHER_E2E") != "1":
            await validate_distillation_model()
        start_scheduler()
        yield
        stop_scheduler()
        log.info("aiwatcher-mcp backend shutdown")


# ── API handlers ───────────────────────────────────────────────────────────────


_SHUTTING_DOWN: bool = False


async def health(request: Request) -> JSONResponse:
    if _SHUTTING_DOWN:
        return JSONResponse({"status": "shutting_down", "server": "aiwatcher-mcp"})
    from aiwatcher_mcp.alerting import get_alert_channel_stats
    from aiwatcher_mcp.database import get_db, get_stats
    from aiwatcher_mcp.scheduler import get_scheduler

    stats = await get_stats()
    last_poll_at: str | None = None
    async with (
        get_db() as db,
        db.execute("SELECT MAX(last_fetched) FROM feeds WHERE last_fetched IS NOT NULL") as cur,
    ):
        row = await cur.fetchone()
        if row and row[0]:
            last_poll_at = row[0]

    sched = get_scheduler()
    return JSONResponse(
        {
            "status": "ok",
            "server": "aiwatcher-mcp",
            "service": "aiwatcher-mcp",
            "version": cfg.server_version,
            "items_total": stats["total_items"],
            "items_last_24h": stats["items_last_24h"],
            "active_feeds": stats["active_feeds"],
            "last_poll_at": last_poll_at,
            "scheduler_running": sched.running,
            "alert_channels": get_alert_channel_stats(),
        }
    )


async def capabilities(request: Request) -> JSONResponse:
    """Mandatory /api/capabilities — WEBAPP_STANDARDS.md §1.4"""
    try:
        tools = await mcp.list_tools(run_middleware=False)
        atomic_tools = sorted({t.name for t in tools})
    except Exception as exc:
        log.warning("capabilities: list_tools failed: %s", exc)
        atomic_tools = []
    n_tools = len(atomic_tools)
    return JSONResponse(
        {
            "status": "ok",
            "server": {
                "name": cfg.server_name,
                "version": cfg.server_version,
                "fastmcp": "3.2+",
                "provider": cfg.llm_provider,
            },
            "tool_surface": {
                "total": n_tools,
                "portmanteau_count": 0,
                "atomic_count": n_tools,
                "atomic_tools": atomic_tools,
            },
            "features": {
                "sampling": True,
                "agentic_workflows": True,
                "prompts": True,
                "resources": True,
                "skills": True,
                "scheduling": True,
                "robofang_integration": cfg.robofang_enabled,
                "email_delivery": cfg.email_enabled,
                "calibre_integration": cfg.calibre_enabled,
                "anthropic_key_configured": bool(cfg.anthropic_api_key),
            },
            "integrations": {
                "robofang": cfg.robofang_enabled,
                "email_mcp": bool(cfg.email_mcp_url),
                "calibre_mcp": cfg.calibre_enabled,
                "speechops": bool(cfg.speechops_http_url),
            },
            "runtime": {"transport": "dual", "surface_mode": "atomic"},
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


async def api_stats(request: Request) -> JSONResponse:
    from aiwatcher_mcp.database import get_stats

    return JSONResponse(await get_stats())


async def api_feeds(request: Request) -> JSONResponse:
    from aiwatcher_mcp.database import get_feeds

    return JSONResponse({"feeds": await get_feeds()})


async def api_morning_news(request: Request) -> JSONResponse:
    hours = int(request.query_params.get("hours", 24))
    limit = min(int(request.query_params.get("limit", 20)), 50)
    from aiwatcher_mcp.database import get_recent_items

    items = await get_recent_items(hours=min(hours, 168), limit=limit)
    return JSONResponse(
        {
            "items": items,
            "count": len(items),
            "hours": hours,
            "generated_at": __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .strftime("%Y-%m-%d %H:%M UTC"),
        }
    )


async def api_items(request: Request) -> JSONResponse:
    hours = int(request.query_params.get("hours", 24))
    limit = min(int(request.query_params.get("limit", 50)), 200)
    offset = max(int(request.query_params.get("offset", 0)), 0)
    feed_id_raw = request.query_params.get("feed_id")
    feed_id = int(feed_id_raw) if feed_id_raw is not None else None
    feed_type = request.query_params.get("feed_type") or None
    from aiwatcher_mcp.database import get_recent_items

    fetch_n = limit + 1
    rows = await get_recent_items(
        hours=min(hours, 168),
        limit=fetch_n,
        offset=offset,
        feed_id=feed_id,
        feed_type=feed_type,
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    return JSONResponse(
        {
            "items": items,
            "count": len(items),
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
        }
    )


async def api_poll(request: Request) -> JSONResponse:
    from aiwatcher_mcp.ingestion import poll_all_feeds

    results = await poll_all_feeds()
    return JSONResponse({"total_new": sum(results.values()), "by_feed": results})


async def api_distill(request: Request) -> JSONResponse:
    from aiwatcher_mcp.distillation import distill_items

    count = await distill_items(batch_size=30)
    return JSONResponse({"items_distilled": count})


async def api_check_alerts(request: Request) -> JSONResponse:
    from aiwatcher_mcp.alerting import process_alerts

    alerted = await process_alerts()
    return JSONResponse({"alerted": alerted, "count": len(alerted)})


async def api_digest_preview(request: Request) -> JSONResponse:
    hours = int(request.query_params.get("hours", 24))
    from aiwatcher_mcp.distillation import generate_digest

    digest = await generate_digest(hours=hours)
    return JSONResponse(digest)


async def api_digest_html(request: Request) -> HTMLResponse:
    """Return the digest as a rendered HTML page — for browser preview."""
    hours = int(request.query_params.get("hours", 24))
    from aiwatcher_mcp.distillation import generate_digest

    digest = await generate_digest(hours=hours)
    return HTMLResponse(digest.get("html_body", "<p>No digest available</p>"))


async def api_send_digest(request: Request) -> JSONResponse:
    from aiwatcher_mcp.distillation import generate_digest
    from aiwatcher_mcp.email_delivery import send_digest
    from aiwatcher_mcp.intel_hub_client import publish_digest_to_hub

    digest = await generate_digest(hours=24)
    success = await send_digest(digest)
    hub = await publish_digest_to_hub(digest, hours=24)
    return JSONResponse({"sent": success, "intel_hub": hub})


async def api_add_feed(request: Request) -> JSONResponse:
    body = await request.json()
    from aiwatcher_mcp.database import get_db

    async with get_db() as db:
        try:
            cur = await db.execute(
                "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                (body["name"], body["url"], body.get("feed_type", "rss")),
            )
            await db.commit()
            return JSONResponse({"id": cur.lastrowid, "ok": True})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)


async def api_toggle_feed(request: Request) -> JSONResponse:
    feed_id = int(request.path_params["feed_id"])
    from aiwatcher_mcp.database import get_db

    async with get_db() as db:
        await db.execute(
            "UPDATE feeds SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?",
            (feed_id,),
        )
        await db.commit()
    return JSONResponse({"ok": True})


async def api_get_env(request: Request) -> JSONResponse:
    from pathlib import Path

    import dotenv

    env_path = Path(".env")
    if not env_path.exists():
        return JSONResponse({})
    env_dict = dotenv.dotenv_values(env_path)
    return JSONResponse(redact_env_dict(dict(env_dict)))


async def api_update_env(request: Request) -> JSONResponse:
    body = await request.json()
    from pathlib import Path

    import dotenv

    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()

    for key, value in body.items():
        if value is None:
            continue
        sv = str(value).strip()
        if sv == "***REDACTED***":
            continue
        ku = key.upper()
        if not sv and (ku.endswith("_TOKEN") or ku.endswith("_KEY") or "PASSWORD" in ku):
            continue
        dotenv.set_key(env_path, key, str(value))

    return JSONResponse({"ok": True, "message": "Settings saved to .env"})


async def api_test_llm(request: Request) -> JSONResponse:
    body = await request.json()
    provider = body.get("provider") or cfg.llm_provider
    key = body.get("key") or cfg.anthropic_api_key
    model = body.get("model") or cfg.distillation_model
    base_url = body.get("base_url") or cfg.llm_base_url

    try:
        if provider == "anthropic":
            if not key:
                return JSONResponse({"ok": False, "error": "No API key provided"}, status_code=400)
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=key)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
        else:
            import openai

            if not base_url:
                if provider == "ollama":
                    base_url = "http://localhost:11434/v1"
                elif provider == "lmstudio":
                    base_url = "http://localhost:1234/v1"

            client = openai.AsyncOpenAI(api_key="not-needed", base_url=base_url)
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )

        return JSONResponse({"ok": True, "message": f"Connection to {provider} successful!"})
    except Exception as exc:
        log.error("LLM test failed for %s: %s", provider, exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


async def api_llm_models(request: Request) -> JSONResponse:
    """Fetch available models for a given provider.

    Query params: provider=, base_url=, key=
    """
    provider = request.query_params.get("provider") or cfg.llm_provider or "lmstudio"
    base_url = request.query_params.get("base_url") or cfg.llm_base_url or ""
    key = request.query_params.get("key") or cfg.anthropic_api_key or ""

    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if provider == "ollama":
                url = (base_url.rstrip("/") if base_url else "http://localhost:11434") + "/api/tags"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", []) if m.get("name")]
                    return JSONResponse({"models": models})
                return JSONResponse({"models": [], "error": f"HTTP {resp.status_code}"})

            elif provider == "anthropic":
                if not key:
                    return JSONResponse(
                        {
                            "models": [
                                "claude-sonnet-4-20250514",
                                "claude-3-5-sonnet-latest",
                                "claude-3-opus-latest",
                                "claude-3-haiku-latest",
                            ]
                        }
                    )
                url = "https://api.anthropic.com/v1/models"
                headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if m.get("id")]
                    return JSONResponse({"models": models})
                return JSONResponse({"models": [], "error": f"HTTP {resp.status_code}"})

            elif provider == "openai":
                if not key:
                    return JSONResponse(
                        {"models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]}
                    )
                url = (
                    base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
                ) + "/models"
                headers = {"Authorization": f"Bearer {key}"}
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if m.get("id")]
                    return JSONResponse({"models": models})
                return JSONResponse({"models": [], "error": f"HTTP {resp.status_code}"})

            elif provider == "deepseek":
                url = (
                    base_url.rstrip("/") if base_url else "https://api.deepseek.com/v1"
                ) + "/models"
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", []) if m.get("id")]
                    return JSONResponse({"models": models})
                return JSONResponse({"models": ["deepseek-chat", "deepseek-reasoner"]})

            else:
                # LM Studio / OpenAI-compatible local
                url = (base_url.rstrip("/") if base_url else "http://localhost:1234/v1") + "/models"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", m.get("name", "")) for m in data.get("data", [])]
                    return JSONResponse({"models": [m for m in models if m]})
                return JSONResponse({"models": [], "error": f"HTTP {resp.status_code}"})

    except Exception as e:
        log.warning("Failed to fetch models for %s: %s", provider, e)
        return JSONResponse({"models": [], "error": str(e)})


async def api_test_speak(request: Request) -> JSONResponse:
    body = await request.json()
    text = body.get("text", "Testing speech output.")

    if not cfg.speechops_http_url:
        return JSONResponse({"error": "Speechops not configured"}, status_code=400)

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            # speech-mcp convention: POST /api/v1/tts { "text": "...", "provider": "windows" }
            resp = await client.post(
                f"{cfg.speechops_http_url}/api/v1/tts",
                json={"text": text, "provider": "windows"},
                timeout=15,
            )
            return JSONResponse({"ok": resp.status_code == 200, "status": resp.status_code})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_test_discover_sources(request: Request) -> JSONResponse:
    body = await request.json()
    topic = body.get("topic")
    if not topic:
        return JSONResponse({"error": "topic is required"}, status_code=400)

    from aiwatcher_mcp.bundles import elicit_bundle_config

    config = await elicit_bundle_config(topic)
    return JSONResponse(config)


async def api_search(request: Request) -> JSONResponse:
    """Full-text search over items using FTS5."""
    query = request.query_params.get("q", "").strip()
    limit = int(request.query_params.get("limit", 20))
    if not query:
        return JSONResponse({"error": "q parameter required"}, status_code=400)
    from aiwatcher_mcp.database import search_items

    items = await search_items(query=query, limit=min(limit, 100))
    return JSONResponse({"items": items, "count": len(items), "query": query})


async def api_digest_history(request: Request) -> JSONResponse:
    """List recent persisted digests (metadata only, no body)."""
    limit = int(request.query_params.get("limit", 10))
    from aiwatcher_mcp.database import get_recent_digests

    digests = await get_recent_digests(limit=min(limit, 50))
    return JSONResponse({"digests": digests, "count": len(digests)})


async def api_reload_config(request: Request) -> JSONResponse:
    """
    Hot-reload settings from .env without restarting the server.
    Resets the _settings singleton so the next get_settings() re-reads .env.
    The scheduler is NOT restarted — interval changes take effect on next restart.
    """
    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    new_cfg = cfg_mod.get_settings()
    log.info(
        "Config reloaded from .env — provider=%s model=%s",
        new_cfg.llm_provider,
        new_cfg.distillation_model,
    )
    return JSONResponse(
        {
            "ok": True,
            "llm_provider": new_cfg.llm_provider,
            "distillation_model": new_cfg.distillation_model,
            "alert_threshold": new_cfg.alert_threshold,
            "item_retention_days": new_cfg.item_retention_days,
        }
    )


async def api_feed_health(request: Request) -> JSONResponse:
    """Return feeds sorted by health — degraded/disabled feeds first."""
    from aiwatcher_mcp.database import get_db
    from aiwatcher_mcp.feed_quality import enrich_feeds_with_quality

    async with (
        get_db() as db,
        db.execute(
            """SELECT id, name, url, feed_type, enabled, last_fetched,
                  consecutive_failures, last_error, created_at
           FROM feeds
           ORDER BY consecutive_failures DESC, name"""
        ) as cur,
    ):
        feeds = [dict(r) for r in await cur.fetchall()]
    feeds = await enrich_feeds_with_quality(feeds)
    low_signal = sum(1 for f in feeds if f.get("quality_flag") == "low_signal")
    return JSONResponse(
        {
            "feeds": feeds,
            "count": len(feeds),
            "low_signal_feeds": low_signal,
        }
    )


async def metrics(request: Request):
    from starlette.responses import PlainTextResponse

    from aiwatcher_mcp.database import get_stats
    from aiwatcher_mcp.metrics import format_prometheus
    from aiwatcher_mcp.scheduler import get_scheduler

    stats = await get_stats()
    body = format_prometheus(stats, scheduler_running=get_scheduler().running)
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4")


async def api_trends(request: Request) -> JSONResponse:
    days = int(request.query_params.get("days", "7"))
    from aiwatcher_mcp.trends import get_tag_trends

    trends = await get_tag_trends(days=days)
    return JSONResponse({"days": days, "trends": trends})


async def api_expire_items(request: Request) -> JSONResponse:
    """Manually trigger the retention job."""
    from aiwatcher_mcp.database import expire_old_items

    deleted = await expire_old_items(retention_days=cfg.item_retention_days)
    return JSONResponse({"deleted": deleted, "retention_days": cfg.item_retention_days})


async def api_logs(request: Request) -> JSONResponse:
    from aiwatcher_mcp.logging_utils import get_logs

    return JSONResponse({"logs": get_logs()})


async def api_bundles(request: Request) -> JSONResponse:
    from aiwatcher_mcp.database import get_bundles

    return JSONResponse({"bundles": await get_bundles()})


async def api_create_bundle(request: Request) -> JSONResponse:
    body = await request.json()
    topic = body.get("topic")
    if not topic:
        return JSONResponse({"error": "topic is required"}, status_code=400)

    from aiwatcher_mcp.bundles import elicit_bundle_config
    from aiwatcher_mcp.database import add_bundle

    config = await elicit_bundle_config(topic)
    bundle_id = await add_bundle(
        name=config["name"], topic=topic, system_prompt=config["system_prompt"]
    )
    return JSONResponse(
        {
            "id": bundle_id,
            "name": config["name"],
            "topic": topic,
            "system_prompt": config["system_prompt"],
            "suggested_feeds": config.get("suggested_feeds", []),
        }
    )


async def api_bundle_items(request: Request) -> JSONResponse:
    bundle_id = int(request.path_params["bundle_id"])
    hours = int(request.query_params.get("hours", 24))
    limit = int(request.query_params.get("limit", 50))
    from aiwatcher_mcp.database import get_bundle_recent_items

    items = await get_bundle_recent_items(bundle_id=bundle_id, hours=hours, limit=limit)
    return JSONResponse({"items": items, "count": len(items)})


async def api_bundle_feeds_list(request: Request) -> JSONResponse:
    """GET /api/bundles/{bundle_id}/feeds — list feeds linked to a bundle."""
    bundle_id = int(request.path_params["bundle_id"])
    from aiwatcher_mcp.database import get_bundle_feeds

    feeds = await get_bundle_feeds(bundle_id)
    return JSONResponse({"feeds": feeds, "count": len(feeds)})


async def api_bundle_link_feed(request: Request) -> JSONResponse:
    bundle_id = int(request.path_params["bundle_id"])
    body = await request.json()
    feed_id = body.get("feed_id")
    if not feed_id:
        return JSONResponse({"error": "feed_id is required"}, status_code=400)

    from aiwatcher_mcp.database import link_feed_to_bundle

    await link_feed_to_bundle(feed_id, bundle_id)
    return JSONResponse({"ok": True})


async def api_fleet_apps(request: Request) -> JSONResponse:
    apps = discover_fleet_from_docs()
    return JSONResponse({"apps": [app.model_dump() for app in apps]})


async def api_scrubber_reload(request: Request) -> JSONResponse:
    from aiwatcher_mcp.scrubber import Scrubber

    Scrubber().reload()
    return JSONResponse({"ok": True, "status": "reloaded"})


async def api_wikipedia_poll(request: Request) -> JSONResponse:
    """POST /api/wikipedia/poll — trigger Wikipedia ingestion."""
    from aiwatcher_mcp.wikipedia_ingestion import poll_wikipedia

    results = await poll_wikipedia()
    return JSONResponse({"success": True, "results": results})


async def api_huggingface_poll(request: Request) -> JSONResponse:
    """POST /api/huggingface/poll — trigger Hugging Face ingestion."""
    from aiwatcher_mcp.huggingface_ingestion import poll_huggingface

    results = await poll_huggingface()
    return JSONResponse({"success": True, "results": results, "total_new": sum(results.values())})


def _parse_hf_quants(summary: str | None) -> list[str]:
    if not summary or "Quant variants" not in summary:
        return []
    lines: list[str] = []
    in_block = False
    for line in summary.splitlines():
        if line.startswith("Quant variants"):
            in_block = True
            continue
        if in_block:
            if not line.strip():
                break
            if line.startswith("- "):
                lines.append(line[2:].strip())
            elif line.startswith("Base model:"):
                break
    return lines


_HF_CATEGORY_FEEDS = {
    "drops": {
        "HuggingFace Author Watchlist",
        "HuggingFace Discovery",
        "HuggingFace New Models",
    },
    "papers": {"HuggingFace Daily Papers"},
    "updates": {"HuggingFace Model Updates", "HuggingFace Trending"},
}


async def api_huggingface_dashboard(request: Request) -> JSONResponse:
    """GET /api/huggingface/dashboard — HF watchlist config + clustered model drops."""
    hours = min(int(request.query_params.get("hours", 72)), 168)
    limit = min(int(request.query_params.get("limit", 80)), 200)
    category = (request.query_params.get("category") or "drops").lower()

    from aiwatcher_mcp.config import get_settings
    from aiwatcher_mcp.database import get_feeds, get_recent_items
    from aiwatcher_mcp.huggingface_ingestion import get_effective_hf_watchlist

    cfg = get_settings()
    rows = await get_recent_items(hours=hours, limit=limit, feed_type="huggingface")

    if category != "all":
        allowed = _HF_CATEGORY_FEEDS.get(category, _HF_CATEGORY_FEEDS["drops"])
        rows = [row for row in rows if row.get("feed_name") in allowed]

    items = []
    for row in rows:
        summary = row.get("summary") or ""
        quants = _parse_hf_quants(summary)
        body = summary
        if quants:
            body = summary.split("Quant variants")[0].strip()
        items.append(
            {
                **row,
                "quants": quants,
                "quant_count": len(quants),
                "body": body,
            }
        )

    hf_feeds = [f for f in await get_feeds() if f.get("feed_type") == "huggingface"]

    return JSONResponse(
        {
            "watchlist": get_effective_hf_watchlist(),
            "config": {
                "huggingface_enabled": cfg.huggingface_enabled,
                "poll_interval_minutes": cfg.hf_poll_interval_minutes,
                "discovery_enabled": cfg.hf_discovery_enabled,
                "hf_token_set": bool(cfg.hf_token.strip()),
                "min_weight_bytes": cfg.hf_min_weight_bytes,
            },
            "feeds": hf_feeds,
            "items": items,
            "count": len(items),
            "category": category,
            "hours": hours,
        }
    )


async def api_huggingface_watchlist(request: Request) -> JSONResponse:
    """GET/POST /api/huggingface/watchlist — read or mutate HF author watchlist."""
    from aiwatcher_mcp.config import get_settings
    from aiwatcher_mcp.huggingface_ingestion import (
        get_effective_hf_watchlist,
        set_runtime_hf_watchlist,
    )

    cfg = get_settings()

    if request.method == "GET":
        return JSONResponse(
            {
                "watchlist": get_effective_hf_watchlist(),
                "count": len(get_effective_hf_watchlist()),
                "poll_interval_minutes": cfg.hf_poll_interval_minutes,
                "discovery_enabled": cfg.hf_discovery_enabled,
                "hf_token_set": bool(cfg.hf_token.strip()),
            }
        )

    body = await request.json()
    action = str(body.get("action") or "get").lower()
    authors_raw = body.get("authors") or ""
    parts = [p.strip() for p in str(authors_raw).split(",") if p.strip()]
    current = get_effective_hf_watchlist()

    if action == "set":
        if not parts:
            return JSONResponse({"error": "authors required for set"}, status_code=400)
        set_runtime_hf_watchlist(parts)
    elif action == "add":
        if not parts:
            return JSONResponse({"error": "authors required for add"}, status_code=400)
        merged = list(current)
        for part in parts:
            if part not in merged:
                merged.append(part)
        set_runtime_hf_watchlist(merged)
    elif action == "remove":
        if not parts:
            return JSONResponse({"error": "authors required for remove"}, status_code=400)
        remove_set = {p.lower() for p in parts}
        set_runtime_hf_watchlist([a for a in current if a.lower() not in remove_set])
    else:
        return JSONResponse({"error": f"unknown action: {action}"}, status_code=400)

    updated = get_effective_hf_watchlist()
    return JSONResponse({"action": action, "watchlist": updated, "count": len(updated)})


def _hf_settings_payload(cfg) -> dict:
    return {
        "huggingface_enabled": cfg.huggingface_enabled,
        "hf_token_set": bool(cfg.hf_token.strip()),
        "hf_watchlist": cfg.hf_watchlist,
        "hf_poll_interval_minutes": cfg.hf_poll_interval_minutes,
        "hf_poll_max_per_author": cfg.hf_poll_max_per_author,
        "hf_min_weight_bytes": cfg.hf_min_weight_bytes,
        "hf_include_papers": cfg.hf_include_papers,
        "hf_include_models": cfg.hf_include_models,
        "hf_include_modified": cfg.hf_include_modified,
        "hf_include_trending": cfg.hf_include_trending,
        "hf_discovery_enabled": cfg.hf_discovery_enabled,
        "hf_discovery_limit": cfg.hf_discovery_limit,
        "hf_discovery_max_age_days": cfg.hf_discovery_max_age_days,
    }


async def api_huggingface_settings(request: Request) -> JSONResponse:
    """GET/POST /api/huggingface/settings — structured HF config for the webapp Settings page."""
    from pathlib import Path

    import dotenv

    from aiwatcher_mcp.config import get_settings
    from aiwatcher_mcp.huggingface_ingestion import set_runtime_hf_watchlist

    cfg = get_settings()

    if request.method == "GET":
        return JSONResponse(_hf_settings_payload(cfg))

    body = await request.json()
    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()

    bool_keys = {
        "huggingface_enabled": "HUGGINGFACE_ENABLED",
        "hf_include_papers": "HF_INCLUDE_PAPERS",
        "hf_include_models": "HF_INCLUDE_MODELS",
        "hf_include_modified": "HF_INCLUDE_MODIFIED",
        "hf_include_trending": "HF_INCLUDE_TRENDING",
        "hf_discovery_enabled": "HF_DISCOVERY_ENABLED",
    }
    int_keys = {
        "hf_poll_interval_minutes": "HF_POLL_INTERVAL_MINUTES",
        "hf_poll_max_per_author": "HF_POLL_MAX_PER_AUTHOR",
        "hf_min_weight_bytes": "HF_MIN_WEIGHT_BYTES",
        "hf_discovery_limit": "HF_DISCOVERY_LIMIT",
        "hf_discovery_max_age_days": "HF_DISCOVERY_MAX_AGE_DAYS",
    }
    str_keys = {
        "hf_watchlist": "HF_WATCHLIST",
    }

    for field, env_key in bool_keys.items():
        if field in body:
            dotenv.set_key(env_path, env_key, "true" if body[field] else "false")

    for field, env_key in int_keys.items():
        if field in body:
            dotenv.set_key(env_path, env_key, str(int(body[field])))

    for field, env_key in str_keys.items():
        if field in body:
            dotenv.set_key(env_path, env_key, str(body[field] or ""))

    token = str(body.get("hf_token") or "").strip()
    if token and token != "***REDACTED***":
        dotenv.set_key(env_path, "HF_TOKEN", token)

    import aiwatcher_mcp.config as cfg_mod

    cfg_mod._settings = None
    set_runtime_hf_watchlist(None)
    new_cfg = cfg_mod.get_settings()

    return JSONResponse({"ok": True, "settings": _hf_settings_payload(new_cfg)})


async def api_pipeline_liveness(request: Request) -> JSONResponse:
    """Pipeline health: stale arXiv feeds, wrong arxiv-mcp URL, upstream reachability."""
    stale_hours = int(request.query_params.get("stale_hours", 48))
    from aiwatcher_mcp.pipeline_liveness import check_pipeline_liveness

    return JSONResponse(await check_pipeline_liveness(stale_hours=stale_hours))


async def api_skills(request: Request) -> JSONResponse:
    """GET /api/skills — list available skill directories."""
    skills_dir = Path(__file__).resolve().parent / "skills"
    if not skills_dir.is_dir():
        return JSONResponse({"skills": []})
    skills: list[dict[str, str]] = []
    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir():
            skill_md = entry / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
            skills.append({"name": entry.name, "content": content[:5000]})
    return JSONResponse({"skills": skills, "count": len(skills)})


async def api_llm_discover(request: Request) -> JSONResponse:
    """GET /api/llm/discover — probe local provider availability."""
    import httpx

    result: dict[str, bool] = {}
    for name, url, _tag in [
        ("ollama", "http://localhost:11434/api/tags", ""),
        ("lmstudio", "http://localhost:1234/v1/models", ""),
    ]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(url)
                result[name] = r.status_code < 400
        except Exception:
            result[name] = False
    return JSONResponse({"providers": result})


async def api_help(request: Request) -> JSONResponse:
    from aiwatcher_mcp.help_content import get_help

    return JSONResponse(get_help(None))


async def api_help_topic(request: Request) -> JSONResponse:
    from aiwatcher_mcp.help_content import get_help

    topic = request.path_params.get("topic", "")
    result = get_help(topic)
    if not result.get("success"):
        return JSONResponse(result, status_code=404)
    return JSONResponse(result)


async def api_diagnostics(request: Request) -> JSONResponse:
    try:
        import psutil

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
    except ImportError:
        cpu = mem = disk = None
    return JSONResponse(
        {
            "success": True,
            "backend": {"port": cfg.backend_port, "status": "running"},
            "system": {"cpu_percent": cpu, "memory_percent": mem, "disk_percent": disk},
            "tools": {"total": 0},
            "cua_status": {"tesseract_available": False, "window_found": False},
        }
    )


async def api_inbox_ingest(request: Request) -> JSONResponse:
    """Ingest markdown analysis into the Inbox feed.

    Body:
        {"title": str, "content": str, "source"?: str, "tags"?: str,
         "urgency_hint"?: float}
    Wraps inbox.ingest_markdown; lands in the 'Opencode Analysis' feed.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    if not title or not content:
        return JSONResponse({"error": "title and content are required"}, status_code=400)

    urgency_hint = body.get("urgency_hint")
    if urgency_hint is not None:
        try:
            urgency_hint = float(urgency_hint)
        except (TypeError, ValueError):
            return JSONResponse({"error": "urgency_hint must be a number"}, status_code=400)

    tags_str = body.get("tags", "")
    tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    from aiwatcher_mcp.inbox import ingest_markdown

    result = await ingest_markdown(
        title=title,
        content=content,
        source=str(body.get("source", "opencode")),
        tags=tag_list,
        urgency_hint=urgency_hint,
    )
    return JSONResponse(result)


async def api_inbox_list(request: Request) -> JSONResponse:
    """List pending inbox files and recently ingested DB items."""
    from aiwatcher_mcp.inbox import list_inbox

    result = await list_inbox()
    return JSONResponse(result)


async def api_fleet_ingest(request: Request) -> JSONResponse:
    """Push a structured event from another fleet member into the items table.

    Producer interface for tools like arxiv-mcp's code-hunt scanner. Body:
        {"title": str, "summary"?: str, "source"?: str, "url"?: str, "urgency_hint"?: float}
    Wraps ingest_fleet_event; lands in the synthetic 'Fleet Events' feed.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "title is required"}, status_code=400)

    urgency_hint = body.get("urgency_hint")
    if urgency_hint is not None:
        try:
            urgency_hint = float(urgency_hint)
        except (TypeError, ValueError):
            return JSONResponse({"error": "urgency_hint must be a number"}, status_code=400)

    from aiwatcher_mcp.fleet_events import ingest_fleet_event

    result = await ingest_fleet_event(
        title=title,
        summary=str(body.get("summary") or ""),
        source=str(body.get("source") or "fleet"),
        url=str(body.get("url") or ""),
        urgency_hint=urgency_hint,
    )
    return JSONResponse(result)


async def api_bundle_health(request: Request) -> JSONResponse:
    bundle_id = int(request.path_params["bundle_id"])
    from aiwatcher_mcp.database import get_bundle_stats

    stats = await get_bundle_stats(bundle_id)
    if stats is None:
        return JSONResponse({"error": f"Bundle {bundle_id} not found"}, status_code=404)
    return JSONResponse(stats)


async def api_scheduler(request: Request) -> JSONResponse:
    """GET /api/scheduler — APScheduler job list and intervals for the webapp."""
    from aiwatcher_mcp.scheduler import get_scheduler_status

    return JSONResponse(get_scheduler_status())


async def api_llm_providers(request: Request) -> JSONResponse:
    """GET /api/llm/providers — return available Ollama models."""
    import httpx

    models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://localhost:11434/api/tags")
            data = r.json()
            for m in data.get("models", []):
                name = m.get("name", "")
                if name:
                    models.append(name)
    except Exception:
        pass
    return JSONResponse({"providers": [{"name": "ollama", "models": models}]})


async def api_llm_health(request: Request) -> JSONResponse:
    """GET /api/llm/health — probe LLM providers, show recovery readiness."""
    from aiwatcher_mcp.llm_watchdog import llm_health as check_llm

    status = await check_llm()
    http_code = 200 if status.get("any_ok") else 503
    return JSONResponse(status, status_code=http_code)


CHAT_HISTORY: dict[str, list[dict]] = {}  # session_id → messages

# Load aiwatcher-expert skill for chat preprompt
_AIWATCHER_SKILL: str | None = None
_skill_path = Path(__file__).resolve().parent / "skills" / "aiwatcher-expert" / "SKILL.md"
if _skill_path.exists():
    _AIWATCHER_SKILL = _skill_path.read_text(encoding="utf-8")
    log.info("Loaded aiwatcher-expert skill (%d chars)", len(_AIWATCHER_SKILL))

PERSONALITIES: dict[str, str] = {
    "professional": "You are a helpful AI assistant. Respond professionally and concisely.",
    "mentor": "You are a supportive mentor who explains concepts patiently and encourages learning.",
    "sarcastic": "You respond with dry wit and sarcasm. Keep it sharp but not mean.",
    "pirate": "Arr, ye be talkin' to a pirate AI! Speak like a salty sea captain, use nautical terms, and keep it fun.",
    "enthusiast": "You are an over-the-top enthusiast! Everything is exciting and amazing! Use lots of energy and emojis!",
}


def _system_prompt(personality: str | None, context: str | None) -> str:
    base = PERSONALITIES.get(personality or "", PERSONALITIES["professional"])
    if _AIWATCHER_SKILL:
        base += f"\n\n## System Expert Context\n{_AIWATCHER_SKILL[:3000]}"
    if context:
        base += f"\n\n## User Context\n{context[:2000]}"
    return base


async def api_llm_chat(request: Request) -> JSONResponse:
    """POST /api/llm/chat — multi-provider chat with personality support."""
    import httpx

    body = await request.json()
    provider = body.get("provider", cfg.llm_provider or "ollama")
    model = body.get("model", body.get("distillation_model", cfg.distillation_model or "gemma3:1b"))
    messages = body.get("messages", [])
    prompt = body.get("prompt", "")
    personality = body.get("personality", "professional")
    context = body.get("context", "")
    base_url = body.get("base_url", cfg.llm_base_url or "")

    # Build message list
    system = _system_prompt(personality if personality != "professional" else None, context)
    chat_messages: list[dict] = []
    if system:
        chat_messages.append({"role": "system", "content": system})
    chat_messages.extend(messages)
    if prompt:
        chat_messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if provider == "ollama":
                url = (base_url.rstrip("/") if base_url else "http://localhost:11434") + "/api/chat"
                payload = {"model": model, "messages": chat_messages, "stream": False}
                r = await client.post(url, json=payload)
                data = r.json()
                reply = data.get("message", {}).get("content", "")
            elif provider == "anthropic":
                key = cfg.anthropic_api_key or ""
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }
                anthy_messages = [m for m in chat_messages if m["role"] != "system"]
                system_text = next(
                    (m["content"] for m in chat_messages if m["role"] == "system"), None
                )
                payload: dict = {"model": model, "messages": anthy_messages, "max_tokens": 1024}
                if system_text:
                    payload["system"] = system_text
                r = await client.post(url, json=payload, headers=headers)
                data = r.json()
                reply = data.get("content", [{}])[0].get("text", "")
            else:
                # OpenAI-compatible (lmstudio, openai, deepseek)
                key = ""
                if provider == "openai":
                    key = cfg.openai_api_key or ""
                elif provider == "deepseek":
                    key = cfg.deepseek_api_key or ""
                if not base_url:
                    if provider == "openai":
                        base_url = "https://api.openai.com/v1"
                    elif provider == "deepseek":
                        base_url = "https://api.deepseek.com/v1"
                    else:
                        base_url = "http://localhost:1234/v1"
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                url = base_url.rstrip("/") + "/chat/completions"
                payload = {
                    "model": model,
                    "messages": chat_messages,
                    "max_tokens": 1024,
                    "stream": False,
                }
                r = await client.post(url, json=payload, headers=headers)
                data = r.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            return JSONResponse({"reply": reply, "model": model, "provider": provider})

    except Exception as e:
        log.error("LLM chat failed: %s", e)
        return JSONResponse({"reply": f"Error: {e}", "model": model, "provider": provider})


async def api_llm_chat_stream(request: Request) -> StreamingResponse:
    """POST /api/llm/chat/stream — streaming chat via SSE (Ollama + OpenAI-compat)."""
    import httpx

    body = await request.json()
    provider = body.get("provider", cfg.llm_provider or "ollama")
    model = body.get("model", cfg.distillation_model or "gemma3:1b")
    messages = body.get("messages", [])
    prompt = body.get("prompt", "")
    personality = body.get("personality", "professional")
    context = body.get("context", "")
    base_url = body.get("base_url", cfg.llm_base_url or "")

    # Resolve base URL before the closure to avoid shadowing issues
    if not base_url:
        if provider == "openai":
            base_url = "https://api.openai.com/v1"
        elif provider == "deepseek":
            base_url = "https://api.deepseek.com/v1"
        elif provider == "ollama":
            base_url = "http://localhost:11434"
        else:
            base_url = "http://localhost:1234/v1"

    system = _system_prompt(personality if personality != "professional" else None, context)
    chat_messages: list[dict] = []
    if system:
        chat_messages.append({"role": "system", "content": system})
    chat_messages.extend(messages)
    if prompt:
        chat_messages.append({"role": "user", "content": prompt})

    async def _stream():
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                if provider == "ollama":
                    url = base_url.rstrip("/") + "/api/chat"
                    payload = {"model": model, "messages": chat_messages, "stream": True}
                    async with client.stream("POST", url, json=payload) as resp:
                        async for line in resp.aiter_lines():
                            if not line.strip():
                                continue
                            import json as _j

                            try:
                                chunk = _j.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield f"data: {_j.dumps({'token': content})}\n\n"
                            except _j.JSONDecodeError:
                                pass
                        yield "data: [DONE]\n\n"
                else:
                    _ak = ""
                    if provider == "openai":
                        _ak = cfg.openai_api_key or ""
                    elif provider == "deepseek":
                        _ak = cfg.deepseek_api_key or ""
                    _stream_url = base_url.rstrip("/") + "/chat/completions"
                    _headers = {"Authorization": f"Bearer {_ak}"} if _ak else {}
                    payload = {
                        "model": model,
                        "messages": chat_messages,
                        "max_tokens": 1024,
                        "stream": True,
                    }
                    async with client.stream(
                        "POST", _stream_url, json=payload, headers=_headers
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    yield "data: [DONE]\n\n"
                                    return
                                import json as _j

                                try:
                                    chunk = _j.loads(data_str)
                                    content = (
                                        chunk.get("choices", [{}])[0]
                                        .get("delta", {})
                                        .get("content", "")
                                    )
                                    if content:
                                        yield f"data: {_j.dumps({'token': content})}\n\n"
                                except _j.JSONDecodeError:
                                    pass
        except Exception as e:
            yield f"data: {_j.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


async def api_chat_history(request: Request) -> JSONResponse:
    """GET/POST /api/chat/history — list or save chat sessions."""
    if request.method == "POST":
        body = await request.json()
        session_id = body.get("session_id", "default")
        messages = body.get("messages", [])
        CHAT_HISTORY[session_id] = messages
        return JSONResponse({"ok": True, "session_id": session_id, "count": len(messages)})
    session_id = request.query_params.get("session_id", "default")
    messages = CHAT_HISTORY.get(session_id, [])
    return JSONResponse({"session_id": session_id, "messages": messages, "count": len(messages)})


async def api_shutdown(request: Request) -> JSONResponse:
    """Graceful shutdown endpoint — called by start.ps1 before hard kill."""
    global _SHUTTING_DOWN
    _SHUTTING_DOWN = True
    import os

    log.info("Graceful shutdown requested via /api/shutdown")

    async def _die():
        import asyncio as _asyncio

        await _asyncio.sleep(0.5)
        os._exit(0)

    import asyncio as _asyncio

    _asyncio.ensure_future(_die())
    return JSONResponse({"success": True, "message": "Shutting down"})


async def api_opml_import(request: Request) -> JSONResponse:
    body = await request.json()
    opml_xml = body.get("opml_xml", "")
    if not opml_xml:
        return JSONResponse({"error": "opml_xml is required"}, status_code=400)

    from aiwatcher_mcp.opml import import_feeds_from_opml

    result = await import_feeds_from_opml(opml_xml)
    return JSONResponse(result)


# ── App ─────────────────────────────────────────────────────────────────────────

_app = FastAPI(
    lifespan=lifespan,
    title="AIWatcher MCP",
    version=cfg.server_version,
    description="AI news ingestion, distillation, and alert system — REST API",
)

_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:10946",
        "http://localhost:10946",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_origin_regex=r"https?://(?:[a-zA-Z0-9-]+\.ts\.net|.*?\.tail-[a-f0-9]+\.ts\.net|tauri\.localhost|localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|100\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?$|^tauri://localhost$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-AIWatcher-Key", "Authorization"],
)

# ── Route registration ─────────────────────────────────────────────────────────

_app.add_api_route("/health", health, methods=["GET"])
_app.add_api_route("/api/health", health, methods=["GET"])
_app.add_api_route("/metrics", metrics, methods=["GET"])
_app.add_api_route("/api/capabilities", capabilities, methods=["GET"])
_app.add_api_route("/api/stats", api_stats, methods=["GET"])
_app.add_api_route("/api/feeds", api_feeds, methods=["GET"])
_app.add_api_route("/api/feeds/{feed_id:int}/toggle", api_toggle_feed, methods=["POST"])
_app.add_api_route("/api/feeds/add", api_add_feed, methods=["POST"])
_app.add_api_route("/api/morning-news", api_morning_news, methods=["GET"])
_app.add_api_route("/api/items", api_items, methods=["GET"])
_app.add_api_route("/api/poll", api_poll, methods=["POST"])
_app.add_api_route("/api/distill", api_distill, methods=["POST"])
_app.add_api_route("/api/alerts/check", api_check_alerts, methods=["POST"])
_app.add_api_route("/api/digest/preview", api_digest_preview, methods=["GET"])
_app.add_api_route("/api/digest/html", api_digest_html, methods=["GET"])
_app.add_api_route("/api/digest/send", api_send_digest, methods=["POST"])
_app.add_api_route("/api/env", api_get_env, methods=["GET"])
_app.add_api_route("/api/env", api_update_env, methods=["POST"])
_app.add_api_route("/api/search", api_search, methods=["GET"])
_app.add_api_route("/api/digest/history", api_digest_history, methods=["GET"])
_app.add_api_route("/api/config/reload", api_reload_config, methods=["POST"])
_app.add_api_route("/api/feeds/health", api_feed_health, methods=["GET"])
_app.add_api_route("/api/trends", api_trends, methods=["GET"])
_app.add_api_route("/api/items/expire", api_expire_items, methods=["POST"])
_app.add_api_route("/api/logs", api_logs, methods=["GET"])
_app.add_api_route("/api/llm/models", api_llm_models, methods=["GET"])
_app.add_api_route("/api/llm/discover", api_llm_discover, methods=["GET"])
_app.add_api_route("/api/skills", api_skills, methods=["GET"])
_app.add_api_route("/api/llm/chat", api_llm_chat, methods=["POST"])
_app.add_api_route("/api/llm/chat/stream", api_llm_chat_stream, methods=["POST"])
_app.add_api_route("/api/chat/history", api_chat_history, methods=["GET", "POST"])
_app.add_api_route("/api/test-llm", api_test_llm, methods=["POST"])
_app.add_api_route("/api/bundles", api_bundles, methods=["GET"])
_app.add_api_route("/api/bundles/create", api_create_bundle, methods=["POST"])
_app.add_api_route("/api/bundles/{bundle_id:int}/items", api_bundle_items, methods=["GET"])
_app.add_api_route("/api/bundles/{bundle_id:int}/feeds", api_bundle_feeds_list, methods=["GET"])
_app.add_api_route("/api/bundles/{bundle_id:int}/feeds", api_bundle_link_feed, methods=["POST"])
_app.add_api_route("/api/bundles/{bundle_id:int}/health", api_bundle_health, methods=["GET"])
_app.add_api_route("/api/scheduler", api_scheduler, methods=["GET"])
_app.add_api_route("/api/opml/import", api_opml_import, methods=["POST"])
_app.add_api_route("/api/test/speak", api_test_speak, methods=["POST"])
_app.add_api_route("/api/shutdown", api_shutdown, methods=["POST"])
_app.add_api_route("/api/test/discover-sources", api_test_discover_sources, methods=["POST"])
_app.add_api_route("/api/fleet/apps", api_fleet_apps, methods=["GET"])
_app.add_api_route("/api/inbox/ingest", api_inbox_ingest, methods=["POST"])
_app.add_api_route("/api/inbox/list", api_inbox_list, methods=["GET"])
_app.add_api_route("/api/fleet/ingest", api_fleet_ingest, methods=["POST"])
_app.add_api_route("/api/wikipedia/poll", api_wikipedia_poll, methods=["POST"])
_app.add_api_route("/api/huggingface/poll", api_huggingface_poll, methods=["POST"])
_app.add_api_route("/api/huggingface/dashboard", api_huggingface_dashboard, methods=["GET"])
_app.add_api_route("/api/huggingface/watchlist", api_huggingface_watchlist, methods=["GET", "POST"])
_app.add_api_route("/api/huggingface/settings", api_huggingface_settings, methods=["GET", "POST"])
_app.add_api_route("/api/pipeline/liveness", api_pipeline_liveness, methods=["GET"])
_app.add_api_route("/api/help", api_help, methods=["GET"])
_app.add_api_route("/api/help/{topic}", api_help_topic, methods=["GET"])
_app.add_api_route("/api/scrubber/reload", api_scrubber_reload, methods=["POST"])
_app.add_api_route("/api/llm/providers", api_llm_providers, methods=["GET"])
_app.add_api_route("/api/llm/health", api_llm_health, methods=["GET"])
_app.add_api_route("/api/v1/diagnostics", api_diagnostics, methods=["GET"])
_app.mount("/mcp", app=_mcp_http_app, name="mcp")

# Wrap with API key auth (outer ASGI middleware)
app: ASGIApp = ApiKeyMiddleware(_app)


def run() -> None:
    import uvicorn

    from aiwatcher_mcp.logging_utils import setup_ui_logging

    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)
    setup_ui_logging(level=log_level)

    uvicorn.run(
        "aiwatcher_mcp.api:app",
        host="0.0.0.0",
        port=cfg.backend_port,
        reload=False,
        log_level=cfg.log_level.lower(),
    )


if __name__ == "__main__":
    run()
