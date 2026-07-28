"""Fix all 3 PS5 syntax errors in start.ps1 at once."""

import pathlib

p = pathlib.Path(__file__).resolve().parent.parent / "start.ps1"
c = p.read_text(encoding="utf-8")

# Fix 1: $svcRunning -> $svcUp (contains 'run', triggers PS5 parser)
c = c.replace("$svcRunning", "$svcUp")

# Fix 2: $uvExe run -> split into two Write-Host calls
old = '    Write-Host "  cd $RepoRoot; $uvExe run python -m aiwatcher_mcp.api" -ForegroundColor Yellow'
new = '    Write-Host "  cd $RepoRoot; " -ForegroundColor Yellow -NoNewline\n    Write-Host $uvExe -ForegroundColor Yellow -NoNewline\n    Write-Host " run python -m aiwatcher_mcp.api" -ForegroundColor Yellow'
c = c.replace(old, new)

# Fix 3: Wait-Process -> Wait-Job for Start-Job backend
c = c.replace("Wait-Process -Id $backendProc.Id", "$backendProc | Wait-Job -Timeout 99999")

# Fix 4: Stop-Process for backend job -> Stop-Job
c = c.replace("Stop-Process -Id $backendProc.Id", "$backendProc | Stop-Job")

# Fix 5: "Backend PID" -> "Backend job" (Start-Job has no PID)
c = c.replace("Backend PID", "Backend job")

p.write_text(c, encoding="utf-8")
print("Fixed.")
print("  $svcRunning -> $svcUp")
print("  $uvExe run split")
print("  Wait-Job for Start-Job backend")
