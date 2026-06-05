"""Tests for fleet.py — discover_fleet_from_docs with mock registries."""

from __future__ import annotations

import json


def test_discover_fleet_from_docs(tmp_path, monkeypatch):
    import aiwatcher_mcp.config as cfg_mod
    import aiwatcher_mcp.fleet as fleet_mod

    ops = tmp_path / "operations"
    ops.mkdir()
    (ops / "webapp-registry.json").write_text(
        json.dumps(
            {
                "webapps": [
                    {
                        "id": "demo-mcp",
                        "label": "Demo MCP",
                        "port": 10999,
                        "tags": ["frontend", "sota"],
                        "repo_path": "D:/Dev/repos/demo-mcp",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (ops / "fleet-registry.json").write_text(
        json.dumps(
            {
                "fleet": [
                    {
                        "id": "demo-mcp",
                        "description": "Demo server",
                        "category": "ai",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CENTRAL_DOCS_PATH", str(tmp_path))
    cfg_mod._settings = None

    apps = fleet_mod.discover_fleet_from_docs()

    assert len(apps) >= 1
    demo = next(a for a in apps if a.id == "demo-mcp")
    assert demo.port == 10999
    assert demo.description == "Demo server"
    assert demo.category == "ai"
