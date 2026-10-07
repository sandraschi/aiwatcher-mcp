#Requires -Version 5.1
<#
.SYNOPSIS
Forwarder: `just mcpb-pack` (scripts/just/fleet.just) invokes this path.
Canonical pipeline lives in mcp-central-docs/scripts/fleet-mcpb-pack.ps1 and is
reached via scripts/mcpb-pack.ps1 (fleet shim). This file carries no pack logic
so fleet fixes apply without per-repo edits (audit class: VENDORED).
#>
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Shim = Join-Path $RepoRoot 'scripts\mcpb-pack.ps1'
if (-not (Test-Path -LiteralPath $Shim)) { throw "Missing fleet shim: $Shim" }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Shim -RepoRoot $RepoRoot
if ($LASTEXITCODE -ne 0) { throw "mcpb pack pipeline failed (exit $LASTEXITCODE)" }
