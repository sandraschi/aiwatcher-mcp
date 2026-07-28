@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run as Administrator
    pause
    exit /b 1
)

set NSSM="C:\Program Files\Jellyfin\Server\nssm.exe"
set DIR=%~dp0

%NSSM% stop aiwatcher-mcp 2>nul
%NSSM% remove aiwatcher-mcp confirm 2>nul

%NSSM% install aiwatcher-mcp "%DIR%run-aiwatcher-service.bat"
%NSSM% set aiwatcher-mcp AppDirectory "%DIR%"

REM --- Environment pinning (REQUIRED - do not remove) -------------------------
REM NSSM services run as LocalSystem. Under that account USERPROFILE/APPDATA/
REM LOCALAPPDATA resolve to C:\WINDOWS\system32\config\systemprofile\..., NOT to
REM the developer profile. aiwatcher itself anchors on Path(__file__) and is
REM currently clean, but pin anyway: this file is the template other repos get
REM copied from, and any future Path.home() usage would silently split the data.
REM See mcp-central-docs/standards/TRAPS_AND_PITFALLS.md trap 14.
%NSSM% set aiwatcher-mcp AppEnvironmentExtra "USERPROFILE=%USERPROFILE%" "APPDATA=%APPDATA%" "LOCALAPPDATA=%LOCALAPPDATA%"
%NSSM% set aiwatcher-mcp AppStdout "%DIR%\logs\service-stdout.log"
%NSSM% set aiwatcher-mcp AppStderr "%DIR%logs\service-stderr.log"
%NSSM% set aiwatcher-mcp Start SERVICE_AUTO_START
%NSSM% set aiwatcher-mcp AppRotateFiles 1
%NSSM% set aiwatcher-mcp AppRotateSeconds 86400
%NSSM% set aiwatcher-mcp AppRotateBytes 10485760

%NSSM% start aiwatcher-mcp
echo aiwatcher-mcp service installed and started
