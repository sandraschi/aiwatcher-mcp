"""Help topics for aiwatcher_help MCP tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_TOPICS: dict[str, str] = {
    "overview": "overview",
    "fleet_pipeline": "FLEET_PIPELINE.md",
    "fleet": "FLEET_PIPELINE.md",
    "api_keys": "FLEET_PIPELINE.md",
    "integrations": "FLEET_PIPELINE.md",
    "intel_hub": "overview",
    "alerts": "overview",
    "scoring": "overview",
}


def _repo_docs() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs"
        if candidate.is_dir():
            return candidate
    return here.parents[2] / "docs"


def _read_doc(name: str) -> str:
    path = _repo_docs() / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"(missing doc: {name})"


def _overview() -> str:
    return """# aiwatcher-mcp help

AI news distillation, urgency scoring, fleet ingest, and pipeline liveness.

## Topics (`aiwatcher_help(topic="...")`)

| topic | Content |
|-------|---------|
| `fleet_pipeline` | arxiv + vla ingest, liveness, interest bundles |
| `api_keys` | AIWATCHER_API_KEY vs Anthropic/DeepSeek |
| `integrations` | robofang, speechops, email, calibre, arxiv, vla |
| `intel_hub` | Digest HTML → Intel Reports Hub (:11027) |
| `alerts` | Alert threshold + robofang/speechops pipeline |
| `scoring` | Relevance/urgency model |

## Fleet ingest

`POST /api/fleet/ingest` — producers: arxiv-codehunt, vla-mcp-pipeline

## Key MCP tools

- `get_top_items`, `search_items`, `generate_digest`, `check_alerts`
- `get_bundle_health`, `poll_feeds`, `distill_pending`
- `aiwatcher_help` — this help

## Ports

- Backend: **10946** | Webapp: **10947**

## Pipeline health

Dashboard card → `GET /api/pipeline/liveness`

## Intel Reports Hub

Set `INTEL_REPORTS_HUB_URL=http://127.0.0.1:11027`. Daily digest and `POST /api/digest/send` publish HTML for iPad/Tailscale. Fritz also publishes Pulse/Day Prep reports to the same hub.
"""


def get_help(topic: str | None = None) -> dict[str, Any]:
    topics = sorted(
        {
            "overview",
            "fleet_pipeline",
            "fleet",
            "api_keys",
            "integrations",
            "intel_hub",
            "alerts",
            "scoring",
        }
    )
    if not topic:
        return {
            "success": True,
            "server": "aiwatcher-mcp",
            "topics": topics,
            "markdown": _overview(),
            "message": "Call aiwatcher_help(topic='fleet_pipeline') for ingest + liveness docs.",
        }

    key = topic.strip().lower().replace("-", "_")
    if key == "api_keys":
        md = (
            "## AIWATCHER_API_KEY\n\n"
            "Optional. When set, all `/api/*` except `/health`, `/api/health`, `/metrics`, `/mcp` "
            "require `X-AIWatcher-Key` or `Authorization: Bearer`.\n\n"
            "Producers must use the same secret:\n"
            "- arxiv-mcp: `ARXIV_MCP_AIWATCHER_API_KEY`\n"
            "- vla-mcp: `VLA_AIWATCHER_API_KEY`\n\n"
            "NOT the same as ANTHROPIC_API_KEY or DEEPSEEK_API_KEY (distillation only).\n\n"
            + _read_doc("FLEET_PIPELINE.md")
        )
    elif key in ("alerts", "scoring") or key in ("overview",):
        md = _overview()
    else:
        file_name = _TOPICS.get(key)
        if not file_name or file_name == "overview":
            return {"success": False, "error": f"Unknown topic: {topic}", "topics": topics}
        md = _read_doc(file_name)

    return {
        "success": True,
        "topic": key,
        "markdown": md,
        "message": f"Loaded help topic '{key}'",
    }
