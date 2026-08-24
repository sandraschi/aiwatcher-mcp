"""
Interest Bundle logic - handles LLM-driven elicitation for new bundles.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

from aiwatcher_mcp.config import get_settings
from aiwatcher_mcp.distillation import _get_llm_response, _strip_fences

log = logging.getLogger(__name__)
cfg = get_settings()

ELICITATION_SYSTEM = """You are an expert at defining personas and interest profiles for news distillation.
The user will provide a topic (e.g. "dogs", "yachts", "travel").
Generate a concise configuration for an "Interest Bundle" including:
1. A descriptive Name (e.g. "Canine Care & Science")
2. A System Prompt (Persona) that instructs Claude how to score items for this interest. 
   Include criteria for RELEVANCE and URGENCY (0-10).
3. A set of suggested high-quality RSS/Atom feed URLs or blog URLs related to the topic.
   Try to provide real, working feed URLs if possible, or high-probability ones (e.g. /feed/ at the end).

Respond ONLY with valid JSON:
{
  "name": "...",
  "system_prompt": "...",
  "suggested_feeds": [
    {"name": "Name of Source", "url": "https://example.com/feed", "type": "rss"}
  ]
}
"""


def get_bundles_json_path() -> str:
    return os.path.join(cfg.central_docs_path, "operations", "bundles.json")


def load_fleet_bundles() -> list[dict]:
    path = get_bundles_json_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("bundles", [])
    except Exception as e:
        log.error("Failed to load bundles from %s: %s", path, e)
        return []


def save_fleet_bundles(bundles: list[dict]):
    path = get_bundles_json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"bundles": bundles}, f, indent=2)
    except Exception as e:
        log.error("Failed to save bundles to %s: %s", path, e)


async def elicit_bundle_config(topic: str) -> dict:
    """Use LLM to generate a bundle persona from a topic keyword."""
    prompt = f"Topic: {topic}\nGenerate a high-fidelity bundle configuration."

    try:
        raw = await _get_llm_response(ELICITATION_SYSTEM, prompt, max_tokens=2048)
        log.debug("Raw bundle elicitation response: %s", raw)
        data = json.loads(_strip_fences(raw))
    except Exception as exc:
        log.error(
            "Bundle elicitation failed for %s: %s. Raw response: %s",
            topic,
            exc,
            locals().get("raw", "N/A"),
        )
        return {
            "name": topic.capitalize(),
            "system_prompt": f"You are an expert on {topic}. Score items for interest and urgency related to {topic}.",
            "suggested_feeds": [],
        }

    data["suggested_feeds"] = await _probe_feed_urls(data.get("suggested_feeds", []))
    return data


async def find_feeds_for_topic(topic: str) -> dict:
    """Elicit bundle config AND probe/verify feed URLs end-to-end."""
    config = await elicit_bundle_config(topic)
    return config


FEED_FALLBACK_PATHS = [
    "/feed/",
    "/rss/",
    "/index.xml",
    "/atom.xml",
    "/feed.xml",
    "/blog/feed/",
    "/feed",
    "/rss",
]


async def _probe_feed_urls(suggested_feeds: list[dict]) -> list[dict]:
    """Probe each suggested feed URL with httpx+feedparser; keep only working ones.
    For broken URLs, try common feed path variants on the same domain."""
    import httpx

    verified = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for feed in suggested_feeds[:12]:
            url = feed.get("url", "").strip()
            if not url.startswith("http"):
                continue
            if await _verify_feed_url(client, url):
                feed["verified"] = True
                verified.append(feed)
                continue
            domain = _extract_domain(url)
            if not domain:
                continue
            for path in FEED_FALLBACK_PATHS:
                fallback = f"{domain.rstrip('/')}{path}"
                if await _verify_feed_url(client, fallback):
                    verified.append(
                        {
                            "name": feed.get("name", "Discovered Feed"),
                            "url": fallback,
                            "type": "rss",
                            "verified": True,
                            "original_url": url,
                        }
                    )
                    break

    for feed in suggested_feeds[len(verified) :]:
        feed["verified"] = False
        verified.append(feed)

    return verified


async def _verify_feed_url(client: httpx.AsyncClient, url: str) -> bool:
    """Check if a URL returns valid RSS/Atom content."""
    import feedparser

    try:
        resp = await client.get(url, headers={"User-Agent": "aiwatcher-mcp/0.2"})
        if resp.status_code not in (200, 301, 302, 307, 308):
            return False
        parsed = feedparser.parse(resp.text)
        return bool(parsed.entries)
    except Exception:
        return False


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
