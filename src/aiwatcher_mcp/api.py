"""
Starlette ASGI backend — REST API on port 10946.
Mounts FastMCP at /mcp, exposes /api/* for the React webapp.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.fleet import discover_fleet_from_docs
from aiwatcher_mcp.server import mcp

log = logging.getLogger(__name__)
cfg = get_settings()

# mcp.http_app() is safe at module level — uvicorn loads this module within its
# own event loop context. The MCP server's own lifespan (_mcp_db_lifespan in
# server.py) handles FastMCP internals; the Starlette lifespan below handles
# the DB init and scheduler independently. Do NOT nest lifespan contexts.
_mcp_http_app = mcp.http_app()


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    from aiwatcher_mcp.database import init_db
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler, validate_distillation_model
    log.info("aiwatcher-mcp backend starting on port %d", cfg.backend_port)
    await init_db()
    # Shallow DB probe
    from aiwatcher_mcp.database import get_stats
    stats = await get_stats()
    log.info("DB probe OK — %d feeds, %d total items", stats["active_feeds"], stats["total_items"])
    # LLM provider validation (non-blocking — logs warning if unreachable)
    await validate_distillation_model()
    start_scheduler()
    yield
    stop_scheduler()
    log.info("aiwatcher-mcp backend shutdown")


# ── API handlers ───────────────────────────────────────────────────────────────

async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "aiwatcher-mcp", "version": "0.1.0"})


async def capabilities(request: Request) -> JSONResponse:
    """Mandatory /api/capabilities — WEBAPP_STANDARDS.md §1.4"""
    return JSONResponse({
        "status": "ok",
        "server": {
            "name": cfg.server_name,
            "version": cfg.server_version,
            "fastmcp": "3.2+",
            "provider": cfg.llm_provider
        },
        "tool_surface": {
            "total": 11,
            "portmanteau_count": 0,
            "atomic_count": 11,
            "atomic_tools": [
                "poll_feeds", "distill_pending", "check_alerts",
                "generate_digest", "send_digest_now", "get_top_items",
                "get_feeds_list", "add_feed",
                "get_bundles_list", "create_bundle_from_topic", "link_feed_to_bundle"
            ],
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
    })


async def api_stats(request: Request) -> JSONResponse:
    from aiwatcher_mcp.database import get_stats
    return JSONResponse(await get_stats())


async def api_feeds(request: Request) -> JSONResponse:
    from aiwatcher_mcp.database import get_feeds
    return JSONResponse({"feeds": await get_feeds()})


async def api_items(request: Request) -> JSONResponse:
    hours = int(request.query_params.get("hours", 24))
    limit = int(request.query_params.get("limit", 50))
    from aiwatcher_mcp.database import get_recent_items
    items = await get_recent_items(hours=min(hours, 168), limit=min(limit, 200))
    return JSONResponse({"items": items, "count": len(items)})


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
    digest = await generate_digest(hours=24)
    success = await send_digest(digest)
    return JSONResponse({"sent": success})


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
    return JSONResponse(env_dict)


async def api_update_env(request: Request) -> JSONResponse:
    body = await request.json()
    from pathlib import Path

    import dotenv
    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()
    
    for key, value in body.items():
        if value is not None:
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
                timeout=15
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
    log.info("Config reloaded from .env — provider=%s model=%s", new_cfg.llm_provider, new_cfg.distillation_model)
    return JSONResponse({
        "ok": True,
        "llm_provider": new_cfg.llm_provider,
        "distillation_model": new_cfg.distillation_model,
        "alert_threshold": new_cfg.alert_threshold,
        "item_retention_days": new_cfg.item_retention_days,
    })


async def api_feed_health(request: Request) -> JSONResponse:
    """Return feeds sorted by health — degraded/disabled feeds first."""
    from aiwatcher_mcp.database import get_db
    async with get_db() as db, db.execute(
        """SELECT id, name, url, feed_type, enabled, last_fetched,
                  consecutive_failures, last_error, created_at
           FROM feeds
           ORDER BY consecutive_failures DESC, name"""
    ) as cur:
        feeds = [dict(r) for r in await cur.fetchall()]
    return JSONResponse({"feeds": feeds, "count": len(feeds)})


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
        name=config["name"],
        topic=topic,
        system_prompt=config["system_prompt"]
    )
    return JSONResponse({
        "id": bundle_id, 
        "name": config["name"], 
        "topic": topic,
        "system_prompt": config["system_prompt"],
        "suggested_feeds": config.get("suggested_feeds", [])
    })


async def api_bundle_items(request: Request) -> JSONResponse:
    bundle_id = int(request.path_params["bundle_id"])
    hours = int(request.query_params.get("hours", 24))
    limit = int(request.query_params.get("limit", 50))
    from aiwatcher_mcp.database import get_bundle_recent_items
    items = await get_bundle_recent_items(bundle_id=bundle_id, hours=hours, limit=limit)
    return JSONResponse({"items": items, "count": len(items)})


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


async def api_bundle_health(request: Request) -> JSONResponse:
    bundle_id = int(request.path_params["bundle_id"])
    from aiwatcher_mcp.database import get_bundle_stats
    stats = await get_bundle_stats(bundle_id)
    if stats is None:
        return JSONResponse({"error": f"Bundle {bundle_id} not found"}, status_code=404)
    return JSONResponse(stats)


async def api_opml_import(request: Request) -> JSONResponse:
    body = await request.json()
    opml_xml = body.get("opml_xml", "")
    if not opml_xml:
        return JSONResponse({"error": "opml_xml is required"}, status_code=400)

    import xml.etree.ElementTree as ET

    from aiwatcher_mcp.database import get_db

    root = ET.fromstring(opml_xml)
    imported = []

    for outline in root.iter("outline"):
        xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
        title = outline.get("title") or outline.get("text") or "OPML Import"
        if not xml_url:
            continue
        async with get_db() as db:
            try:
                cur = await db.execute(
                    "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                    (title, xml_url, "rss"),
                )
                await db.commit()
                imported.append({"id": cur.lastrowid, "name": title, "url": xml_url})
            except Exception:
                pass

    return JSONResponse({"imported": imported, "count": len(imported)})


# ── Routes ─────────────────────────────────────────────────────────────────────

routes = [
    Route("/health", health),
    Route("/api/health", health),
    Route("/api/capabilities", capabilities),
    Route("/api/stats", api_stats),
    Route("/api/feeds", api_feeds),
    Route("/api/feeds/{feed_id:int}/toggle", api_toggle_feed, methods=["POST"]),
    Route("/api/feeds/add", api_add_feed, methods=["POST"]),
    Route("/api/items", api_items),
    Route("/api/poll", api_poll, methods=["POST"]),
    Route("/api/distill", api_distill, methods=["POST"]),
    Route("/api/alerts/check", api_check_alerts, methods=["POST"]),
    Route("/api/digest/preview", api_digest_preview),
    Route("/api/digest/html", api_digest_html),
    Route("/api/digest/send", api_send_digest, methods=["POST"]),
    Route("/api/env", api_get_env),
    Route("/api/env", api_update_env, methods=["POST"]),
    Route("/api/search", api_search),
    Route("/api/digest/history", api_digest_history),
    Route("/api/config/reload", api_reload_config, methods=["POST"]),
    Route("/api/feeds/health", api_feed_health),
    Route("/api/items/expire", api_expire_items, methods=["POST"]),
    Route("/api/logs", api_logs),
    Route("/api/test-llm", api_test_llm, methods=["POST"]),
    Route("/api/bundles", api_bundles),
    Route("/api/bundles/create", api_create_bundle, methods=["POST"]),
    Route("/api/bundles/{bundle_id:int}/items", api_bundle_items),
    Route("/api/bundles/{bundle_id:int}/feeds", api_bundle_link_feed, methods=["POST"]),
    Route("/api/bundles/{bundle_id:int}/health", api_bundle_health),
    Route("/api/opml/import", api_opml_import, methods=["POST"]),
    Route("/api/test/speak", api_test_speak, methods=["POST"]),
    Route("/api/test/discover-sources", api_test_discover_sources, methods=["POST"]),
    Route("/api/fleet/apps", api_fleet_apps),
    Mount("/mcp", app=_mcp_http_app),
]

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
