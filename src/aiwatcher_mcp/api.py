"""
Starlette ASGI backend — REST API on port 10946.
Mounts FastMCP at /mcp, exposes /api/* for the React webapp.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Mount, Route

from aiwatcher_mcp.config import get_settings
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
    from aiwatcher_mcp.scheduler import start_scheduler, stop_scheduler
    log.info("aiwatcher-mcp backend starting on port %d", cfg.backend_port)
    await init_db()
    # Shallow DB probe (startup pattern from fastmcp-3.2-startup-probes.md)
    from aiwatcher_mcp.database import get_stats
    stats = await get_stats()
    log.info("DB probe OK — %d feeds, %d total items", stats["active_feeds"], stats["total_items"])
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
        "server": {"name": cfg.server_name, "version": "0.1.0", "fastmcp": "3.2+"},
        "tool_surface": {
            "total": 8,
            "portmanteau_count": 0,
            "atomic_count": 8,
            "atomic_tools": [
                "poll_feeds", "distill_pending", "check_alerts",
                "generate_digest", "send_digest_now", "get_top_items",
                "get_feeds_list", "add_feed",
            ],
        },
        "features": {
            "sampling": False,
            "agentic_workflows": False,
            "prompts": True,
            "resources": True,
            "skills": False,
            "scheduling": True,
            "robofang_integration": cfg.robofang_enabled,
            "email_delivery": cfg.email_enabled,
            "calibre_integration": cfg.calibre_enabled,
        },
        "integrations": {
            "robofang": cfg.robofang_enabled,
            "email_mcp": bool(cfg.email_mcp_url),
            "calibre_mcp": cfg.calibre_enabled,
            "speechops": bool(cfg.speechops_http_url),
        },
        "runtime": {"transport": "dual", "surface_mode": "atomic"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))
    uvicorn.run(
        "aiwatcher_mcp.api:app",
        host="0.0.0.0",
        port=cfg.backend_port,
        reload=False,
        log_level=cfg.log_level.lower(),
    )


if __name__ == "__main__":
    run()
