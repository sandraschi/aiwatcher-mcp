@echo off
cd /d "%~dp0"

:: If the aiwatcher service exists, restart via NSSM
sc.exe query aiwatcher-mcp >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo aiwatcher-mcp service found -- restarting via NSSM
    "C:\Program Files\Jellyfin\Server\nssm.exe" restart aiwatcher-mcp
    echo Done.
    exit /b 0
)

echo aiwatcher-mcp service not installed.
echo Install it first: install-service.bat (as Admin)
pause
