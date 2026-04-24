# aiwatcher-mcp justfile
# just is installed by start.bat/start.ps1 via winget (Casey.Just).
# After start.bat runs once on a new machine, `just` is available everywhere.
#
# Usage: just <recipe>   (run from repo root)
#   just install         -- install all deps
#   just check           -- smoke-test import
#   just backend         -- start backend only
#   just lint / fmt      -- ruff
#   just pack            -- build .mcpb bundle
#   just install-task    -- register 5am Windows Scheduled Task

# Use PowerShell instead of sh (no Git Bash dependency)
set shell := ["powershell.exe", "-NoProfile", "-Command"]

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
    & "{{UV}}" run ruff check src/

fmt:
    & "{{UV}}" run ruff format src/

typecheck:
    & "{{UV}}" run ty check src/ --ignore-errors

# --- Packaging ---------------------------------------------------------

# Build .mcpb bundle for Claude Desktop (requires: npm i -g @anthropic-ai/mcpb)
pack:
    New-Item -ItemType Directory -Force -Path "{{REPO}}\\dist" | Out-Null
    mcpb pack "{{REPO}}" "{{REPO}}\\dist\\aiwatcher-mcp-v0.1.0.mcpb"
    Write-Host "Bundle: {{REPO}}\\dist\\aiwatcher-mcp-v0.1.0.mcpb"

# Validate manifest.json without packing
validate-manifest:
    mcpb validate "{{REPO}}\\manifest.json"
    powershell.exe -ExecutionPolicy Bypass -File "{{REPO}}\\scripts\\install_task.ps1"
