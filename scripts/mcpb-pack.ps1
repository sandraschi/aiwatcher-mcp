#Requires -Version 5.1
<#
.SYNOPSIS
Fleet shim for the .mcpb pack pipeline (do not vendor logic here).
Canonical implementation: mcp-central-docs/scripts/fleet-mcpb-pack.ps1
(resolved relative to this repo so naked clones on any drive keep working).
Fixes land centrally and reach every shimmed repo at once.
#>
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path $RepoRoot).Path
$Central = Join-Path (Split-Path -Parent $RepoRoot) 'mcp-central-docs\scripts\fleet-mcpb-pack.ps1'
if (-not (Test-Path -LiteralPath $Central)) {
    throw "Fleet pack pipeline not found: $Central (clone mcp-central-docs next to this repo, or run mcpb/pack.ps1 directly)."
}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Central -RepoRoot $RepoRoot
if ($LASTEXITCODE -ne 0) { throw "fleet-mcpb-pack.ps1 failed (exit $LASTEXITCODE)" }
