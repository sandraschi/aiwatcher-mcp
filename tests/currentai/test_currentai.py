"""Unit tests for currentai module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiwatcher_mcp.currentai import diff_snapshots, gap_report

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def s1() -> dict:
    return _load("snap1.json")


@pytest.fixture
def s2() -> dict:
    return _load("snap2.json")


# ── differ ──────────────────────────────────────────────────────────────────────


def test_diff_added(s1, s2):
    r = diff_snapshots(s1, s2)
    assert len(r["added"]) == 1
    assert r["added"][0]["product"] == "NewHotness"


def test_diff_removed_none(s1, s2):
    r = diff_snapshots(s1, s2)
    assert len(r["removed"]) == 0


def test_diff_removed_when_dropped():
    older = {"products": [
        {"product": "A", "stack_layer": "L1", "openness_class": "os", "adoption_level": 4, "maturity": 5},
        {"product": "B", "stack_layer": "L1", "openness_class": "cs", "adoption_level": 2, "maturity": 0},
    ]}
    newer = {"products": [
        {"product": "A", "stack_layer": "L1", "openness_class": "os", "adoption_level": 4, "maturity": 5},
    ]}
    r = diff_snapshots(older, newer)
    assert len(r["removed"]) == 1
    assert r["removed"][0]["product"] == "B"


def test_diff_openness_reclassified(s1, s2):
    r = diff_snapshots(s1, s2)
    mock = [x for x in r["openness_reclassified"] if x["product"] == "Mockformer-9000"]
    assert len(mock) == 1
    assert mock[0]["old_class"] == "open_source"
    assert mock[0]["new_class"] == "restricted"
    ds = [x for x in r["openness_reclassified"] if x["product"] == "DeepSeek-V4-Pro-Base"]
    assert len(ds) == 1
    assert ds[0]["old_class"] == "open_weights"
    assert ds[0]["new_class"] == "open_source"


def test_diff_adoption_changed(s1, s2):
    r = diff_snapshots(s1, s2)
    ad = {(x["product"], x["old_level"], x["new_level"]) for x in r["adoption_changed"]}
    assert ("DeepSeek-V4-Pro-Base", 4, 5) in ad
    assert ("ClosedCorp", 4, 3) in ad
    assert ("Joe Mocky's Inference Engine", 3, 4) in ad


def test_diff_empty():
    recs = [{"product": "A", "stack_layer": "L1", "openness_class": "os", "adoption_level": 4, "maturity": 5}]
    older = {"products": recs}
    newer = {"products": [dict(recs[0])]}
    r = diff_snapshots(older, newer)
    assert r["total_changes"] == 0
    assert len(r["added"]) == 0
    assert len(r["removed"]) == 0
    assert len(r["openness_reclassified"]) == 0
    assert len(r["adoption_changed"]) == 0


# ── gap_report ──────────────────────────────────────────────────────────────────


def test_gap_report(s1):
    r = gap_report(s1.get("products", []))
    assert r["total_products"] == 5
    assert len(r["layers"]) >= 2


# ── store ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    import aiwatcher_mcp.currentai.store as sm

    monkeypatch.setattr(sm, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(sm, "_SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(sm, "_LATEST_POINTER", tmp_path / "latest.json")
    return tmp_path


def test_save_and_load(tmp_store, s1):
    from aiwatcher_mcp.currentai.store import get_latest, load_snapshot, save_snapshot

    path = save_snapshot(s1["products"], s1["commit"])
    assert Path(path).exists()

    latest = get_latest()
    assert latest is not None
    assert latest["commit"] == s1["commit"]

    result = load_snapshot()
    assert result is not None
    data, name = result
    assert data["product_count"] == 5
    assert data["products"] == s1["products"]


def test_list_snapshots(tmp_store, s1):
    from aiwatcher_mcp.currentai.store import list_snapshots, save_snapshot

    save_snapshot(s1["products"], s1["commit"])
    snaps = list_snapshots()
    assert len(snaps) == 1
    assert snaps[0].endswith(".json")


def test_load_specific(tmp_store, s1):
    from aiwatcher_mcp.currentai.store import list_snapshots, load_snapshot, save_snapshot

    save_snapshot(s1["products"], s1["commit"])
    snaps = list_snapshots()
    r = load_snapshot(snaps[0])
    assert r is not None
    assert r[1] == snaps[0]


def test_filename_format():
    from aiwatcher_mcp.currentai.store import snapshot_filename

    assert snapshot_filename("2026-07-05", "abc123ab") == "2026-07-05_abc123ab.json"


def test_get_latest_none(tmp_store):
    from aiwatcher_mcp.currentai.store import get_latest

    assert get_latest() is None


# ── watchlist matching logic ────────────────────────────────────────────────────


def test_watchlist_match():
    products = [
        {"product": "vLLM", "slug": "vllm"},
        {"product": "Ollama", "slug": "ollama"},
    ]
    entries = ["vllm", "ollama"]
    for entry in entries:
        q = entry.lower()
        matches = [p for p in products if q in p.get("product", "").lower()]
        assert len(matches) == 1


def test_watchlist_no_match():
    products = [{"product": "vLLM", "slug": "vllm"}]
    matches = [p for p in products if "nonexistent" in p.get("product", "").lower()]
    assert len(matches) == 0


def test_watchlist_ambiguous():
    products = [{"product": "Qwen 2.5", "slug": "qwen-2-5"}, {"product": "Qwen 3", "slug": "qwen-3"}]
    matches = [p for p in products if "qwen" in p.get("product", "").lower()]
    assert len(matches) == 2


def test_concentration_risk():
    products = [
        {"product": "A", "stack_layer": "L1", "openness_bucket": "open"},
        {"product": "B", "stack_layer": "L1", "openness_bucket": "open"},
        {"product": "C", "stack_layer": "L1", "openness_bucket": "closed"},
    ]
    open_count = sum(1 for p in products
                     if p["stack_layer"] == "L1" and p["openness_bucket"] == "open")
    assert open_count == 2  # < 3 → risk


def test_concentration_sufficient():
    products = [
        {"product": "A", "stack_layer": "L1", "openness_bucket": "open"},
        {"product": "B", "stack_layer": "L1", "openness_bucket": "open"},
        {"product": "C", "stack_layer": "L1", "openness_bucket": "open"},
        {"product": "D", "stack_layer": "L1", "openness_bucket": "closed"},
    ]
    open_count = sum(1 for p in products
                     if p["stack_layer"] == "L1" and p["openness_bucket"] == "open")
    assert open_count >= 3
