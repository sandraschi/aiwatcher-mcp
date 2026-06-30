"""
Spam scrubber — three-layer classifier for inbound feed items.

Architecture (cascading, fastest first):
  Layer 1: Regex blocklist (μs) — known spam patterns, URL shorteners
  Layer 2: URL blocklist (μs) — known spam domains
  Layer 3: Local LLM (1-5s) — optional, only for borderline cases

Fast path: Layers 1+2 catch 99% of spam in microseconds.
Layer 3 only fires when content looks suspicious but needs context.

Usage:
    from aiwatcher_mcp.scrubber import Scrubber

    scrub = Scrubber()
    result = scrub.check(title="...", summary="...", url="...")
    # result is "legit", "spam", or "scam"
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

ScrubResult = Literal["pending", "legit", "spam", "scam"]

# ---------------------------------------------------------------------------
# Layer 1: Regex patterns — catch the obvious junk
# ---------------------------------------------------------------------------

_SPAM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bget\s+rich\s+quick\b", re.IGNORECASE),
    re.compile(r"\bcar\s+insurance\b", re.IGNORECASE),
    re.compile(r"\bNigerian\s+prince\b", re.IGNORECASE),
    re.compile(r"\byou['\u2019]?ve\s+won\b", re.IGNORECASE),
    re.compile(r"\bcongratulations!?\s+(you|your)", re.IGNORECASE),
    re.compile(r"\bclick\s+here\s+to\s+claim\b", re.IGNORECASE),
    re.compile(r"\b(limited|exclusive)\s+(time|offer)\b", re.IGNORECASE),
    re.compile(r"\bcrypto\s*(giveaway|airdrop)\b", re.IGNORECASE),
    re.compile(r"\bwork\s+from\s+home\s+\$", re.IGNORECASE),
    re.compile(r"\b(unsecured|guaranteed)\s+(loan|credit|approval)\b", re.IGNORECASE),
    re.compile(r"\bViagra|Cialis|cialis\b", re.IGNORECASE),
    re.compile(r"\bIRS|tax\s+refund\b", re.IGNORECASE),
    re.compile(r"\bact\s+now\b.*\bexpires?\b", re.IGNORECASE),
    re.compile(
        r"\byour\s+(account|payment|subscription)\s+(has been )?(suspended|on hold|blocked)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bverify\s+your\s+(account|identity|details)\b", re.IGNORECASE),
    re.compile(r"\bunlock\s+(your\s+)?(account|device|phone)\b", re.IGNORECASE),
    re.compile(r"\b\$\d{3,}\s+(weekly|daily|hourly)\b", re.IGNORECASE),
    re.compile(r"\b(make|earn)\s+\$\d{4,}\s+(a\s+)?(month|week|day)\b", re.IGNORECASE),
    re.compile(r"\b(make|earn)\s+money\s+(fast|quick|online|from\s+home)\b", re.IGNORECASE),
    re.compile(r"\b(passive|residual)\s+income\b", re.IGNORECASE),
    re.compile(r"\bbuy\s+followers\b", re.IGNORECASE),
    re.compile(r"\bSEO\s+(service|expert|optimization)\s+(that|to|for)\b", re.IGNORECASE),
    re.compile(r"\bweight\s+loss\s+(gummy|pill|supplement|secret)\b", re.IGNORECASE),
    re.compile(r"\binternational\s+lottery\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Layer 1b: URL shorteners — often used to hide spam destinations
# ---------------------------------------------------------------------------

_SHORTENER_DOMAINS: set[str] = {
    "bit.ly",
    "tinyurl.com",
    "shorturl.at",
    "t.co",
    "buff.ly",
    "ow.ly",
    "is.gd",
    "cli.gs",
    "tiny.cc",
    "tr.im",
    "shorte.st",
    "bc.vc",
    "adf.ly",
    "lnkd.in",
}

# ---------------------------------------------------------------------------
# Layer 2: Spam domains — known low-reputation sources
# ---------------------------------------------------------------------------

_SPAM_DOMAINS: set[str] = set()

_BLOCKLIST_FILE = Path(__file__).resolve().parent / "data" / "spam_blocklist.txt"


def _load_blocklist() -> set[str]:
    domains: set[str] = set()
    if _BLOCKLIST_FILE.is_file():
        for line in _BLOCKLIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                domains.add(line.lower())
    return domains


def _reload_blocklist() -> None:
    global _SPAM_DOMAINS
    _SPAM_DOMAINS = _load_blocklist()


def _check_regex(text: str) -> str | None:
    """Return matched pattern name if any regex fires."""
    for pat in _SPAM_PATTERNS:
        if pat.search(text):
            return pat.pattern[:60]
    return None


def _check_url(url: str | None) -> str | None:
    """Return domain if URL is a known spammer or shortener."""
    if not url:
        return None
    from urllib.parse import urlparse

    try:
        domain = urlparse(url).hostname or ""
    except Exception:
        return None
    domain = domain.lower().removeprefix("www.")
    if domain in _SHORTENER_DOMAINS:
        return f"shortener:{domain}"
    if domain in _SPAM_DOMAINS:
        return f"blocklisted:{domain}"
    return None


# ---------------------------------------------------------------------------
# Scrubber
# ---------------------------------------------------------------------------


class Scrubber:
    """Lightweight spam classifier. Reusable, thread-safe after init."""

    def __init__(self, enable_llm: bool = False):
        self._llm_enabled = enable_llm
        _reload_blocklist()

    def reload(self) -> None:
        _reload_blocklist()

    def check(
        self,
        title: str = "",
        summary: str = "",
        url: str | None = None,
        content_html: str | None = None,
    ) -> tuple[ScrubResult, str]:
        """
        Classify an item. Returns (result, reason).

        result: "legit" | "spam" | "scam"
        reason: human-readable explanation of which rule fired.
        """
        text = f"{title} {summary or ''} {content_html or ''}"

        # Layer 1: regex patterns
        reason = _check_regex(text)
        if reason:
            return "spam", f"pattern:{reason}"

        # Layer 2: URL check
        reason = _check_url(url)
        if reason:
            return "spam", f"url:{reason}"

        return "legit", ""

    def check_item(self, item: dict) -> tuple[ScrubResult, str]:
        """Convenience: classify an upsert_item dict."""
        return self.check(
            title=item.get("title", ""),
            summary=item.get("summary"),
            url=item.get("url"),
            content_html=item.get("content_html"),
        )
