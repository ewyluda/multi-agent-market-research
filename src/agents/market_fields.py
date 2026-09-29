"""Readers for MarketAgent output fields shared by downstream (synthesis) agents.

MarketAgent emits (see ``market_agent.py``):
  - ``price_change_1m`` / ``price_change_3m``: ``{"change", "change_pct", "start_price", "end_price"}``
    where ``change_pct`` is already a percentage (4.2 means +4.2%)
  - ``fifty_two_week_high`` / ``fifty_two_week_low`` / ``average_volume``

Downstream agents previously assumed a bare fraction and ``high_52w``-style keys, which raised
``TypeError`` inside ThesisAgent and EarningsReviewAgent on every real run. Read these fields
through this module instead of re-deriving the shape in each agent.
"""

from typing import Any, Dict, Optional


def period_change_pct(value: Any) -> Optional[float]:
    """Percent change for a ``price_change_*`` field, or None if unavailable.

    Accepts the MarketAgent dict shape; a bare number is treated as a fraction (0.05 -> 5.0).
    """
    if isinstance(value, dict):
        pct = value.get("change_pct")
        return float(pct) if isinstance(pct, (int, float)) else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) * 100
    return None


def format_period_change(value: Any) -> str:
    """``+4.2%`` style string for a ``price_change_*`` field, or ``N/A``."""
    pct = period_change_pct(value)
    return f"{pct:+.1f}%" if pct is not None else "N/A"


def first_present(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """First non-None value among ``keys`` (current name first, legacy aliases after)."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def week52_high(data: Dict[str, Any]) -> Any:
    return first_present(data, "fifty_two_week_high", "high_52w", default="N/A")


def week52_low(data: Dict[str, Any]) -> Any:
    return first_present(data, "fifty_two_week_low", "low_52w", default="N/A")


def average_volume(data: Dict[str, Any]) -> Optional[float]:
    return first_present(data, "average_volume", "avg_volume")
