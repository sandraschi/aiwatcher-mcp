@echo off
cd /d "D:\Dev\repos\aiwatcher-mcp"

:: Ensure WindowsApps (winget location) is on PATH for the child PowerShell session
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WindowsApps"

powershell.exe -ExecutionPolicy Bypass -File "D:\Dev\repos\aiwatcher-mcp\start.ps1" %*
echo Exit code: %ERRORLEVEL%
if %ERRORLEVEL% NEQ 0 pause
