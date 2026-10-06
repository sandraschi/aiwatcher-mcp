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


## 2026-10-06 - NSIS rebuild (0.1.0)

Rebuilt after `dist/` was found missing (last installer 2026-08-26; no release build existed in `native/target`).
Output: `dist/AIWatcher MCP_0.1.0_x64-setup.exe` (45.1 MB), backend 43.0 MB, frozen-binary smoke test PASSED.

Phase 1 audit (TAURI_PRODUCTION_PITFALLS A-J) gaps found and fixed:

| Gap | Fix |
|-----|-----|
| Spec `noarchive=False` (must be True) | Set `noarchive=True` |
| Spec missing `cachetools`, `joserfc*`, `mcp.types`, `key_value` hiddenimports | Added |
| `backend.rs` resolved bare flat filename before `resources/` (#19) | `resources/` first |
| `free_port` blind port-PID kill (sec 15, wslrelay class) | Image-scoped `taskkill /IM aiwatcher-mcp-backend.exe` only |
| `build.ps1` used `uv run pyinstaller` | Uses `.venv\Scripts\pyinstaller.exe` (committed earlier) |

Known, NOT fixed (needs a claimed port via fleet-gate/claim_ports.py): operator backend port equals dev backend port (10946),
violating the side-by-side rule. Mitigated by the responsive-holder attach in `spawn_backend`.
Harmless build noise: spec lists nonexistent hidden imports `aiwatcher_mcp.app/main/tools` (PyInstaller ERROR lines, build still passes);
`src-tauri/` is a duplicate of `native/` (justfile builds `native/`). Not run: CUA NSIS smoke test, installed-app verify (sec M).
