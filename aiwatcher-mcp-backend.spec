# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for aiwatcher-mcp backend sidecar."""

from PyInstaller.utils.hooks import copy_metadata

pkg_name = "aiwatcher_mcp"

datas = [(f"src/aiwatcher_mcp", "aiwatcher_mcp")]
for pkg in (
    "fastmcp",
    "uvicorn",
    "pydantic",
    "starlette",
    "httpx",
):
    datas += copy_metadata(pkg)

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "aiwatcher_mcp.server",
    "aiwatcher_mcp.api",
    "aiwatcher_mcp.app",
    "aiwatcher_mcp.main",
    "aiwatcher_mcp.tools",
    "_strptime",
]

a = Analysis(
    ["run_server.py"],
    pathex=["src"],
    binaries=[],
    
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "scipy", "torch", "tensorflow"],
    noarchive=True,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    
    name="aiwatcher-mcp-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)







