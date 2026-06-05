# Playwright: backend (10946) in background, then Vite foreground (10947)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Runner = Join-Path $ProjectRoot "webapp\e2e_run_backend.py"

if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python. Run 'uv sync' in project root first."
}

function Stop-PortListeners([int]$port) {
    netstat -ano -p tcp | Select-String ":$port\s" | ForEach-Object {
        $parts = ($_.Line -replace '\s+', ' ').Trim().Split(' ')
        $procId = [int]$parts[-1]
        if ($procId -gt 4) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-PortListeners 10946
Stop-PortListeners 10947
Start-Sleep -Seconds 1

$backend = Start-Process -FilePath $Python -ArgumentList $Runner -PassThru -WindowStyle Hidden

$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:10946/health" -TimeoutSec 3
        if ($h.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Write-Error "Backend did not become healthy on port 10946 within 90s"
}

Set-Location $PSScriptRoot
try {
    npm run dev
} finally {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
