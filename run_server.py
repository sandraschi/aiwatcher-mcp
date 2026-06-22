"""PyInstaller entrypoint for aiwatcher-mcp HTTP sidecar."""

from __future__ import annotations

import _strptime  # noqa: F401 -- PyInstaller must bundle this eagerly
import mcp.types  # noqa: F401 -- must be imported before fastmcp touches it
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
else:
    base = Path(__file__).resolve().parent
if str(base / "src") not in sys.path:
    sys.path.insert(0, str(base / "src"))

os.environ.setdefault("MCP_TRANSPORT", "http")

if __name__ == "__main__":
    import uvicorn
    from aiwatcher_mcp.api import app

    host = os.environ.get("AIWATCHER_HOST", "127.0.0.1")
    port = int(os.environ.get("AIWATCHER_PORT", os.environ.get("MCP_PORT", "10946")))
    log_level = os.environ.get("AIWATCHER_LOG_LEVEL", "info")
    uvicorn.run(app, host=host, port=port, log_level=log_level)

