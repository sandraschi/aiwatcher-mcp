@echo off
cd /d D:\Dev\repos\aiwatcher-mcp
set PATH=C:\Users\sandr\.local\bin;%PATH%
"%~dp0.venv\Scripts\python.exe" -m aiwatcher_mcp.api
