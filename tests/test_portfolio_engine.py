"""Unit tests for portfolio advisory overlay engine."""

from src.portfolio_engine import PortfolioEngine


def _snapshot(max_position=0.10, max_sector=0.30, risk_budget=1.0, by_ticker=None):
    return {
        "profile": {
            "max_position_pct": max_position,
            "max_sector_pct": max_sector,
            "risk_budget_pct": risk_budget,
        },
        "by_ticker": by_ticker or [],
    }


def _diagnostics(quality="good", conflicted=False):
    return {
        "disagreement": {"is_conflicted": conflicted},
        "data_quality": {"quality_level": quality},
    }


def test_buy_maps_to_add_when_constraints_clear():
    engine = PortfolioEngine(_snapshot())
    result = engine.evaluate(
        ticker="AAPL",
        analysis={"recommendation": "BUY"},
        diagnostics=_diagnostics(quality="good", conflicted=False),
    )

    action = result["portfolio_action"]
    assert action["action"] == "add"
    assert action["fit_score"] > 0
    assert any(check["name"] == "max_position" for check in action["constraint_checks"])


def test_poor_quality_with_existing_position_moves_to_hedge():
    engine = PortfolioEngine(
        _snapshot(
            by_ticker=[
                {
                    "ticker": "AAPL",
                    "position_pct": 0.08,
                    "sector_exposure_pct": 0.18,
                }
            ]
        )
    )

    result = engine.evaluate(
        ticker="AAPL",
        analysis={"recommendation": "BUY"},
        diagnostics=_diagnostics(quality="poor", conflicted=True),
    )

    action = result["portfolio_action"]
    assert action["action"] == "hedge"
    quality_check = next(c for c in action["constraint_checks"] if c["name"] == "data_quality_gate")
    assert quality_check["status"] == "fail"


def test_sector_overweight_for_existing_position_trims():
    engine = PortfolioEngine(
        _snapshot(
            max_position=0.20,
            max_sector=0.25,
            by_ticker=[
                {
                    "ticker": "NVDA",
                    "position_pct": 0.14,
                    "sector_exposure_pct": 0.33,
                }
            ],
        )
    )

    result = engine.evaluate(
        ticker="NVDA",
        analysis={"recommendation": "HOLD"},
        diagnostics=_diagnostics(quality="good", conflicted=False),
    )

    assert result["portfolio_action"]["action"] == "trim"


def test_sell_without_position_becomes_hold():
    engine = PortfolioEngine(_snapshot())
    result = engine.evaluate(
        ticker="TSLA",
        analysis={"recommendation": "SELL"},
        diagnostics=_diagnostics(),
    )
    assert result["portfolio_action"]["action"] == "hold"


def test_portfolio_risk_summary_basic():
    """portfolio_risk_summary computes weighted beta and sector concentration."""
    holdings = [
        {"ticker": "AAPL", "shares": 100, "market_value": 18000, "sector": "Technology", "beta": 1.2},
        {"ticker": "JPM", "shares": 50, "market_value": 10000, "sector": "Financials", "beta": 1.1},
        {"ticker": "MSFT", "shares": 30, "market_value": 12000, "sector": "Technology", "beta": 1.0},
    ]
    profile = {"max_position_pct": 0.10, "max_sector_pct": 0.30}

    result = PortfolioEngine.portfolio_risk_summary(holdings, profile)

    assert "portfolio_beta" in result
    assert "total_market_value" in result
    assert result["total_market_value"] == 40000
    assert "sector_concentration" in result
    assert "Technology" in result["sector_concentration"]
    tech_pct = result["sector_concentration"]["Technology"]
    assert abs(tech_pct - 0.75) < 0.01  # (18000+12000)/40000
    assert len(result["sector_breaches"]) > 0  # Technology > 30%


def test_portfolio_risk_summary_empty_holdings():
    """portfolio_risk_summary returns sensible defaults for empty portfolio."""
    result = PortfolioEngine.portfolio_risk_summary([], {})

    assert result["portfolio_beta"] == 0.0
    assert result["total_market_value"] == 0.0
    assert result["sector_concentration"] == {}
    assert result["position_breaches"] == []
    assert result["sector_breaches"] == []


def test_portfolio_risk_summary_position_breach():
    """Holdings exceeding max_position_pct are flagged."""
    holdings = [
        {"ticker": "AAPL", "shares": 100, "market_value": 18000, "sector": "Tech", "beta": 1.2},
        {"ticker": "JPM", "shares": 50, "market_value": 2000, "sector": "Fin", "beta": 1.1},
    ]
    profile = {"max_position_pct": 0.50}

    result = PortfolioEngine.portfolio_risk_summary(holdings, profile)

    assert any(b["ticker"] == "AAPL" for b in result["position_breaches"])
