# Installation

## 🚀 Quick Start (recommended)

```powershell
# Install just if you don't have it
winget install Casey.Just    # Windows
# scoop install just          # Windows (alternative)
# brew install just           # macOS
# sudo apt install just       # Debian/Ubuntu
# cargo install just          # Linux (Rust)

git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
just
```

The interactive recipe dashboard opens in your browser. From there:

```powershell
just install     # Python (uv sync) + webapp npm install
just start       # full stack via start.bat / start.ps1
just backend     # API only  |  just frontend   # Vite only
```

Set `UV_EXE` in the environment if `uv` is not on your PATH when `just` runs (optional; defaults to `uv`).

> **Why not `pip install`?** MCP servers bundle webapps, configs, project scaffolding, and tooling that a flat Python package can't deliver. PyPI offers no safety advantage — it doesn't audit packages either. `just` gives you the complete, ready-to-run stack.

---

## 🐌 Traditional Setup

If you prefer not to use `just`:

1. Install [Python 3.13+](https://python.org) and [uv](https://docs.astral.sh/uv/)
2. Clone and enter the repo:
   ```powershell
   git clone https://github.com/sandraschi/aiwatcher-mcp
   cd aiwatcher-mcp
   ```
3. Install dependencies:
   ```powershell
   uv sync
   ```
4. Start the **HTTP API** (REST + MCP at `http://localhost:10946/mcp`):
   ```powershell
   uv run python -m aiwatcher_mcp.api
   ```
   For **stdio MCP** only (e.g. Claude Desktop): `uv run python -m aiwatcher_mcp.server`
5. (Optional) Start the frontend in another terminal:
   ```powershell
   cd webapp
   npm install
   npm run dev
   ```
6. Open **`http://localhost:10947`** for the web UI, or **`http://localhost:10946/api/health`** for the API.

---

## Intel Reports Hub (optional)

Daily digest HTML is published to the shared fleet hub when `INTEL_REPORTS_HUB_URL` is set (default `http://127.0.0.1:11027` in `.env.example`).

```powershell
# Ensure hub is running (from fleet-agent-mcp or aiwatcher)
.\scripts\ensure-intel-hub.ps1
```

Hub index: `http://127.0.0.1:11027/` — iPad via Tailscale. See `docs/API.md` and mcp-central-docs `patterns/intel-reports-hub.md`.

---

## ❓ Troubleshooting

| Issue | Fix |
|---|---|
| `just` not found | Install via `winget install Casey.Just`, `scoop install just`, or `brew install just` |
| Port **10946** / **10947** in use | Stop other dev servers or change `BACKEND_PORT` / `FRONTEND_PORT` in `.env` |
| Dependencies out of sync | `uv sync` (and `cd webapp; npm install` for the UI) |
| Something else | [Open a GitHub issue](https://github.com/sandraschi/aiwatcher-mcp/issues) |

---

*See the main [README](README.md) for feature overview and documentation.*

---

## Legacy: Windows zero-install (`start.bat`)

`start.bat` / `start.ps1` can install **uv**, **Node LTS**, **npm**, and **just** via winget when missing, run `uv sync`, run `npm install` in `webapp/`, smoke-test `import aiwatcher_mcp.api`, clear ports **10946** / **10947**, start the API and Vite, then open the browser (unless `-NoBrowser` or `-BackendOnly`).

```bat
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
REM Edit .env - set ANTHROPIC_API_KEY for cloud distillation
start.bat
```

**Prerequisites (auto via winget):** `Astral.uv`, `OpenJS.NodeJS.LTS`, `Casey.Just` (see script for details).

**Python:** `requires-python` is **>=3.11**; uv installs a compatible runtime into `.venv` on first sync.

**Flags (see `start.ps1`):** `-Headless`, `-BackendOnly`, `-NoBrowser`, env **`SKIP_SYNC=1`**.

**Manual sequence if `start.bat` fails:** install uv + Node from winget, reopen shell, `uv sync`, `uv run python -c "import aiwatcher_mcp.api; print('OK')"`, `cd webapp` then `npm install`, set `.env`, then `uv run python -m aiwatcher_mcp.api` in one window and `npm run dev` in `webapp` in another. Frontend: **http://localhost:10947**.

**Minimum:** Windows 10 1809+, ~4 GB RAM, network for first install; **ANTHROPIC_API_KEY** (or a local LLM provider) for distillation as configured.
