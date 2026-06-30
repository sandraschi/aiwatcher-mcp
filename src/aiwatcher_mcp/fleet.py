import json
import logging
from pathlib import Path

from pydantic import BaseModel

from .config import get_settings

logger = logging.getLogger(__name__)


class FleetApp(BaseModel):
    id: str
    name: str
    port: int
    url: str
    repo_path: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] = []


def discover_fleet_from_docs() -> list[FleetApp]:
    """
    Elicit fleet apps from the mcp-central-docs operations registry.
    """
    settings = get_settings()
    mcd_path = Path(settings.central_docs_path)

    webapp_registry_path = mcd_path / "operations" / "webapp-registry.json"
    fleet_registry_path = mcd_path / "operations" / "fleet-registry.json"

    apps: dict[str, FleetApp] = {}

    # 1. Load webapp registry (primary source for frontend ports)
    if webapp_registry_path.exists():
        try:
            with open(webapp_registry_path, encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("webapps", []):
                    app_id = entry.get("id")
                    if not app_id:
                        continue

                    # Skip items that are explicitly backend or mcp unless they are tagged as sota/frontend
                    tags = entry.get("tags", [])
                    if "frontend" not in tags and "sota" not in tags:
                        # If it's a backend but the only one we have, we might still want to show it?
                        # For now, let's stick to frontend/sota for the dashboard.
                        continue

                    # Build the app object
                    apps[app_id] = FleetApp(
                        id=app_id,
                        name=entry.get("label", app_id),
                        port=entry.get("port", 0),
                        url=f"http://localhost:{entry.get('port', 0)}",
                        repo_path=entry.get("repo_path"),
                        tags=tags,
                    )
        except Exception as e:
            logger.error(f"Error reading webapp-registry.json: {e}")

    # 2. Enrich with fleet-registry metadata
    if fleet_registry_path.exists():
        try:
            with open(fleet_registry_path, encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("fleet", []):
                    app_id = entry.get("id")
                    if app_id in apps:
                        apps[app_id].description = entry.get("description")
                        apps[app_id].category = entry.get("category")
                    elif entry.get("port"):
                        # If it's in fleet-registry but not webapp-registry, maybe it's an MCP-only service
                        # We might still want to track its status.
                        apps[app_id] = FleetApp(
                            id=app_id,
                            name=entry.get("name", app_id),
                            port=entry.get("port"),
                            url=f"http://localhost:{entry.get('port')}",
                            repo_path=entry.get("repo_path"),
                            category=entry.get("category"),
                        )
        except Exception as e:
            logger.error(f"Error reading fleet-registry.json: {e}")

    # Fallback if no registry found
    if not apps:
        logger.warning("No apps discovered from MCD registry. Using fallback.")
        fallback_ports = [
            10704,
            10741,
            10721,
            10848,
            10852,
            10858,
            10834,
            10864,
            10728,
            10752,
            10842,
            10822,
        ]
        for port in fallback_ports:
            apps[str(port)] = FleetApp(
                id=f"app-{port}", name=f"App {port}", port=port, url=f"http://localhost:{port}"
            )

    # Sort by port
    return sorted(apps.values(), key=lambda x: x.port)
