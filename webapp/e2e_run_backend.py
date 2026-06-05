"""Start Starlette backend for Playwright e2e (loads .env, port 10946)."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Fast e2e startup: avoid blocking local LLM probes from developer .env
os.environ["AIWATCHER_E2E"] = "1"
os.environ["LLM_PROVIDER"] = "anthropic"
os.environ.setdefault("ANTHROPIC_API_KEY", "")
# E2E backend only — avoid blocking poll on external arxiv-mcp / RSS timeouts
os.environ["ARXIV_ENABLED"] = "false"
os.environ["READLY_ENABLED"] = "false"
os.environ["GMAIL_ENABLED"] = "false"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "aiwatcher_mcp.api:app",
        host="127.0.0.1",
        port=10946,
        log_level="warning",
    )
