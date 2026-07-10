param([switch]$Headless, [switch]$BackendOnly, [switch]$NoBrowser)

$svc = Get-Service -Name aiwatcher-mcp -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host 'aiwatcher-mcp service found -- restarting via NSSM' -ForegroundColor Yellow
    $nssm = 'C:\Program Files\Jellyfin\Server\nssm.exe'
    if (Test-Path $nssm) {
        Start-Process $nssm -ArgumentList 'restart aiwatcher-mcp' -Verb RunAs -Wait
        Write-Host 'Service restarted' -ForegroundColor Green
    }
    exit
}

Write-Host 'aiwatcher-mcp service not installed.' -ForegroundColor Red
Write-Host 'Install it first: install-service.bat (as Admin)' -ForegroundColor Yellow
exit 1
