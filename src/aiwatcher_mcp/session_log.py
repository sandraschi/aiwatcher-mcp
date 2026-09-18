"""AIWatcher's provenance-marked entries in the fleet session log.

Invokes mcp-central-docs' shared appender script as a subprocess (fleet
convention for cross-repo scripts). Writes to the 'aiwatcher' sink, not the
main session log - AIWatcher's own digests run long/frequent enough to swamp
everything else if mixed in with coding-agent and Fritz entries. Keep the
BODY short here too (subject + item count), even in its own file - the
separate sink protects other sources, it isn't licence to dump the full
digest text.

Best-effort: a session-log write must never block or break the digest job.
See mcp-central-docs/operations/session-log/README.md for the convention.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_UV = r"C:\Users\sandr\.local\bin\uv.exe"
_APPENDER = Path(r"D:\Dev\repos\mcp-central-docs\scripts\session-log-append.py")


def log_digest_published(subject: str, item_count: int, hub_published: bool) -> None:
    """Log a completed daily digest run. Best-effort - swallows all errors."""
    if not _APPENDER.exists():
        return
    title = "Daily digest generated"
    body = (
        f"- {subject}\n"
        f"- {item_count} item(s) distilled.\n"
        f"- Intel Hub publish: {'ok' if hub_published else 'skipped/failed'}.\n"
        f"- Full digest content is in email/Intel Hub, not duplicated here."
    )
    try:
        subprocess.run(
            [
                _UV,
                "run",
                "python",
                str(_APPENDER),
                "--agent",
                "AIWatcher",
                "--category",
                "heartbeat",
                "--title",
                title,
                "--body",
                body,
                "--sink",
                "aiwatcher",
            ],
            cwd=str(_APPENDER.parent.parent),
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception:
        logger.debug("session-log append failed (non-fatal)", exc_info=True)
