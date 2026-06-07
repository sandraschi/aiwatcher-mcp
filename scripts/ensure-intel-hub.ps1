# Ensure Fleet Intel Reports Hub is running (delegates to fleet-agent-mcp).
param(
    [string]$FleetAgentRoot = "D:\Dev\repos\fleet-agent-mcp"
)

$script = Join-Path $FleetAgentRoot "scripts\start-intel-hub.ps1"
if (-not (Test-Path -LiteralPath $script)) {
    Write-Host "WARN: Intel Hub launcher not found at $script" -ForegroundColor Yellow
    exit 0
}

& $script -Root $FleetAgentRoot
