# aiwatcher-mcp

AI news ingestion, distillation, and alert system. FastMCP 3.2 fleet server.

Polls 10+ AI news sources, scores everything with Claude (Sandra-persona), generates
beautiful HTML digests for Sandra and Steve, and fires TTS wake-ups for breaking events.

## Architecture

```
RSS/Atom + Gmail (Alpha Signal)
        │
        ▼
   Ingestion  ──────►  SQLite (items, feeds, digests)
        │                        │
        ▼                        ▼
  APScheduler         Claude Distillation
  (poll/distill/          (relevance + urgency
   alerts/digest)          scores + summaries)
        │                        │
        ├──── urgency ≥ 8.5 ─────►  robofang Council POST
        │                            speechops TTS wake-up
        │
        ├──── 06:00 UTC ──────────►  HTML digest email
        │                            (Sandra + Steve via email-mcp/SMTP)
        │
        └──── digest ─────────────►  calibre-mcp (AI News library)
```

## Ports

| Service  | Port  |
|----------|-------|
| Backend  | 10946 |
| Frontend | 10947 |
| MCP HTTP | 10946/mcp |

## Quick Start (from zero)

```bat
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
REM  Edit .env -- set ANTHROPIC_API_KEY=sk-ant-...
start.bat
```

`start.bat` handles everything on a bare machine: installs **uv** and **Node.js LTS**
via winget if absent, runs `uv sync` and `npm install`, smoke-tests the import,
then starts backend + frontend and opens the browser. See [INSTALL.md](INSTALL.md)
for the full manual walkthrough.

**Nothing needs to be pre-installed globally** — not vite, not ruff, not just, not pip.

## Claude Desktop Config

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

## Key Config (.env)

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for scoring + digest |
| `ALERT_THRESHOLD` | 8.5 | Urgency score for TTS wake-up |
| `ALERT_HOUR_UTC` | 4 | 5am Vienna CET / 6am CEST |
| `ROBOFANG_ENABLED` | true | Push breaking alerts to robofang |
| `EMAIL_ENABLED` | false | Send digest to Sandra + Steve |
| `EMAIL_RECIPIENTS` | — | Comma-separated |
| `CALIBRE_ENABLED` | false | Archive digests to Calibre |
| `GMAIL_ENABLED` | false | Parse Alpha Signal from Gmail |

## MCP Tools

`poll_feeds` · `distill_pending` · `check_alerts` · `generate_digest` ·
`send_digest_now` · `get_top_items` · `get_feeds_list` · `add_feed` ·
`show_dashboard_card` (Prefab UI)

## Fleet Integrations

- **robofang** — breaking event POSTs to Council bridge (port 10871)
- **speechops** — TTS wake-up HTTP (port 10895), SAPI5 fallback
- **email-mcp** — digest delivery (port 10812)
- **calibre-mcp** — digest archival to "AI News" library (port 10720)
- **Gmail MCP** — Alpha Signal newsletter ingestion

## Standards

FastMCP 3.2+ · WEBAPP_STANDARDS §1.4 (capabilities endpoint) ·
SOTA_REQUIREMENTS (dual transport, Prefab UI) · fleet port range 10700-11000

---
*Fleet server — Sandra Schipal · aiwatcher-mcp v0.1.0*
