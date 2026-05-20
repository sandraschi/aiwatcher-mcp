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
just bootstrap   # install all dependencies
just serve       # start the server
just web         # start the frontend (if applicable)
```

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
   uv sync --all-extras
   ```
4. Start the server:
   ```powershell
   # stdio mode (for MCP clients like Claude Desktop)
   uv run python -m aiwatcher_mcp.server

   # HTTP mode (for web dashboard)
   uv run uvicorn aiwatcher_mcp.server:app --port 10946
   ```

4. (optional) Start the frontend:
   ```powershell
   cd webapp
   npm install
   npm run dev
   ```

5. Open `http://localhost:10946` or the frontend URL.

---

## ❓ Troubleshooting

| Issue | Fix |
|---|---|
| `just` not found | Install via `winget install Casey.Just`, `scoop install just`, or `brew install just` |
| Port conflict | Run `just kill-all` to clear fleet ports (10700–11000) |
| Dependencies out of sync | `uv sync --all-extras` |
| Something else | [Open a GitHub issue](https://github.com/sandraschi/aiwatcher-mcp/issues) |

---

*See the main [README](README.md) for feature overview and documentation.

---

## Legacy Documentation

_This INSTALL.md was updated with the standard fleet Quick Start template. The original instructions are preserved below._

# Installation ÔÇö From Zero

This document covers a full cold-start on a machine that has nothing installed.

## Prerequisites (auto-installed if missing)

`start.bat` will install these automatically via **winget** if they are absent:

| Tool | What it does | Winget ID |
|---|---|---|
| **uv** | Python package manager ÔÇö also downloads Python 3.11 automatically | `Astral.uv` |
| **Node.js LTS** | JavaScript runtime for the React frontend | `OpenJS.NodeJS.LTS` |
| **just** | Command runner ÔÇö enables `just <recipe>` after install | `Casey.Just` |

Everything else is installed locally by those two tools:
- Python 3.11+ ÔÇö fetched by uv on first `uv sync` (reads `requires-python` from pyproject.toml)
- All Python deps ÔÇö installed into `.venv/` by `uv sync`
- vite, tailwind, react, etc. ÔÇö installed into `webapp/node_modules/` by `npm install`

**Nothing goes into global Python or npm. `just` is not required.**

## Quick start

```bat
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
REM  Open .env and set ANTHROPIC_API_KEY=sk-ant-...
start.bat
```

`start.bat` does everything:
1. Installs `uv` via winget if missing
2. Installs `Node.js LTS` via winget if missing
3. Runs `uv sync` ÔÇö creates `.venv`, downloads Python if needed, installs all Python deps
4. Runs `npm install` in `webapp/` ÔÇö installs vite and all frontend deps locally
5. Verifies `node_modules/.bin/vite` exists (explicit guard against the silent failure)
6. Runs an import smoke-test to catch errors before the 90s health-wait loop
7. Clears ports 10946 / 10947
8. Starts the Starlette backend and waits for `/api/health`
9. Starts the Vite dev server
10. Opens the browser once the frontend responds

## Manual step-by-step (if start.bat fails)

```powershell
# 1. Install uv (if missing) -- this also covers Python
winget install --id Astral.uv --silent

# 2. Install Node.js LTS (if missing)
winget install --id OpenJS.NodeJS.LTS --silent

# 3. Close and reopen PowerShell to pick up new PATH entries

# 4. Python deps (uv downloads Python 3.11 automatically on first run)
cd D:\path\to\aiwatcher-mcp
uv sync

# 5. Smoke-test
uv run python -c "import aiwatcher_mcp.api; print('OK')"

# 6. Frontend deps
cd webapp
npm install
cd ..

# 7. Set your API key
copy .env.example .env
notepad .env

# 8. Start backend (keep this window open, watch for errors)
uv run python -m aiwatcher_mcp.api

# 9. In a second window: start frontend
cd webapp
npm run dev

# 10. Open http://localhost:10947
```

## Minimum system requirements

- Windows 10 version 1809+ or Windows 11 (winget requires this)
- 4 GB RAM, 2 GB free disk
- Internet connection for first-time dep install
- `ANTHROPIC_API_KEY` for Claude scoring and digest generation

## What is NOT required

- Python (uv downloads it automatically)
- pip
- vite, ruff, tailwind (all installed locally by npm/uv)
- just, ruff, vite, tailwind (all installed locally ÔÇö just via winget, rest via uv/npm)
- Any globally installed npm packages
