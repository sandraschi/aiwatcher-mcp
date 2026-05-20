# aiwatcher-mcp

<p align="center">
  <a href="https://github.com/casey/just"><img src="https://img.shields.io/badge/just-ready_to_go-7c5cfc?style=flat-square&logo=just&logoColor=white" alt="Just"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://biomejs.dev"><img src="https://img.shields.io/badge/Linted_with-Biome-60a5fa?style=flat-square&logo=biome&logoColor=white" alt="Biome"></a>
  <a href="https://github.com/PrefectHQ/fastmcp"><img src="https://img.shields.io/badge/FastMCP-3.2-7c5cfc?style=flat-square" alt="FastMCP"></a>
</p>


> 📖 **[Installation Guide](INSTALL.md)** — quick start, manual setup, and troubleshooting

**AI news ingestion, distillation, and alert system.**

The `aiwatcher-mcp` is a FastMCP 3.2-compliant fleet server that acts as a central intelligence node. It polls 10+ AI news sources (RSS/Atom, Gmail, ArXiv, and Readly), scores every item with Claude using a customized "Sandra" persona, generates beautiful HTML digests for daily consumption, and fires cross-fleet TTS wake-ups for breaking events.

## Features

- **Multi-Source Ingestion**: RSS/Atom feeds, Gmail newsletters (Alpha Signal), ArXiv papers, Readly magazines
- **Interest Bundles**: Per-topic distillation (e.g. "Sandra's AI Research", "Robotics", "Vienna") with custom system prompts
- **Claude Distillation**: Every item scored for Relevance (0-10) and Urgency (0-10) with multi-provider support (Anthropic, Ollama, LM Studio)
- **Feed Discovery**: LLM-elicited feed URLs are probed and verified before use; broken feeds auto-heal via fallback URL probing
- **Cross-Feed Dedup**: Title similarity via `difflib.SequenceMatcher` (85% threshold, 48h window)
- **Bundle Health**: Per-bundle metrics — items scored, avg urgency, top tags, feed contributions
- **OPML Import**: Import curated feeds from Feedly, Inoreader, etc.
- **Cross-Fleet Alerting**: `robofang` (Council bridge) + `speechops` (TTS wake-up) for items exceeding urgency threshold
- **Email & Calibre Archival**: Daily HTML digest via `email-mcp`, archived to Calibre via `calibre-mcp`
- **Web App & Prefab UI**: Standalone React/Vite dashboard + FastMCP Prefab UI card

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md): Deep dive into system flows, pipelines, and the SQLite schema.
- [API.md](docs/API.md): Reference for MCP Tools, Prompts, and Resources.
- [PRD.md](docs/PRD.md): Product requirements and roadmap.
- [ASSESSMENT.md](ASSESSMENT.md): Deep code assessment (v0.2.0)
- [TODO.md](TODO.md): Action items and progress tracking
- [SPEC_0.2.md](SPEC_0.2.md): v0.2 implementation plan

## Quick Start

```powershell
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
just
```

This opens an interactive dashboard showing all available commands. Run `just bootstrap` to install dependencies, then `just serve` or `just dev` to start.

### Manual Setup

If you don't have `just` installed:
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
.\start.ps1
### Startup Options (`start.ps1`)
*Note: The project leverages `uv` for python package management. `start.ps1` handles dependency synchronization automatically.*

## Fleet Configuration (Claude Desktop)

```json
{
  "mcpServers": {
    "aiwatcher-mcp": {
      "command": "C:\\Users\\sandr\\.local\\bin\\uv.exe",
      "args": ["run", "python", "-m", "aiwatcher_mcp.server"],
      "cwd": "D:\\Dev\\repos\\aiwatcher-mcp"
    }
  }
}
```

## Key Environment Variables (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required** for scoring + digest generation |
| `LLM_PROVIDER` | anthropic | anthropic, ollama, or lmstudio |
| `LLM_BASE_URL` | — | Custom base URL for OpenAI-compatible providers |
| `ALERT_THRESHOLD` | 8.5 | Urgency score threshold for TTS wake-up |
| `ALERT_HOUR_UTC` | 4 | Time (UTC) to trigger the morning alert |
| `ROBOFANG_ENABLED` | true | Push breaking alerts to `robofang` |
| `EMAIL_ENABLED` | false | Send digest to Sandra + Steve via `email-mcp` |
| `CALIBRE_ENABLED` | false | Archive digests to `calibre-mcp` |
| `GMAIL_ENABLED` | false | Parse newsletters from Gmail |
| `ARXIV_ENABLED` | false | Ingest latest papers from ArXiv categories |
| `READLY_ENABLED` | false | Ingest articles from Readly magazines |

## Fleet Integrations & Ports

| Service | Port | Description |
|---|---|---|
| **aiwatcher Backend** | `10946` | Main Starlette backend + FastMCP stdio |
| **aiwatcher Frontend** | `10947` | Vite/React Web App |
| **robofang** | `10871` | Breaking event POSTs to Council bridge |
| **speechops** | `10895` | TTS wake-up HTTP API |
| **email-mcp** | `10812` | Digest delivery mechanism |
| **calibre-mcp** | `10720` | Digest archival to eBook library |
| **arxiv-mcp** | `10719` | ArXiv paper ingestion (optional) |
| **readly-mcp** | `10863` | Magazine article ingestion (optional) |

## MCP Tools

| Tool | Category |
|------|----------|
| `poll_feeds` | Ingestion |
| `distill_pending` | Distillation |
| `check_alerts` | Alerting |
| `generate_digest` / `send_digest_now` | Delivery |
| `get_top_items` / `search_items` | Discovery |
| `get_feeds_list` / `add_feed` / `get_feed_health` | Feed Management |
| `get_bundles_list` / `create_bundle_from_topic` / `link_feed_to_bundle` | Bundles |
| `get_bundle_health` / `find_feeds_for_topic` | Bundles (v0.2) |
| `import_opml` | Import (v0.2) |
| `get_digest_history` / `expire_old_items` | Maintenance |
| `show_dashboard_card` | Prefab UI |

---

*Fleet server — Sandra Schipal · aiwatcher-mcp v0.2.0*
