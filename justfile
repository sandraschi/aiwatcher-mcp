# aiwatcher-mcp justfile
import 'scripts/just/fleet.just'
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
    @just --list

# Paths: repo root = this justfile's directory. Override UV with env UV_EXE if uv is not on PATH.
REPO := justfile_directory()
UV := env_var_or_default("UV_EXE", "uv")
PLAYWRIGHT_SCRIPT := justfile_directory()

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

# Populate baseline RSS feeds when feeds table is empty (safe to re-run)
seed-feeds:
    & "{{UV}}" run python "{{REPO}}\\scripts\\seed_feeds.py"

# --- One-off ops ---------------------------------------------------

poll-ingest:
    & "{{UV}}" run python -c "import asyncio; from aiwatcher_mcp.ingestion import poll_all_feeds; r=asyncio.run(poll_all_feeds()); print(r)"

distill-ingest:
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

# Playwright UI e2e (backend 10946 + Vite 10947)
e2e:
    Set-Location "{{REPO}}\\webapp"; npm run test:e2e

# Fleet-wide Playwright audit (mcp-central-docs; optional)
e2e-fleet-audit:
    pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "{{PLAYWRIGHT_SCRIPT}}" -RepoPath "{{REPO}}"

# Smoke test for the start script logic
test-start:
    & "{{UV}}" run pytest tests/test_startup.py

# --- Packaging ---------------------------------------------------------

# Build .mcpb bundle for Claude Desktop (requires: npm i -g @anthropic-ai/mcpb)
pack:
    New-Item -ItemType Directory -Force -Path "{{REPO}}\\dist" | Out-Null
    $ver = (Select-String -Path "pyproject.toml" -Pattern '(?m)^version = "(.*)"').Matches.Groups[1].Value
    mcpb pack "{{REPO}}" "{{REPO}}\\dist\\aiwatcher-mcp-v$ver.mcpb"
    Write-Host "Bundle: {{REPO}}\\dist\\aiwatcher-mcp-v$ver.mcpb"

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

# Poll all feeds (backend must be running)
poll:
    Set-Location "{{REPO}}"; Invoke-RestMethod -Uri "http://127.0.0.1:10946/api/poll" -Method Post -ContentType "application/json" -Body "{}"

# Run Claude distillation on pending items
distill:
    Set-Location "{{REPO}}"; Invoke-RestMethod -Uri "http://127.0.0.1:10946/api/distill" -Method Post -ContentType "application/json" -Body "{}"

# Check critical alerts
alerts:
    Set-Location "{{REPO}}"; Invoke-RestMethod -Uri "http://127.0.0.1:10946/api/alerts/check" -Method Post -ContentType "application/json" -Body "{}"

# Reload spam blocklist
scrubber-reload:
    Set-Location "{{REPO}}"; Invoke-RestMethod -Uri "http://127.0.0.1:10946/api/scrubber/reload" -Method Post -ContentType "application/json" -Body "{}"

# Show ingestion stats
stats:
    Set-Location "{{REPO}}"; Invoke-RestMethod -Uri "http://127.0.0.1:10946/api/stats" -Method Get

# CUA-NSIS smoke test
cua-nsis-test:
    uv run python scripts/cua-smoke.py
