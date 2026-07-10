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
%NSSM% set aiwatcher-mcp AppStdout "%DIR%\logs\service-stdout.log"
%NSSM% set aiwatcher-mcp AppStderr "%DIR%logs\service-stderr.log"
%NSSM% set aiwatcher-mcp Start SERVICE_AUTO_START
%NSSM% set aiwatcher-mcp AppRotateFiles 1
%NSSM% set aiwatcher-mcp AppRotateSeconds 86400
%NSSM% set aiwatcher-mcp AppRotateBytes 10485760

%NSSM% start aiwatcher-mcp
echo aiwatcher-mcp service installed and started
