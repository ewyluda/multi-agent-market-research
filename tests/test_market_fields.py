"""Contract tests: downstream agents must accept real MarketAgent output (campaign A2)."""

import pandas as pd

from src.agents.market_agent import MarketAgent
from src.agents.market_fields import (
    average_volume,
    format_period_change,
    period_change_pct,
    week52_high,
    week52_low,
)
from src.agents.thesis_agent import ThesisAgent


def _real_change():
    """Build a price_change_* value with MarketAgent's own calculator, not a hand-written guess."""
    df = pd.DataFrame({"Close": [100.0, 104.2]})
    agent = MarketAgent.__new__(MarketAgent)
    return agent._calculate_price_change(df)


def test_period_change_reads_market_agent_dict():
    change = _real_change()
    assert isinstance(change, dict)
    assert round(period_change_pct(change), 1) == 4.2
    assert format_period_change(change) == "+4.2%"


def test_period_change_handles_missing_and_legacy_values():
    assert period_change_pct(None) is None
    assert period_change_pct({}) is None
    assert format_period_change(None) == "N/A"
    assert round(period_change_pct(0.05), 6) == 5.0  # legacy fraction
    assert period_change_pct(True) is None


def test_52w_and_volume_prefer_current_keys_with_legacy_fallback():
    current = {"fifty_two_week_high": 220.0, "fifty_two_week_low": 165.0, "average_volume": 5e7}
    legacy = {"high_52w": 210.0, "low_52w": 150.0, "avg_volume": 4e7}
    assert (week52_high(current), week52_low(current), average_volume(current)) == (220.0, 165.0, 5e7)
    assert (week52_high(legacy), week52_low(legacy), average_volume(legacy)) == (210.0, 150.0, 4e7)
    assert week52_high({}) == "N/A"


def test_thesis_market_metrics_accepts_real_market_output():
    data = {
        "current_price": 104.2,
        "fifty_two_week_high": 120.0,
        "fifty_two_week_low": 80.0,
        "average_volume": 12_500_000,
        "price_change_1m": _real_change(),
        "price_change_3m": _real_change(),
    }
    line = ThesisAgent._format_market_metrics(data)
    assert "52w High $120.0" in line
    assert "Vol 12.5M" in line
    assert "1M +4.2%" in line
