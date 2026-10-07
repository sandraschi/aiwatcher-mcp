# ONBOARDING — aiwatcher-mcp

## What is this for

Your self-hosted AI newsroom: it polls AI news sources (RSS/Atom, HN front page,
Gmail newsletters, ArXiv, Hugging Face, Wikipedia, Readly), scores items with an
LLM, builds a daily digest, and shouts (fleet alerts + optional TTS) on breaking
items. Use from Claude Desktop / Cursor as an MCP server, or the React dashboard.

## Money / accounts

None required. Default lane is local LLM (Ollama :11434 or LM Studio :1234 —
auto-detected, see Settings). Cloud distillation (DeepSeek/Anthropic) is optional:
set `CLOUD_PROVIDERS_ALLOWED` + the provider key in `.env`. No wrappee to install.

## 5-minute start

```powershell
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
just install
just serve
```

Open the dashboard (URL printed by `start.ps1`, frontend :10947).

## First-run checklist

1. Backend dot green? (`/api/health` → `{"status":"ok"}`)
2. Settings → LLM: local provider detected? If none, start Ollama/LM Studio.
3. Bundles → seed feeds present? (`just seed-feeds` if the feeds table is empty)
4. Dashboard → Poll, then Distill, then preview the Digest.
5. Optional: email-mcp URL for digest delivery; Discord channel for posting.

## Pitfalls

- Ports 10946/10947 are registry-pinned — don't change them without updating
  `mcp-central-docs/operations/WEBAPP_PORTS.md`.
- `.env` is never committed; `.env.example` is the template.
- The dashboard shows live backend data only — there are no mock/demo KPIs, so an
  empty dashboard means the backend isn't connected (see TROUBLESHOOTING.md).

## Sanity check

```powershell
just check
Invoke-WebRequest "http://127.0.0.1:10946/api/health" -UseBasicParsing
```
