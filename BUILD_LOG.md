# BUILD_LOG.md — aiwatcher-mcp

## 2026-06-25 — SOTA gap fixes

| Check | Status | Notes |
|-------|--------|-------|
| `.env.example` bundling | Fixed | `build.ps1` now copies `.env.example` (not `.env`) to resources |
| `tauri.conf.json` resources | Fixed | `resources/.env` → `resources/.env.example` |
| NSIS hooks | Fixed | Removed dangling POSTINSTALL (`install-mcp-clients.ps1` does not exist) |
| CUA config | Fixed | Process name `aiwatcher-mcp-native-backend` → `aiwatcher-mcp-backend` |
| Context import | Fixed | `from fastmcp.server.context` → `from fastmcp import Context` |
| Tauri CORS | Fixed | Added explicit `tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost` origins |
