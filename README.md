# aiwatcher-mcp

<p align="center">
  <a href="https://github.com/casey/just"><img src="https://img.shields.io/badge/just-ready_to_go-7c5cfc?style=flat-square&logo=just&logoColor=white" alt="Just"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
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
- **Cross-Feed Dedup**: Title + summary fuzzy match (`difflib`, 85%, 48h)
- **Feed Quality Decay**: Flags low-signal feeds (30d avg urgency)
- **Fleet Event Journal**: `ingest_fleet_event` for PRs, missions, fleet activity
- **Tag Trends**: `get_tag_trends` / `GET /api/trends`
- **Portfolio Watch**: Keyword list boosts urgency during distillation
- **Digest Cache**: TTL avoids repeat LLM calls (`DIGEST_CACHE_TTL_MINUTES`)
- **Prometheus**: `GET /metrics` for fleet monitoring
- **Fritz Integration**: Office Day Prep pulls `get_top_items` from aiwatcher
- **Bundle Health**: Per-bundle metrics — items scored, avg urgency, top tags, feed contributions
- **OPML Import**: Import curated feeds from Feedly, Inoreader, etc.
- **Cross-Fleet Alerting**: `robofang` (Council bridge) + `speechops` (TTS wake-up) for items exceeding urgency threshold
- **Email & Calibre Archival**: Daily HTML digest via `email-mcp`, archived to Calibre via `calibre-mcp`
- **Current AI Stack Gap Map**: `currentai` portmanteau tool — fetch product openness/maturity data from currentai-org/os-ai-map, store versioned snapshots, diff changes, flag fleet-dependency concentration risk
- **Intel Reports Hub**: Daily digest HTML published to shared fleet hub (`INTEL_REPORTS_HUB_URL`, port **11027**) for iPad/Tailscale reading
- **Web App & Prefab UI**: Standalone React/Vite dashboard + FastMCP Prefab UI card

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md): Deep dive into system flows, pipelines, and the SQLite schema.
- [API.md](docs/API.md): MCP tools / prompts / resources + HTTP REST index (`/api/capabilities` for live tool names).
- [PRD.md](docs/PRD.md): Product requirements and roadmap.
- [ASSESSMENT.md](ASSESSMENT.md): Code assessment (updated 2026-06-03)
- [TODO.md](TODO.md): Action items and progress tracking
- [SPEC_0.2.md](SPEC_0.2.md): v0.2 implementation plan

## Quick Start

```powershell
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
just
```

This opens an interactive dashboard showing all available commands. Run `just install` to install dependencies, then `just start` (or `just backend` / `just frontend` separately).

### Manual Setup

If you don't have `just` installed:

```powershell
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
.\start.ps1
```

### Startup Options (`start.ps1`)

- **`-Headless`** — re-launch in a hidden window (see script header).
- **`-BackendOnly`** — Python API only (no Vite); skips frontend `npm install`.
- **`-NoBrowser`** — do not open the browser when the frontend is ready.
- **`SKIP_SYNC=1`** — skip `uv sync` (useful when another process holds the venv).

`start.ps1` uses **`uv`** for Python deps and resolves **`npm.cmd`** next to **`node.exe`** so installs work with nvm/scoop-style shims.

## Fleet Configuration (Claude Desktop)

```json
{
  "mcpServers": {
    "aiwatcher-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "aiwatcher_mcp.server"],
      "cwd": "C:\\path\\to\\aiwatcher-mcp"
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
| `ARXIV_ENABLED` | false | Ingest latest papers (`ARXIV_MCP_URL` default **10770**) |
| `READLY_ENABLED` | false | Readly (blocked on upstream MCP tool) |
| `AIWATCHER_API_KEY` | — | Optional REST auth on `/api/*` (exempt: health, `/mcp`). When set, mirror on `ARXIV_MCP_AIWATCHER_API_KEY` and `VLA_AIWATCHER_API_KEY` |
| `VLA_MCP_ENABLED` | true | Probe vla-mcp pipeline liveness (`VLA_MCP_URL` default **11024**) |
| `DIGEST_CACHE_TTL_MINUTES` | 60 | Reuse recent digest without LLM |
| `just seed-feeds` | — | Baseline RSS if feeds table empty |

## Fleet Integrations & Ports

| Service | Port | Description |
|---|---|---|
| **aiwatcher Backend** | `10946` | Starlette REST + MCP HTTP at **`/mcp`** (`python -m aiwatcher_mcp.api`) |
| **aiwatcher Frontend** | `10947` | Vite/React Web App |
| **robofang** | `10871` | Breaking event POSTs to Council bridge |
| **speechops** | `10895` | TTS wake-up HTTP API |
| **email-mcp** | `10812` | Digest delivery mechanism |
| **calibre-mcp** | `10720` | Digest archival to eBook library |
| **arxiv-mcp** | `10770` | ArXiv paper ingestion + code-hunt fleet push |
| **vla-mcp** | `11024` | VLA robotics pipeline fleet push + liveness probe |
| **fleet-agent-mcp** | `10996` | Fritz — calls aiwatcher in Day Prep |
| **readly-mcp** | `10863` | Magazine article ingestion (optional) |

## Testing

```powershell
just test          # pytest (unit/integration)
just e2e           # Playwright — starts backend :10946 + Vite :10947, runs webapp/e2e
```

First-time e2e setup (from repo root):

```powershell
uv sync
Set-Location webapp
npm install
npx playwright install chromium
npm run test:e2e
```

Fleet-wide UI audit (optional, `mcp-central-docs` script): `just e2e-fleet-audit`.

## MCP Tools

Authoritative tool names and counts come from the running server (**`GET /api/capabilities`** → `tool_surface.atomic_tools`). Typical built-ins include:

| Tool | Category |
|------|----------|
| `poll_feeds` | Ingestion |
| `distill_pending` | Distillation |
| `check_alerts` | Alerting |
| `generate_digest` / `send_digest_now` | Delivery |
| `get_top_items` / `search_items` | Discovery |
| `get_feeds_list` / `add_feed` / `get_feed_health` | Feeds |
| `get_bundles_list` / `create_bundle_from_topic` / `link_feed_to_bundle` | Bundles |
| `list_fleet_bundles` / `update_fleet_bundle` | Fleet bundles |
| `get_bundle_health` / `find_feeds_for_topic` | Bundles + discovery |
| `import_opml` | Import |
| `ingest_fleet_event` / `get_tag_trends` | Fleet journal + trends |
| `get_digest_history` / `expire_old_items` | Maintenance |
| `scrubber_reload` | Spam / scrubber |
| `show_dashboard_card` | Prefab UI (when enabled) |

Extra tools may appear when **`MCP_BRIDGE_URLS`** is set (proxied remote tools).

---

*Fleet server — Sandra Schipal · **aiwatcher-mcp** `0.1.6` (see `pyproject.toml` / `_version.py`)*
