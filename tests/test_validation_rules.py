"""Tests for the deterministic validation rule engine."""

import pytest
from src.validation_rules import validate


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_final_analysis(recommendation="BUY", score=65, confidence=0.78):
    return {
        "recommendation": recommendation,
        "score": score,
        "confidence": confidence,
        "reasoning": "Strong fundamentals and technicals.",
        "decision_card": {
            "entry_zone": {"low": 175.0, "high": 185.0, "reference": 180.0},
            "stop_loss": 170.0,
            "targets": [195.0, 210.0],
        },
        "scenarios": {
            "bull": {"probability": 0.4, "expected_return_pct": 15.0},
            "base": {"probability": 0.4, "expected_return_pct": 5.0},
            "bear": {"probability": 0.2, "expected_return_pct": -10.0},
        },
        "signal_snapshot": {
            "recommendation": recommendation,
            "market_regime": "bullish",
            "macro_risk_environment": "risk_on",
            "macro_cycle": "expansion",
        },
    }


def _make_agent_results(
    market_direction="bullish",
    fundamentals_direction="bullish",
    technical_direction="bullish",
    macro_direction="bullish",
    options_direction="bullish",
    sentiment_direction="bullish",
):
    """Build agent_results with controllable directions."""
    return {
        "market": {
            "success": True,
            "data": {
                "current_price": 180.0,
                "trend": market_direction,
                "price_change_1m": {"change_pct": 5.0 if market_direction == "bullish" else -5.0},
            },
        },
        "fundamentals": {
            "success": True,
            "data": {
                "health_score": 75 if fundamentals_direction == "bullish" else 30,
                "key_metrics": {
                    "pe_ratio": 22.0,
                    "revenue_growth": 0.18,
                    "free_cash_flow": 5000000000,
                    "debt_to_equity": 1.2,
                },
            },
        },
        "technical": {
            "success": True,
            "data": {
                "rsi": 55.0 if technical_direction == "bullish" else 75.0,
                "signals": {
                    "overall": "buy" if technical_direction == "bullish" else "sell",
                    "strength": 40.0 if technical_direction == "bullish" else -40.0,
                },
            },
        },
        "macro": {
            "success": True,
            "data": {
                "economic_cycle": "expansion" if macro_direction == "bullish" else "contraction",
                "risk_environment": "risk_on" if macro_direction == "bullish" else "risk_off",
                "fed_funds_rate": 4.5,
                "yield_curve_spread": 0.5 if macro_direction == "bullish" else -0.3,
            },
        },
        "options": {
            "success": True,
            "data": {
                "put_call_ratio": 0.7 if options_direction == "bullish" else 1.8,
                "overall_signal": options_direction,
                "unusual_activity": [],
            },
        },
        "sentiment": {
            "success": True,
            "data": {
                "overall_sentiment": 0.4 if sentiment_direction == "bullish" else -0.4,
            },
        },
    }


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestValidateClean:
    """When all data aligns, validation should be clean."""

    def test_clean_report(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(),
        )
        assert report["contradictions"] == 0
        assert report["total_confidence_penalty"] == 0.0

    def test_report_structure(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(),
        )
        assert "total_rules_checked" in report
        assert "passed" in report
        assert "warnings" in report
        assert "contradictions" in report
        assert "results" in report
        assert "total_confidence_penalty" in report


class TestDirectionConsistency:
    """Solution recommendation should align with majority agent direction."""

    def test_buy_with_majority_bearish_is_contradiction(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(
                market_direction="bearish",
                fundamentals_direction="bearish",
                technical_direction="bearish",
                options_direction="bearish",
            ),
        )
        contradictions = [r for r in report["results"] if r["rule_id"] == "direction_consistency" and not r["passed"]]
        assert len(contradictions) >= 1
        assert contradictions[0]["severity"] == "contradiction"

    def test_sell_with_majority_bullish_is_contradiction(self):
        report = validate(
            final_analysis=_make_final_analysis("SELL"),
            agent_results=_make_agent_results(),
        )
        contradictions = [r for r in report["results"] if r["rule_id"] == "direction_consistency" and not r["passed"]]
        assert len(contradictions) >= 1

    def test_hold_with_mixed_signals_is_clean(self):
        report = validate(
            final_analysis=_make_final_analysis("HOLD"),
            agent_results=_make_agent_results(
                market_direction="bullish",
                fundamentals_direction="bearish",
                technical_direction="bullish",
            ),
        )
        direction_results = [r for r in report["results"] if r["rule_id"] == "direction_consistency"]
        for r in direction_results:
            assert r["passed"]


class TestRegimeConsistency:
    """Signal snapshot regime should match macro agent output."""

    def test_risk_on_with_contraction_is_warning(self):
        analysis = _make_final_analysis("BUY")
        analysis["signal_snapshot"]["macro_risk_environment"] = "risk_on"
        report = validate(
            final_analysis=analysis,
            agent_results=_make_agent_results(macro_direction="bearish"),
        )
        regime_issues = [r for r in report["results"] if r["rule_id"] == "regime_consistency" and not r["passed"]]
        assert len(regime_issues) >= 1


class TestOptionsAlignment:
    """BUY with heavy put volume should flag."""

    def test_buy_with_high_put_call_ratio(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(options_direction="bearish"),
        )
        options_issues = [r for r in report["results"] if r["rule_id"] == "options_alignment" and not r["passed"]]
        assert len(options_issues) >= 1


class TestTechnicalAlignment:
    """Entry zone should not be set above resistance when RSI is overbought."""

    def test_entry_with_overbought_rsi(self):
        analysis = _make_final_analysis("BUY")
        agent_results = _make_agent_results(technical_direction="bearish")
        report = validate(final_analysis=analysis, agent_results=agent_results)
        tech_issues = [r for r in report["results"] if r["rule_id"] == "technical_alignment" and not r["passed"]]
        assert len(tech_issues) >= 1


class TestPenaltyCapping:
    """Total penalty should be capped at 0.40."""

    def test_many_contradictions_capped(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(
                market_direction="bearish",
                fundamentals_direction="bearish",
                technical_direction="bearish",
                macro_direction="bearish",
                options_direction="bearish",
                sentiment_direction="bearish",
            ),
        )
        assert report["total_confidence_penalty"] <= 0.40
