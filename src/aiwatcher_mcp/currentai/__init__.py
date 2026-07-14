"""Current AI Map -- snapshot fetch, storage, diff, and risk checking."""

from __future__ import annotations

from .differ import check_dependency_risk, diff_snapshots, gap_report
from .fetcher import fetch_normalized_products
from .store import get_latest, list_snapshots, load_snapshot, save_snapshot, snapshot_filename

__all__ = [
    "check_dependency_risk",
    "diff_snapshots",
    "gap_report",
    "fetch_normalized_products",
    "get_latest",
    "list_snapshots",
    "load_snapshot",
    "save_snapshot",
    "snapshot_filename",
]
