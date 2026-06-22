"""Portfolio / project watch list — keyword hits boost perceived urgency."""

from __future__ import annotations

from aiwatcher_mcp.config import get_settings


def portfolio_terms() -> list[str]:
    cfg = get_settings()
    if not cfg.portfolio_watch_terms.strip():
        return []
    return [t.strip().lower() for t in cfg.portfolio_watch_terms.split(",") if t.strip()]


def portfolio_match(text: str) -> list[str]:
    """Return watch terms found in text (case-insensitive)."""
    if not text:
        return []
    lower = text.lower()
    return [t for t in portfolio_terms() if t in lower]


def portfolio_urgency_boost(base_urgency: float | None, title: str, summary: str) -> float | None:
    """Add a small boost when watch terms appear (cap 10)."""
    if base_urgency is None:
        return None
    hits = portfolio_match(f"{title} {summary}")
    if not hits:
        return base_urgency
    cfg = get_settings()
    boosted = min(10.0, float(base_urgency) + cfg.portfolio_watch_urgency_boost)
    return boosted
