"""Apply service-aware port clearing to start.ps1 (original version)."""
import pathlib

p = pathlib.Path(__file__).resolve().parent.parent / "start.ps1"
content = p.read_text(encoding="utf-8")

# === Fix 1: Service-aware port clearing ===
old_clear = """# ===========================================================================
# STEP 4 - Clear ports
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
Start-Sleep -Milliseconds 500"""

new_clear = """# ===========================================================================
# STEP 4 - Clear ports (service-aware)
# ===========================================================================
Write-Host "[4/5] Clearing ports $BackendPort / $FrontendPort ..." -ForegroundColor Cyan

$svcObj = Get-Service -Name aiwatcher-mcp -ErrorAction SilentlyContinue
if ($svcObj -and $svcObj.Status -eq 'Running') {
    Write-Host "  aiwatcher-mcp service is running - restarting via NSSM" -ForegroundColor Yellow
    $nssmBin = "C:\Program Files\Jellyfin\Server\nssm.exe"
    if (Test-Path $nssmBin) {
        Start-Process $nssmBin -ArgumentList "restart aiwatcher-mcp" -Verb RunAs -Wait
        Write-Host "  Service restarted" -ForegroundColor Green
    }
} else {
    foreach ($port in @($BackendPort, $FrontendPort)) {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            try {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "  Killed PID $($conn.OwningProcess) on :$port" -ForegroundColor Yellow
            } catch {}
        }
    }
}
Start-Sleep -Milliseconds 500"""

if old_clear in content:
    content = content.replace(old_clear, new_clear)
    p.write_text(content, encoding="utf-8")
    print("Service-aware port clearing applied")
else:
    print("CLEAR BLOCK NOT FOUND")
    idx = content.find("STEP 4")
    if idx >= 0:
        print("Found STEP 4 at", idx)
        print(repr(content[idx:idx+80]))
