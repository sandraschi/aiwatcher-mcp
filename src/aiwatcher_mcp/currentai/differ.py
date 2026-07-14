"""Diff engine for Current AI snapshots."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _to_list(records: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize input: accept either a dict with 'products' key or a list."""
    if isinstance(records, dict):
        return records.get("products", records.get("records", []))
    return records


def _build_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["product"]: r for r in records}


def diff_snapshots(
    before: list[dict[str, Any]] | dict[str, Any],
    after: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, Any]:
    """Compare two product lists and return categorized changes.

    Accepts either lists of product dicts or dicts with a 'products' key.
    """
    b_list = _to_list(before)
    a_list = _to_list(after)

    idx_before = _build_index(b_list)
    idx_after = _build_index(a_list)
    before_keys = set(idx_before)
    after_keys = set(idx_after)

    result: dict[str, Any] = {
        "added": [],
        "removed": [],
        "openness_reclassified": [],
        "stage_changed": [],
        "adoption_changed": [],
        "before_count": len(b_list),
        "after_count": len(a_list),
        "is_empty": False,
    }

    for name in sorted(after_keys - before_keys):
        result["added"].append({"product": name, **(idx_after[name])})

    for name in sorted(before_keys - after_keys):
        result["removed"].append({"product": name, **(idx_before[name])})

    for name in sorted(before_keys & after_keys):
        old = idx_before[name]
        new = idx_after[name]

        old_oc = old.get("openness_class", "")
        new_oc = new.get("openness_class", "")
        if old_oc != new_oc:
            result["openness_reclassified"].append(
                {
                    "product": name,
                    "old_class": old_oc,
                    "new_class": new_oc,
                    "old_bucket": old.get("openness_bucket", ""),
                    "new_bucket": new.get("openness_bucket", ""),
                }
            )

        old_stage = old.get("openness_score") or old.get("maturity") or 0
        new_stage = new.get("openness_score") or new.get("maturity") or 0
        if old_stage != new_stage:
            result["stage_changed"].append(
                {
                    "product": name,
                    "old_score": old_stage,
                    "new_score": new_stage,
                    "old_maturity": old.get("maturity_stage_num"),
                    "new_maturity": new.get("maturity_stage_num"),
                }
            )

        old_al = old.get("adoption_level")
        new_al = new.get("adoption_level")
        if old_al != new_al:
            result["adoption_changed"].append(
                {
                    "product": name,
                    "old_level": old_al,
                    "new_level": new_al,
                }
            )

    total = sum(
        len(result[k])
        for k in ("added", "removed", "openness_reclassified", "stage_changed", "adoption_changed")
    )
    result["is_empty"] = total == 0
    result["total_changes"] = total
    log.info(
        "Diff: +%d -%d open=%d stage=%d adopt=%d (empty=%s)",
        len(result["added"]),
        len(result["removed"]),
        len(result["openness_reclassified"]),
        len(result["stage_changed"]),
        len(result["adoption_changed"]),
        result["is_empty"],
    )
    return result


def gap_report(products: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Return per-layer openness breakdown."""
    plist = _to_list(products)
    layers: dict[str, dict[str, int]] = {}
    for p in plist:
        layer = p.get("stack_layer", "unknown")
        bucket = p.get("openness_bucket", "")
        if layer not in layers:
            layers[layer] = {"open": 0, "openish": 0, "closed": 0}
        if bucket == "open":
            layers[layer]["open"] += 1
        elif bucket in ("openish", "open-ish"):
            layers[layer]["openish"] += 1
        elif bucket == "closed":
            layers[layer]["closed"] += 1

    layer_list = [
        {
            "layer": layer_name,
            "open": c["open"],
            "openish": c["openish"],
            "closed": c["closed"],
            "total": c["open"] + c["openish"] + c["closed"],
        }
        for layer_name, c in sorted(layers.items())
    ]
    return {"layers": layer_list, "total_layers": len(layer_list), "total_products": len(plist)}


def check_dependency_risk(
    products: list[dict[str, Any]] | dict[str, Any],
    prev_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Check watchlist entries, return risk flags.

    Watchlist is defined in data/currentai/watchlist.json.
    """
    plist = _to_list(products)
    prev_products: list[dict[str, Any]] = []
    if prev_snapshot:
        prev_products = _to_list(prev_snapshot)
    prev_idx = {p.get("product", ""): p for p in prev_products}

    layer_open_counts: dict[str, int] = {}
    for p in plist:
        if p.get("openness_bucket") == "open":
            layer = p.get("stack_layer", "")
            layer_open_counts[layer] = layer_open_counts.get(layer, 0) + 1

    import json
    from pathlib import Path

    _wl_path = Path(__file__).resolve().parents[3] / "data" / "currentai" / "watchlist.json"
    _watchlist: list[str] = []
    if _wl_path.exists():
        _watchlist = json.loads(_wl_path.read_text()).get("entries", [])

    results: list[dict[str, Any]] = []
    for entry in _watchlist:
        q = entry.lower()
        hits = [p for p in plist if q in p.get("product", "").lower()]
        flags: list[str] = []

        if not hits:
            flags.append(f"NOT FOUND: '{entry}'")
        elif len(hits) > 1:
            names = [h["product"] for h in hits]
            flags.append(f"AMBIGUOUS: '{entry}' matched {names}")
        else:
            p = hits[0]
            layer = p.get("stack_layer", "")
            bucket = p.get("openness_bucket", "")
            if bucket != "open":
                flags.append(f"NOT FULLY OPEN: '{p['product']}' is {bucket}")
            open_count = layer_open_counts.get(layer, 0)
            if open_count < 3 and bucket == "open":
                flags.append(f"CONCENTRATION RISK: only {open_count} fully-open in '{layer}'")
            if p["product"] in prev_idx:
                old_bucket = prev_idx[p["product"]].get("openness_bucket")
                if old_bucket and old_bucket != bucket:
                    flags.append(f"BUCKET CHANGED: {old_bucket} -> {bucket}")

        results.append(
            {
                "entry": entry,
                "matched": bool(hits) and len(hits) == 1,
                "product": hits[0]["product"] if hits and len(hits) == 1 else None,
                "flags": flags if flags else ["OK"],
                "flagged": len(flags) > 0 and flags != ["OK"],
            }
        )

    return results
