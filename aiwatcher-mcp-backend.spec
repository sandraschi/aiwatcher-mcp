import sys, os
site_pkgs = os.path.abspath(".venv/Lib/site-packages")
if site_pkgs not in sys.path:
    sys.path.insert(0, site_pkgs)

from PyInstaller.utils.hooks import copy_metadata

pkg_name = "aiwatcher_mcp"

datas = [(f"src/aiwatcher_mcp", "aiwatcher_mcp")]
for pkg in (
    "fastmcp",
    "fastapi",
    "uvicorn",
    "pydantic",
    "starlette",
    "httpx",
):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

hiddenimports = [
    "_strptime",
    "_datetime",
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
]

a = Analysis(
    ["run_server.py"],
    pathex=["src", site_pkgs],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "scipy", "torch", "tensorflow"],
    noarchive=False,
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
