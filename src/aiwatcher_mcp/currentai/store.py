"""Snapshot storage: write, read, latest pointer management."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "currentai"
_SNAPSHOTS_DIR = _DATA_DIR / "snapshots"
_LATEST_POINTER = _DATA_DIR / "latest.json"


def snapshot_filename(iso_date: str, short_commit: str) -> str:
    return f"{iso_date}_{short_commit}.json"


def save_snapshot(records: list[dict[str, Any]], commit: str) -> Path:
    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    iso_date = datetime.now(UTC).strftime("%Y-%m-%d")
    short = commit[:8]
    filename = snapshot_filename(iso_date, short)
    filepath = _SNAPSHOTS_DIR / filename

    payload: dict[str, Any] = {
        "commit": commit,
        "short_commit": short,
        "fetched_at": datetime.now(UTC).isoformat(),
        "product_count": len(records),
        "products": records,
    }

    filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    _LATEST_POINTER.write_text(
        json.dumps(
            {
                "current": filename,
                "commit": commit,
                "product_count": len(records),
                "updated": payload["fetched_at"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log.info("Snapshot saved: %s (%d products)", filename, len(records))
    return filepath


def get_latest() -> dict[str, Any] | None:
    if not _LATEST_POINTER.exists():
        return None
    return json.loads(_LATEST_POINTER.read_text(encoding="utf-8"))


def load_snapshot(snapshot_id: str | None = None) -> tuple[dict[str, Any], str] | None:
    """Load a snapshot by filename, or the latest if None. Returns (data, filename)."""
    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    if snapshot_id is None:
        latest = get_latest()
        if latest is None:
            return None
        snapshot_id = latest["current"]

    filepath = _SNAPSHOTS_DIR / snapshot_id
    if not filepath.exists():
        return None

    data = json.loads(filepath.read_text(encoding="utf-8"))
    return data, filepath.name


def list_snapshots() -> list[str]:
    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(f.name for f in sorted(_SNAPSHOTS_DIR.glob("*.json"), reverse=True))
