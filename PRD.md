# AIWatcher MCP - Product Requirements

**Version**: 0.1.7 (2026-08-24)
**Owner**: Sandra Schipal, Vienna
**Fleet role**: Central intelligence node - polls, scores, and alerts on AI news.

## Purpose

AIWatcher is the fleet's AI news ingestion, distillation, and alert system. It
polls 10+ sources (RSS/Atom, Gmail/Alpha Signal, arXiv, HuggingFace, Readly),
scores every item with a local LLM using a "Sandra" persona, fires cross-fleet
TTS wake-ups for breaking events, and delivers a daily HTML digest by email,
Discord, and the Intel Reports Hub.

## Architecture

```
Feeds/Email/arXiv/Readly ──► SQLite DB ──► Distillation (LLM, 4h) ──► Scoring
        │                                          │
        └── alerts (TTS/robofang, 04:55 UTC)       └── daily digest 04:30 UTC
                                                       ├── email (email-mcp)
                                                       ├── Discord (discord-mcp)
                                                       └── Intel Hub (11027)
Starlette REST :10946  +  FastMCP /mcp  +  Vite UI :10947
```

- **Backend**: Starlette REST + FastMCP streamable HTTP at `/mcp` (port 10946)
- **Frontend**: Vite/React dashboard (port 10947)
- **Scheduler**: APScheduler - poll 30m, distill 4h, alerts 04:55Z, digest 04:30Z
- **Storage**: SQLite (WAL), LanceDB-free; FTS5 search; digests table persists deliveries

## Local LLM Stack (2026-08-15)

- Single engine: **Ollama** (`11434`), model store on `N:\AI\ollama\models`
- Workhorse: **muse-glimmer-131k:latest** (30B multimodal, 131K ctx, vision projector)
- Ollama native `/api/chat` with `think: false` (thinking models otherwise return
  empty content via OpenAI-compat)
- Flash + pro + digest all use the same resident model instance

## Shipped Features

- Multi-source ingestion: RSS/Atom, Gmail (Alpha Signal), arXiv, HuggingFace,
  Readly, Wikipedia, web_search (OpenSERP), Obscura stealth rendering (`d:\Dev\repos\external\obscura`)
- Tiered distillation: flash pass -> classify -> pro rescore (borderline only)
- Interest bundles (config + fleet presets), cross-feed dedup, feed auto-heal, Obscura 403/429 fallback
- Daily HTML+text digest: email-mcp delivery (Basic auth, configurable recipients),
  Discord posting (opt-in channel), Intel Hub publish (Basic auth)
- Alerts: robofang bridge + speech TTS wake-up at urgency >= 8.5
- MCP tools: feeds/bundles/items CRUD, distill_pending, digest preview/send,
  search, tags, currentai portmanteau, inbox scan, fleet event ingest

## Non-Goals

- Cloud LLM providers are gated behind `CLOUD_PROVIDERS_ALLOWED` (empty = local-only)
- No model training; no user accounts; single-operator fleet tool

## Status

- **v0.1.7** - Integrated Obscura stealth pre-rendering engine (`_fetch_with_obscura`) to handle 403/429 feed blocks.
- **v0.1.6** - Local LLM consolidation (Ollama muse-glimmer-131k), digest delivery
  pipeline repaired (email endpoint/auth, hub auth, Discord posting), item_count fix.
