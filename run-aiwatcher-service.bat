@echo off
cd /d D:\Dev\repos\aiwatcher-mcp
set PATH=C:\Users\sandr\.local\bin;%PATH%
set UV_PROJECT_ENVIRONMENT=D:\Dev\repos\aiwatcher-mcp\.venv
C:\Users\sandr\.local\bin\uv.exe run --directory D:\Dev\repos\aiwatcher-mcp python -m aiwatcher_mcp.api
