# aiwatcher-mcp justfile
# just is installed by start.bat/start.ps1 via winget (Casey.Just).
# After start.bat runs once on a new machine, `just` is available everywhere.
#
# Usage: just <recipe>   (run from repo root)
#   just install         -- install all deps
#   just check           -- smoke-test import
#   just backend         -- start backend only
#   just frontend        -- start frontend only
#   just lint / fmt      -- ruff formatting and linting
#   just test            -- run pytest
#   just pack            -- build .mcpb bundle
#   just install-task    -- register 5am Windows Scheduled Task

# Use PowerShell instead of sh (no Git Bash dependency)
set shell := ["powershell.exe", "-NoProfile", "-Command"]

# Open the interactive recipe dashboard in the browser
default:
    @pwsh.exe -NoProfile -ExecutionPolicy Bypass -File ../mcp-central-docs/scripts/just-dashboard.ps1 -Path .

UV := "C:\\Users\\sandr\\.local\\bin\\uv.exe"
REPO := "D:\\Dev\\repos\\aiwatcher-mcp"

# --- Install -------------------------------------------------------

# Install all deps (Python + frontend)
install:
    & "{{UV}}" sync
    Set-Location "{{REPO}}\\webapp"; npm install

# --- Dev -----------------------------------------------------------

# Start Starlette backend only (for debugging)
backend:
    Set-Location "{{REPO}}"; & "{{UV}}" run python -m aiwatcher_mcp.api

# Start backend only in headless mode
backend-headless:
    powershell.exe -ExecutionPolicy Bypass -File .\start.ps1 -BackendOnly -Headless

# Start MCP stdio server only (for Claude Desktop testing)
mcp:
    Set-Location "{{REPO}}"; & "{{UV}}" run python -m aiwatcher_mcp.server

# Start Vite frontend only
frontend:
    Set-Location "{{REPO}}\\webapp"; npm run dev

# Start everything via the fleet start script
start:
    Set-Location "{{REPO}}"; .\\start.bat

# --- Sanity checks -------------------------------------------------

# Quick import check -- catches missing deps before start.bat hangs
check:
    & "{{UV}}" run python -c "import aiwatcher_mcp.api; print('Import OK')"

# Verify DB init
db-init:
    & "{{UV}}" run python -c "import asyncio; from aiwatcher_mcp.database import init_db; asyncio.run(init_db()); print('DB OK')"

# --- One-off ops ---------------------------------------------------

poll:
    & "{{UV}}" run python -c "import asyncio; from aiwatcher_mcp.ingestion import poll_all_feeds; r=asyncio.run(poll_all_feeds()); print(r)"

distill:
    & "{{UV}}" run python -c "import asyncio; from aiwatcher_mcp.distillation import distill_items; r=asyncio.run(distill_items(50)); print(f'Distilled: {r}')"

alert-test:
    & "{{UV}}" run python "{{REPO}}\\scripts\\morning_alert.py"

# --- Quality -------------------------------------------------------

lint:
    & "{{UV}}" run ruff check src/ tests/

fmt:
    & "{{UV}}" run ruff format src/ tests/

typecheck:
    & "{{UV}}" run ty check src/ tests/ --ignore-errors

test:
    & "{{UV}}" run pytest

# Smoke test for the start script logic
test-start:
    & "{{UV}}" run pytest tests/test_startup.py

# --- Packaging ---------------------------------------------------------

# Build .mcpb bundle for Claude Desktop (requires: npm i -g @anthropic-ai/mcpb)
pack:
    New-Item -ItemType Directory -Force -Path "{{REPO}}\\dist" | Out-Null
    mcpb pack "{{REPO}}" "{{REPO}}\\dist\\aiwatcher-mcp-v0.1.0.mcpb"
    Write-Host "Bundle: {{REPO}}\\dist\\aiwatcher-mcp-v0.1.0.mcpb"

# Validate manifest.json without packing
validate-manifest:
    mcpb validate "{{REPO}}\\manifest.json"

# Register the 5am Windows Scheduled Task
install-task:
    powershell.exe -ExecutionPolicy Bypass -File "{{REPO}}\\scripts\\install_task.ps1"

# Run DB migrations
migrate:
    & "{{UV}}" run python "{{REPO}}\\scripts\\migrate.py"

# List pending migrations
migrate-list:
    & "{{UV}}" run python "{{REPO}}\\scripts\\migrate.py" --list

# ── Ingestion ──────────────────────────────────────────────────────────────

# Poll all feeds
poll:
    cd '{{justfile_directory()}}'; \
    curl -s http://127.0.0.1:10946/api/poll | python -c "import sys,json; d=json.load(sys.stdin); [print(f'{k}: {v} new') for k,v in d.get('results',d).items()]"

# Run Claude distillation on pending items
distill:
    cd '{{justfile_directory()}}'; \
    curl -s -X POST http://127.0.0.1:10946/api/distill -H "Content-Type: application/json" -d '{}' | python -c "import sys,json; d=json.load(sys.stdin); print(f'Distilled {d.get(\"items_distilled\",0)} items')"

# Check critical alerts
alerts:
    cd '{{justfile_directory()}}'; \
    curl -s http://127.0.0.1:10946/api/alerts | python -c "import sys,json; d=json.load(sys.stdin); a=d.get('alerts',[]); print(f'{len(a)} alerts'); [print(f'  {x.get(\"title\",\"?\")} urgency={x.get(\"urgency\",\"?\")}') for x in a[:5]]"

# Reload spam blocklist
scrubber-reload:
    cd '{{justfile_directory()}}'; \
    curl -s -X POST http://127.0.0.1:10946/api/scrubber/reload | python -c "import sys,json; print(json.load(sys.stdin))"

# Show ingestion stats
stats:
    cd '{{justfile_directory()}}'; \
    curl -s http://127.0.0.1:10946/api/stats | python -c "import sys,json; d=json.load(sys.stdin); [print(f'{k}: {v}') for k,v in d.items()]"
