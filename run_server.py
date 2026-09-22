"""PyInstaller entrypoint for aiwatcher-mcp HTTP sidecar."""

from __future__ import annotations

import os
import sys
from pathlib import Path

base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
if str(base / "src") not in sys.path:
    sys.path.insert(0, str(base / "src"))

os.environ.setdefault("MCP_TRANSPORT", "http")

if __name__ == "__main__":
    import uvicorn

    from aiwatcher_mcp.api import app

    # native/src/backend.rs sets AIWATCHER_MCP_HOST/_PORT (ENV_HOST/ENV_PORT) when
    # spawning the Tauri sidecar — those names must come first, not the bare
    # AIWATCHER_HOST/_PORT this previously only checked. Dormant today only because
    # BACKEND_PORT in backend.rs and the "10946" default below happen to agree;
    # found while verifying data persistence for BUG-046.
    host = os.environ.get("AIWATCHER_MCP_HOST", os.environ.get("AIWATCHER_HOST", "127.0.0.1"))
    port = int(
        os.environ.get(
            "AIWATCHER_MCP_PORT",
            os.environ.get("AIWATCHER_PORT", os.environ.get("MCP_PORT", "10946")),
        )
    )
    log_level = os.environ.get("AIWATCHER_LOG_LEVEL", "info")
    uvicorn.run(app, host=host, port=port, log_level=log_level)


# PyInstaller lazy-import traps (fleet Tauri protocol)
import _datetime  # noqa: E402, F401
import _strptime  # noqa: E402, F401
