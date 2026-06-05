# Fleet pipeline — arxiv, vla, ingest, liveness

aiwatcher-mcp is the **curation and alert layer** for fleet-produced research signals: arXiv code-hunt drops, vla-mcp pipeline completions, RSS feeds, and manual ingest.

## Producer API

```
POST /api/fleet/ingest
Content-Type: application/json
X-AIWatcher-Key: <optional — required if AIWATCHER_API_KEY is set>

{
  "title": "[code-drop] Paper title",
  "summary": "Human-readable context",
  "source": "arxiv-codehunt | vla-mcp-pipeline",
  "url": "https://github.com/...",
  "urgency_hint": 8.5
}
```

After insert, linked interest bundles get `bundle_item_distillations` so items appear in bundle UI immediately.

## API key (`AIWATCHER_API_KEY`)

| State | Behavior |
|-------|----------|
| **Unset** (default) | All `/api/*` open on localhost; producers need no header |
| **Set** | Producers must send `X-AIWatcher-Key` or `Bearer` token |

**Exempt without key:** `/health`, `/api/health`, `/metrics`, `/mcp`.

**Producers that must match the key:**

- arxiv-mcp → `ARXIV_MCP_AIWATCHER_API_KEY`
- vla-mcp → `VLA_AIWATCHER_API_KEY` (or `AIWATCHER_API_KEY` in vla env)

This is **not** `ANTHROPIC_API_KEY` (distillation) or `DEEPSEEK_API_KEY` (cloud scoring).

## Interest bundles (fleet-related)

| Bundle | Feed patterns | Sources |
|--------|---------------|---------|
| China Open Weights | Fleet Events, cs.AI/LG/RO/SD, FunASR… | arxiv code-hunt |
| VLA & Spatial AI | Fleet Events, VLA, Wall-OSS, X-VLA… | vla-mcp + arxiv VLA titles |
| Robotics | Fleet Events, cs.RO, Embodied… | Both |

Edit `interests.json` or set `INTERESTS_JSON_PATH`.

## Upstream integrations

| Variable | Default | Role |
|----------|---------|------|
| `ARXIV_ENABLED` | false in code / true in example | Pull arxiv-mcp category feeds |
| `ARXIV_MCP_URL` | `http://localhost:10770` | **Not 10719** |
| `VLA_MCP_ENABLED` | true | Probe vla pipeline liveness |
| `VLA_MCP_URL` | `http://localhost:11024` | vla-mcp backend |

## Pipeline liveness

```
GET /api/pipeline/liveness?stale_hours=48
```

Checks:

- arXiv feed `last_fetched` staleness
- Wrong `ARXIV_MCP_URL` port (10719 trap)
- Upstream `arxiv-mcp` `/api/pipeline/liveness`
- Upstream `vla-mcp` `/api/pipeline/liveness` (when enabled)

Dashboard **Pipeline Health** card polls every 15s.

## Supervisor tools

- **meta-mcp** `pipeline_liveness_check`
- **fleet-agent** `pipeline_liveness_check`

## MCP help

Call `aiwatcher_help()` for topics, or `aiwatcher_help(topic="fleet_pipeline")`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Fleet ingest 401 | Set matching key on producer |
| No code drops in UI | Confirm bundle has `Fleet Events` pattern; run `sync_interests` via restart |
| arXiv feeds never fetch | Fix `ARXIV_MCP_URL` to port 10770 |
| Pipeline card degraded | Run arxiv `install_codehunt_tasks.ps1`; check vla peers |
