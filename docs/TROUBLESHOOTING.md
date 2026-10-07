# TROUBLESHOOTING — aiwatcher-mcp

## Backend won't bind :10946 (port zombie)

```powershell
just zombies        # dry-run: who holds fleet ports
just zombie-clean   # kill stale listeners
```

`start.ps1` clears the port before binding; if you bypass it, clear manually.

## Dashboard shows "unreachable" but curl :10946 works

Browser-path vs curl-path (assfix 2026-10-07). The webapp uses same-origin
`/api` (vite proxy) everywhere except inside Tauri. If you opened the frontend
via a LAN/Tailscale name with a stale bundle, hard-refresh. Do NOT "fix" by
widening CORS — fix the URL. Verify both:

```powershell
Invoke-WebRequest "http://127.0.0.1:10947/api/health" -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:10946/api/health" -UseBasicParsing `
  -Headers @{ Origin = "http://goliath:10947" } |
  Select-Object -ExpandProperty Headers |
  Select-Object -ExpandProperty "Access-Control-Allow-Origin"
```

## DB locked / two writers

Only the HTTP daemon owns `data/aiwatcher.db` (WAL). Stdio instances detect the
daemon via `AIWATCHER_API_URL` (default `http://127.0.0.1:10946/mcp`) and become
`create_proxy()` shells. If you see locking: something opened the DB directly —
`sqlite3.connect` on another repo's `data/` path is a HIGH violation. Restart the
daemon, don't add writers.

## Scheduler ran but no items

1. `get_feeds_list` — feeds enabled? 2. `/api/feeds/health` — failure counts?
3. `AIWATCHER_E2E=1` set? It skips live polling + model validation by design.
4. LLM lane down? `/api/llm/health` shows provider readiness; distillation needs a
   reachable provider (local Ollama/LM Studio or allow-listed cloud + key).

## Digest email never arrives

email-mcp integration is opt-in. Check `EMAIL_MCP_URL` + Basic auth, then
`send_digest_now` output, then email-mcp logs. Discord posting needs
`DISCORD_DIGEST_CHANNEL_ID`.

## NSSM service stale after update

`sc.exe stop aiwatcher-mcp` + `sc.exe start aiwatcher-mcp` (never taskkill the
child — NSSM respawns it), then verify a NEW PID owns :10946 and
`/api/health` returns 200. `POST /api/shutdown` first for an orderly exit.

## Pack fails

`just mcpb-pack` needs Bun (`bunx @anthropic-ai/mcpb`) and `uv sync` first.
Never hand-edit `mcpb/src/` — fix `src/` and re-pack.
