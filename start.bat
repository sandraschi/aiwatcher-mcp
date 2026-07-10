@echo off
cd /d "D:\Dev\repos\aiwatcher-mcp"

:: If installed as NSSM service, restart via NSSM instead
C:\Windows\System32\sc.exe query aiwatcher-mcp >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo aiwatcher-mcp service found -- restarting via NSSM
    "C:\Program Files\Jellyfin\Server\nssm.exe" restart aiwatcher-mcp
    echo Done.
    exit /b 0
)

:: Fallback: use pwsh.exe (PS7) for compatibility
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WindowsApps"
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Dev\repos\aiwatcher-mcp\start.ps1" %*
echo Exit code: %ERRORLEVEL%
if %ERRORLEVEL% NEQ 0 pause
