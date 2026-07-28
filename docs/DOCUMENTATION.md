# aiwatcher-mcp documentation index

**Updated:** 2026-07-27

Start here — README alone does not cover bundles, webapp ops, or fleet presets.

## Operator (daily use)

| Doc | When to read |
|-----|----------------|
| [README.md](../README.md) | Install, ports, env vars, quick start |
| [INSTALL.md](../INSTALL.md) | First-time setup, troubleshooting |
| [docs/IDE_HOST_SIGNAL_BUNDLE.md](IDE_HOST_SIGNAL_BUNDLE.md) | Cursor/host IDE community buzz bundle |
| [mcp-central-docs/patterns/AIWATCHER_IDE_HOST_SIGNAL.md](../../mcp-central-docs/patterns/AIWATCHER_IDE_HOST_SIGNAL.md) | Fleet runbook (poll → distill → digest patch) |

## Webapp (:10947)

| Page | Purpose |
|------|---------|
| **Dashboard** | KPIs + manual Poll / Distill / Alerts |
| **Bundles** | Per-topic items, **bundle health**, feed linking (auto-selects IDE Host Signal) |
| **Pipeline Status** | **Scheduled runs** panel + fleet pipeline liveness |
| **Sources** | Feed enable/disable, health |
| **Digest / Morning News** | Generated output |
| **Logs** | Ring buffer from backend |

Help in-app: **Docs** page or MCP `aiwatcher_help(topic="ide_host_signal")`.

## Developer

| Doc | Purpose |
|-----|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Pipelines, schema, scheduler |
| [API.md](API.md) | MCP tools + REST (`GET /api/scheduler`, bundle health) |
| [FLEET_PIPELINE.md](FLEET_PIPELINE.md) | arxiv/vla ingest, API keys |
| [AGENTS.md](../AGENTS.md) | Agent rules, bundle presets |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | lint, test, pre-commit |

## Bundles (two layers)

1. **SQLite bundles** — `bundle_presets.py` → `ensure_fleet_bundle_presets()` on startup. Distillation uses per-bundle system prompts.
2. **Fleet JSON** — `mcp-central-docs/operations/bundles.json` catalog for `list_fleet_bundles` / documentation. Not auto-synced to SQLite except via presets code.

Preset bundles beat LLM-only `create_bundle_from_topic` for fleet-critical watches.

## Staleness watchlist

| Item | Owner action |
|------|----------------|
| `ASSESSMENT.md` (2026-06) | Refresh after major feature drops |
| `PRD.md` roadmap | Align with TODO.md |
| `pyproject.toml` version vs README footer | Bump together on release |
| `operations/bundles.json` vs `bundle_presets.py` | Keep feeds in sync when adding presets |

## CI & quality

- **CI:** `.github/workflows/ci.yml` — **Windows only**, tag push + manual dispatch, ruff + ty + pytest (`-m "not slow"`).
- **Pre-commit:** `.pre-commit-config.yaml` — **`just install`** runs `pre-commit install` (config without install = hooks inactive).
- **Tests:** `just test` — session temp DB via `tests/conftest.py`.
