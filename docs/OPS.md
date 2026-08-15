# aiwatcher-mcp — Operations Notes

**Last updated**: 2026-08-14

## Service Management (NSSM)

The daemon (`aiwatcher_mcp.api`, port 10946) runs as a Windows service **`aiwatcher-mcp`**
managed by NSSM (`C:\Program Files\Jellyfin\Server\nssm.exe`). All management goes through
the just recipes:

| Recipe | Action |
|--------|--------|
| `just service-status` | Status, config, last log lines, health |
| `just service-restart` | Restart (elevated) + health check |
| `just service-start` / `service-stop` | Start / stop |
| `just service-logs` / `service-errors` | Tail stdout / stderr |
| `just service-install` / `service-uninstall` | (Re)install / remove — Admin required |

**Elevation note**: the service runs under a privileged account, so manual restarts
**always pop a UAC prompt** (the recipes use `-Verb RunAs`). `Restart-Service` from a
non-elevated shell fails with "Cannot open 'aiwatcher-mcp' service" — use the recipes,
not `Restart-Service`.

**Crash recovery is automatic**: NSSM restarts the app on process exit (AppThrottle
1500 ms) — no elevation involved. SCM-level `sc failure` recovery actions are NOT
configured; NSSM's built-in restart is the layer that covers it.

## Scheduler — Off-Peak Policy (2026-08-14)

DeepSeek (the cloud fallback rung of the LLM chain) introduced peak/off-peak billing
effective 2026-08-16: **peak = 01:00-04:00 + 06:00-10:00 UTC** (off-peak = half price,
~2.4x cheaper on output). All daily cron jobs are scheduled **outside** those windows:

| Job | Time (UTC) | Peak? |
|-----|-----------|-------|
| daily_digest | 04:30 | off-peak (gap 04-06) |
| morning_news | 05:00 | off-peak |
| alerts | 04:55 (`ALERT_HOUR_UTC=4` in .env) | off-peak |
| retention | 10:15 | off-peak |
| sync_interests | 10:30 | off-peak |
| currentai_sovereignty | 10:45 | off-peak |
| distill / feed polls | every 2h / 30m-1h (interval) | continuous — runs on the local Glimmer lane (`LLM_BASE_URL=:11435`), DeepSeek only if Glimmer is down |

Times are hardcoded in `src/aiwatcher_mcp/scheduler.py` (except alerts, which reads
`ALERT_HOUR_UTC`/`ALERT_MINUTE_UTC` from .env). After changing any schedule: restart the
service (`just service-restart`) and verify with `GET http://127.0.0.1:10946/api/scheduler`.

## Watchdog Interplay

- **fleet-watchdog** (`mcp-central-docs/scripts/fleet-watchdog.ps1`, task `Fleet-aiwatcher-mcp`,
  every 20 min) health-checks :10946 and, on failure, restarts the service via
  `Restart-Service` — **fixed 2026-08-15**: `service-acl-setup.ps1` granted the user
  SID full service-management rights (via a SYSTEM-context DACL write, since these
  services are SYSTEM-owned), so restarts work from the watchdog's non-elevated
  context. The watchdog also now polls the health URL after restarting before
  claiming success (verified: DEAD → Restarted service → healthy after restart (3s)).
- **Crash recovery (SCM)**: `sc failure` configured on all fleet NSSM services —
  restart after 5s/10s/30s on failure. Belt-and-suspenders under NSSM's own
  auto-restart (AppThrottle 1500ms).
- **Glimmer watchdog** (`Watch-MuseGlimmer` scheduled task, every 5 min) is separate —
  it guards the local LLM lane (:11435/:11439), not this service.
- Re-run `mcp-central-docs/scripts/service-acl-setup.ps1` (elevated, self-elevating)
  after any service reinstall to restore the management ACE + crash recovery.

## Alert Channels (wired 2026-08-15)

- **robofang** (`ROBOFANG_BACKEND_URL=http://127.0.0.1:10871`): the robofang bridge
  (`robofang` repo, `start-bridge-headless.ps1`, forced `ROBOFANG_BRIDGE_HOST=127.0.0.1` —
  its default secure bind picks the Tailscale IP, which breaks localhost consumers).
  Supervised by `Fleet-robofang-bridge` watchdog task (health: `GET /api/v1/events`).
  Previously the .env pointed at a tailnet IP (drifts) — fixed to 127.0.0.1.
- **TTS** (`SPEECHOPS_HTTP_URL=http://localhost:10909`): the real gateway is **speech-mcp**
  (`POST /api/v1/tts`, provider `windows`). The old :10895/:10918 values were phantom
  endpoints (nothing ever served them) — aiwatcher silently fell back to SAPI5 every time.
- **Fallback chain** (in `alerting.py`): robofang → speechops → Windows SAPI5, every rung logged.

## LLM Lane

`LLM_BASE_URL=http://127.0.0.1:11435/v1` (Glimmer, local, free). Fallback chain when
Glimmer is down: Ollama (:11434) → DeepSeek cloud. See
`mcp-central-docs/analysis/glimmer-fleet-strategy.md` §5.1 and
`mcp-central-docs/analysis/llm-token-market-2026-08.md`.
