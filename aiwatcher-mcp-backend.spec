# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for aiwatcher-mcp backend sidecar."""

from PyInstaller.utils.hooks import copy_metadata

datas = [(f"src/aiwatcher_mcp", "aiwatcher_mcp")]
for pkg in ("fastmcp", "fastapi", "pydantic"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

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
    "aiwatcher_mcp.__main__",
    "_strptime",
    "mcp.types",
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
    excludes=["tkinter", "matplotlib", "pandas", "scipy", "torch", "tensorflow", "onnxruntime", "grpc"],
    noarchive=True,
    optimize=0,
)
# Strip heavy native binaries that aren't needed
SKIP = ["torch", "playwright", "bitsandbytes", "llvmlite", "pyarrow", "pymupdf", "grpc",
        "numba", "Cython", "google", "azure", "boto3", "botocore", "onnxruntime",
        "matplotlib", "pandas", "scipy", "sklearn", "PIL", "opencv", "cryptography"]
a.binaries = [b for b in a.binaries if not any(s in b[0].lower() for s in SKIP)]
# Keep essential dist-info for packages that need metadata at runtime
_keep_dist = ["fastmcp-", "fastapi-", "pydantic-", "mcp-"]
_saved = [e for e in a.datas if isinstance(e, tuple) and any(k in str(e[0]) for k in _keep_dist) and '.dist-info' in str(e[0])]
# Strip all other .dist-info from all TOC lists
for _list in [a.datas, a.binaries, a.zipfiles, a.scripts]:
    _list[:] = [e for e in _list if not (isinstance(e, tuple) and '.dist-info' in str(e[0]))]
a.datas.extend(_saved)
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







