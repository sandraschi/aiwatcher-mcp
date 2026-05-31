"""Optional API key gate for the Starlette REST surface."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def _is_public_path(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    if path in ("/health", "/api/health"):
        return True
    return path == "/mcp" or path.startswith("/mcp/")


class ApiKeyMiddleware:
    """Require X-AIWatcher-Key or Authorization: Bearer when AIWATCHER_API_KEY is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        from aiwatcher_mcp.config import get_settings

        api_key = (get_settings().api_key or "").strip() or None
        if scope["type"] != "http" or not api_key:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path
        if _is_public_path(path, request.method):
            await self.app(scope, receive, send)
            return

        provided = request.headers.get("x-aiwatcher-key", "").strip()
        if not provided:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip()

        if provided != api_key:
            response = JSONResponse(
                {"error": "Unauthorized", "detail": "Invalid or missing API key"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
