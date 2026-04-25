"""
aiwatcher_mcp — AI news ingestion, distillation, and alert system.

FastMCP 3.2 fleet server, SOTA-aligned (fleet standard v12.1).
Backend: Starlette ASGI on port 10946.
Frontend: Vite/React on port 10947.

Integration points:
  - robofang: publishes BREAKING alerts to robofang Council via HTTP POST
  - email-mcp: optional delivery of HTML digest email (Sandra + Steve)
  - calibre-mcp: optional ingest of distilled articles as ebooks
  - speechops: 5am TTS wake-up for CRITICAL events
"""

from aiwatcher_mcp._version import __version__
from aiwatcher_mcp.server import main

__all__ = ["__version__", "main"]
