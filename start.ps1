param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$BackendPort  = 10946
$FrontendPort = 10947
$RepoRoot     = $PSScriptRoot
$WebRoot      = Join-Path $RepoRoot "webapp"

Write-Host ""
Write-Host "AIWatcher MCP - Setup and Start" -ForegroundColor Cyan
Write-Host "Backend  :$BackendPort   Frontend  :$FrontendPort" -ForegroundColor DarkGray
Write-Host ""

# ===========================================================================
# FUNCTION: require a command, install via winget if missing
# ===========================================================================
function Require-Command {
    param(
        [string]$Cmd,
        [string]$WingetId,
        [string]$FriendlyName
    )
    if (Get-Command $Cmd -ErrorAction SilentlyContinue) {
        Write-Host "  [ok] $FriendlyName found" -ForegroundColor DarkGreen
        return
    }
    Write-Host "  [!]  $FriendlyName not found - installing via winget ..." -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: winget is not available on this machine." -ForegroundColor Red
        Write-Host "Please install $FriendlyName manually: $WingetId" -ForegroundColor Red
        exit 1
    }
    winget install --id $WingetId --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: winget failed to install $FriendlyName (id: $WingetId)" -ForegroundColor Red
        exit 1
    }
    # Refresh PATH in this session so the newly installed binary is found
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        Write-Host "WARNING: $FriendlyName installed but '$Cmd' still not in PATH." -ForegroundColor Yellow
        Write-Host "Close this window, reopen PowerShell, and run start.bat again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  [ok] $FriendlyName installed" -ForegroundColor Green
}

# ===========================================================================
# STEP 1 - Check / install hard prerequisites
# ===========================================================================
Write-Host "[1/5] Checking prerequisites ..." -ForegroundColor Cyan

# uv - Python package manager (also downloads Python automatically)
Require-Command "uv"   "Astral.uv"         "uv (Python package manager)"

# Node.js + npm (LTS)
Require-Command "node" "OpenJS.NodeJS.LTS"  "Node.js LTS"
Require-Command "npm"  "OpenJS.NodeJS.LTS"  "npm"

# just - command runner
Require-Command "just" "Casey.Just"         "just (command runner)"

# ===========================================================================
# STEP 2 - Python deps via uv sync (installs into .venv, no global pip)
#          ruff, ty, just are ALL local -- never assumed global
# ===========================================================================
Write-Host "[2/5] Syncing Python deps (uv sync) ..." -ForegroundColor Cyan
Write-Host "      (first run: uv may download Python 3.11 -- this can take 30s)" -ForegroundColor DarkGray
$uvExe = (Get-Command uv).Source
& $uvExe sync --project $RepoRoot
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: uv sync failed. Check pyproject.toml and network." -ForegroundColor Red
    exit 1
}
Write-Host "  [ok] Python deps ready" -ForegroundColor DarkGreen

# Quick import smoke-test -- surfaces missing deps before the health-wait loop
Write-Host "  Smoke-testing import ..." -ForegroundColor DarkGray
& $uvExe run --project $RepoRoot python -c "import aiwatcher_mcp.api; print('  [ok] Import OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: import check failed -- see output above." -ForegroundColor Red
    exit 1
}

# ===========================================================================
# STEP 3 - Frontend deps via npm install (installs vite locally, never global)
# ===========================================================================
Write-Host "[3/5] Syncing frontend deps (npm install) ..." -ForegroundColor Cyan
$npmExe = (Get-Command npm).Source
if (-not (Test-Path (Join-Path $WebRoot "node_modules"))) {
    Push-Location $WebRoot
    & $npmExe install --prefer-offline 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: npm install failed." -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "  [ok] node_modules installed" -ForegroundColor DarkGreen
} else {
    Write-Host "  [ok] node_modules already present (skipping install)" -ForegroundColor DarkGreen
}

# Verify vite is actually present locally (this is the exact bug Steve hit)
$viteLocal = Join-Path $WebRoot "node_modules\.bin\vite"
if (-not (Test-Path $viteLocal)) {
    Write-Host "ERROR: vite not found at $viteLocal after npm install." -ForegroundColor Red
    Write-Host "Try: Remove-Item -Recurse -Force '$WebRoot\node_modules'; then re-run start.bat" -ForegroundColor Yellow
    exit 1
}
Write-Host "  [ok] vite present at node_modules/.bin/vite" -ForegroundColor DarkGreen

# ===========================================================================
# STEP 4 - Clear port squatters
# ===========================================================================
Write-Host "[4/5] Clearing ports $BackendPort / $FrontendPort ..." -ForegroundColor Cyan
foreach ($port in @($BackendPort, $FrontendPort)) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "  Killed PID $($conn.OwningProcess) on :$port" -ForegroundColor Yellow
        } catch {}
    }
}
Start-Sleep -Milliseconds 500

# ===========================================================================
# STEP 5 - Start backend, wait for health, start frontend, open browser
# ===========================================================================
Write-Host "[5/5] Starting services ..." -ForegroundColor Cyan

# Backend
$backendCmd = "& '$uvExe' run --project '$RepoRoot' python -m aiwatcher_mcp.api"
$backendProc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-Command", $backendCmd `
    -WorkingDirectory $RepoRoot `
    -PassThru
Write-Host "  Backend PID $($backendProc.Id) starting on :$BackendPort" -ForegroundColor DarkGray

# Wait for backend health
$maxWait = 90
$waited  = 0
$ready   = $false
Write-Host "  Waiting for backend health (max ${maxWait}s) ..." -ForegroundColor DarkCyan
while ($waited -lt $maxWait) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$BackendPort/api/health" `
            -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
    $waited++
    if (($waited % 15) -eq 0) {
        Write-Host "    ... $waited s elapsed" -ForegroundColor DarkGray
    }
}
if (-not $ready) {
    Write-Host "ERROR: backend health check timed out after ${maxWait}s." -ForegroundColor Red
    Write-Host "The backend process may have crashed. Check the uvicorn window for errors." -ForegroundColor Red
    Write-Host "Hint: run this to see the error directly:" -ForegroundColor Yellow
    Write-Host "  cd $RepoRoot; $uvExe run python -m aiwatcher_mcp.api" -ForegroundColor Yellow
    exit 1
}
Write-Host "  [ok] Backend healthy after ${waited}s" -ForegroundColor Green

# Frontend
$frontendCmd = "npm run dev"
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", $frontendCmd `
    -WorkingDirectory $WebRoot `
    -PassThru
Write-Host "  Frontend PID $($frontendProc.Id) starting on :$FrontendPort" -ForegroundColor DarkGray

# Open browser once frontend responds
if (-not $NoBrowser) {
    $url = "http://localhost:$FrontendPort"
    $pollScript = "for (`$i=0;`$i -lt 60;`$i++) { try { `$null=Invoke-WebRequest -Uri '$url' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; Start-Process '$url'; exit } catch { Start-Sleep 1 } }"
    Start-Process "powershell.exe" -ArgumentList "-NoProfile","-WindowStyle","Hidden","-Command",$pollScript
    Write-Host "  Browser will open when Vite is ready" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Running:" -ForegroundColor Cyan
Write-Host "  Backend   http://localhost:$BackendPort"
Write-Host "  Frontend  http://localhost:$FrontendPort"
Write-Host "  MCP HTTP  http://localhost:$BackendPort/mcp"
Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

try { Wait-Process -Id $backendProc.Id -ErrorAction SilentlyContinue } catch {}
