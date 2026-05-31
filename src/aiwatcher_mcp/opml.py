"""OPML feed import — shared by MCP tool and REST API."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from aiwatcher_mcp.database import get_db


async def import_feeds_from_opml(opml_xml: str) -> dict:
    """
    Parse OPML and insert feeds with xmlUrl into the database.

    Returns:
        {"imported": list[dict], "count": int}
    """
    root = ET.fromstring(opml_xml)
    imported: list[dict] = []

    for outline in root.iter("outline"):
        xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
        title = outline.get("title") or outline.get("text") or "OPML Import"
        if not xml_url:
            continue
        async with get_db() as db:
            try:
                cur = await db.execute(
                    "INSERT INTO feeds(name, url, feed_type) VALUES (?,?,?)",
                    (title, xml_url, "rss"),
                )
                await db.commit()
                imported.append({"id": cur.lastrowid, "name": title, "url": xml_url})
            except Exception:
                pass

    return {"imported": imported, "count": len(imported)}
