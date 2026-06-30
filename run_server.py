"""PyInstaller entrypoint for aiwatcher-mcp HTTP sidecar."""

from __future__ import annotations

import os

os.environ["OTEL_PYTHON_CONTEXT"] = "contextvars_context"

# Shim the entire opentelemetry package — its entry-point-based provider
# discovery doesn't work in frozen PyInstaller builds (StopIteration).
# fastmcp.server.server imports opentelemetry.trace which requires this.
import sys
import types as _types


def _noop(*a, **kw):
    return None


class _NoopTracer:
    start_span = _noop
    end_span = _noop


class _NoopSpan:
    set_attribute = _noop
    end = _noop


_noop_tracer = _NoopTracer()
for _name, _mod in {
    "opentelemetry": _types.ModuleType("opentelemetry"),
    "opentelemetry.trace": _types.ModuleType("opentelemetry.trace"),
    "opentelemetry.context": _types.ModuleType("opentelemetry.context"),
    "opentelemetry.context.contextvars_context": _types.ModuleType(
        "opentelemetry.context.contextvars_context"
    ),
}.items():
    _mod.__path__ = []
    _mod.get_tracer = lambda *a, **kw: _noop_tracer
    _mod.get_tracer_provider = lambda *a, **kw: _NoopTracer()
    _mod.set_tracer_provider = _noop
    _mod.Tracer = type("Tracer", (), {})
    _mod.NonRecordingSpan = _NoopSpan
    _mod._Span = _NoopSpan
    _mod.Status = type("Status", (), {"__init__": _noop})
    _mod.StatusCode = type("StatusCode", (), {"UNSET": 0, "OK": 1, "ERROR": 2})
    _mod.SpanKind = type(
        "SpanKind", (), {"INTERNAL": 0, "SERVER": 1, "CLIENT": 2, "PRODUCER": 3, "CONSUMER": 4}
    )
    _mod.propagate = _types.ModuleType("opentelemetry.propagate")
    _mod.Span = _NoopSpan
    _mod.Tracer = _NoopTracer
    sys.modules[_name] = _mod

# Fix _RUNTIME_CONTEXT specifically
sys.modules["opentelemetry.context"]._RUNTIME_CONTEXT = _types.SimpleNamespace(
    attach=_noop, detach=_noop
)
sys.modules["opentelemetry.context"]._LOAD_RUNTIME_CONTEXT = lambda: (
    sys.modules["opentelemetry.context"]._RUNTIME_CONTEXT
)
sys.modules["opentelemetry.context"].Context = _types.SimpleNamespace

import _strptime  # noqa: F401 -- PyInstaller must bundle this eagerly
import os
import sys
from pathlib import Path

import mcp.types  # noqa: F401 -- must be imported before fastmcp touches it

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
else:
    base = Path(__file__).resolve().parent
if str(base / "src") not in sys.path:
    sys.path.insert(0, str(base / "src"))

os.environ.setdefault("MCP_TRANSPORT", "http")

if __name__ == "__main__":
    import uvicorn

    from aiwatcher_mcp.api import app

    host = os.environ.get("AIWATCHER_HOST", "127.0.0.1")
    port = int(
        os.environ.get(
            "AIWATCHER_PORT",
            os.environ.get("AIWATCHER_MCP_PORT", os.environ.get("MCP_PORT", "10946")),
        )
    )
    log_level = os.environ.get("AIWATCHER_LOG_LEVEL", "info")
    uvicorn.run(app, host=host, port=port, log_level=log_level)
