"""Tests for LLM output guardrails and structured transcript extraction.

Run:
    python -m pytest tests/test_llm_guardrails.py -v
"""

import pytest

from src.llm_guardrails import (
    validate_price_targets,
    validate_sentiment,
    validate_scenarios,
    validate_equity_research,
)
from src.agents.fundamentals_agent import FundamentalsAgent
from src.validation_rules import validate as run_validation


# ═══════════════════════════════════════════════
# Price Target Guardrails
# ═══════════════════════════════════════════════


class TestPriceTargetGuardrails:
    """validate_price_targets — clamp hallucinated price levels."""

    def test_clamp_stop_loss_above_entry(self):
        targets = {"entry": 190.0, "target": 210.0, "stop_loss": 200.0}
        result, warnings = validate_price_targets(targets, current_price=185.0)
        assert result["stop_loss"] < result["entry"]
        assert len(warnings) >= 1
        assert "stop_loss" in warnings[0].lower() or "Stop loss" in warnings[0]

    def test_clamp_stop_loss_below_floor(self):
        targets = {"entry": 100.0, "target": 120.0, "stop_loss": 40.0}
        result, warnings = validate_price_targets(targets, current_price=100.0)
        assert result["stop_loss"] >= 50.0  # 50% of current_price
        assert any("50%" in w or "below" in w.lower() for w in warnings)

    def test_clamp_target_above_ceiling(self):
        targets = {"entry": 100.0, "target": 250.0, "stop_loss": 90.0}
        result, warnings = validate_price_targets(targets, current_price=100.0)
        assert result["target"] <= 200.0  # 2x current_price
        assert any("ceiling" in w.lower() or "exceeds" in w.lower() for w in warnings)

    def test_clamp_target_with_analyst_high(self):
        targets = {"entry": 100.0, "target": 250.0, "stop_loss": 90.0}
        result, warnings = validate_price_targets(
            targets, current_price=100.0, analyst_estimates={"target_high": 220.0}
        )
        # Ceiling is max(200, 220) = 220
        assert result["target"] <= 220.0
        assert len(warnings) >= 1

    def test_passthrough_valid(self):
        targets = {"entry": 100.0, "target": 115.0, "stop_loss": 93.0}
        result, warnings = validate_price_targets(targets, current_price=100.0)
        assert result["entry"] == 100.0
        assert result["target"] == 115.0
        assert result["stop_loss"] == 93.0
        assert warnings == []


# ═══════════════════════════════════════════════
# Sentiment Guardrails
# ═══════════════════════════════════════════════


class TestSentimentGuardrails:
    """validate_sentiment — clamp out-of-bounds LLM sentiment scores."""

    def test_clamp_out_of_bounds(self):
        result = {"overall_sentiment": 1.5, "confidence": 1.2}
        validated, warnings = validate_sentiment(result)
        assert validated["overall_sentiment"] == 1.0
        assert validated["confidence"] == 1.0
        assert len(warnings) >= 2

    def test_weight_normalization(self):
        result = {
            "overall_sentiment": 0.5,
            "confidence": 0.8,
            "factors": {
                "earnings": {"score": 0.5, "weight": 0.5, "contribution": 0.25},
                "guidance": {"score": 0.3, "weight": 0.5, "contribution": 0.15},
                "news": {"score": 0.2, "weight": 0.6, "contribution": 0.12},
            },
        }
        validated, warnings = validate_sentiment(result)
        total_weight = sum(
            f["weight"] for f in validated["factors"].values() if isinstance(f, dict)
        )
        assert abs(total_weight - 1.0) < 0.01
        assert any("normalizing" in w.lower() for w in warnings)

    def test_factor_score_clamping(self):
        result = {
            "overall_sentiment": 0.0,
            "factors": {
                "earnings": {"score": -2.0, "weight": 0.5, "contribution": -1.0},
            },
        }
        validated, warnings = validate_sentiment(result)
        assert validated["factors"]["earnings"]["score"] == -1.0
        assert any("score" in w.lower() for w in warnings)

    def test_passthrough_valid(self):
        result = {
            "overall_sentiment": 0.35,
            "confidence": 0.75,
            "factors": {
                "earnings": {"score": 0.5, "weight": 0.3, "contribution": 0.15},
                "guidance": {"score": 0.3, "weight": 0.4, "contribution": 0.12},
                "news": {"score": 0.2, "weight": 0.3, "contribution": 0.06},
            },
        }
        validated, warnings = validate_sentiment(result)
        assert validated["overall_sentiment"] == 0.35
        assert warnings == []


# ═══════════════════════════════════════════════
# Scenario Guardrails
# ═══════════════════════════════════════════════


class TestScenarioGuardrails:
    """validate_scenarios — enforce probability and return constraints."""

    def test_probability_sum_warning(self):
        scenarios = {
            "bull": {"probability": 0.3, "expected_return_pct": 10.0},
            "base": {"probability": 0.2, "expected_return_pct": 2.0},
            "bear": {"probability": 0.2, "expected_return_pct": -8.0},
        }
        _, warnings = validate_scenarios(scenarios)
        assert any("sum" in w.lower() or "probabilities" in w.lower() for w in warnings)

    def test_return_bounds(self):
        scenarios = {
            "bull": {"probability": 0.4, "expected_return_pct": 50.0},
            "base": {"probability": 0.35, "expected_return_pct": 5.0},
            "bear": {"probability": 0.25, "expected_return_pct": -40.0},
        }
        validated, warnings = validate_scenarios(scenarios)
        assert validated["bull"]["expected_return_pct"] == 30.0
        assert validated["bear"]["expected_return_pct"] == -30.0
        assert len(warnings) >= 2

    def test_monotonicity(self):
        scenarios = {
            "bull": {"probability": 0.3, "expected_return_pct": -5.0},
            "base": {"probability": 0.4, "expected_return_pct": 10.0},
            "bear": {"probability": 0.3, "expected_return_pct": 3.0},
        }
        validated, warnings = validate_scenarios(scenarios)
        assert validated["bull"]["expected_return_pct"] >= validated["base"]["expected_return_pct"]
        assert validated["base"]["expected_return_pct"] >= validated["bear"]["expected_return_pct"]
        assert any("monotonic" in w.lower() for w in warnings)

    def test_passthrough_valid(self):
        scenarios = {
            "bull": {"probability": 0.35, "expected_return_pct": 12.0},
            "base": {"probability": 0.40, "expected_return_pct": 3.0},
            "bear": {"probability": 0.25, "expected_return_pct": -8.0},
        }
        validated, warnings = validate_scenarios(scenarios)
        assert validated["bull"]["expected_return_pct"] == 12.0
        assert warnings == []


# ═══════════════════════════════════════════════
# Recommendation Override
# ═══════════════════════════════════════════════


class TestRecommendationOverride:
    """validation_rules — override to HOLD when 5+ agents disagree."""

    def _make_agent_results(self, directions: dict) -> dict:
        """Build agent_results dict from direction map."""
        results = {}
        direction_map = {
            "bullish": {"trend": "uptrend"},
            "bearish": {"trend": "downtrend"},
            "neutral": {"trend": "sideways"},
        }
        signal_map = {
            "bullish": {"overall": "buy", "strength": 30},
            "bearish": {"overall": "sell", "strength": -30},
            "neutral": {"overall": "neutral", "strength": 0},
        }
        for agent, direction in directions.items():
            if agent == "market":
                results["market"] = {"data": direction_map.get(direction, {"trend": "sideways"})}
            elif agent == "technical":
                results["technical"] = {"data": {"signals": signal_map.get(direction, {"overall": "neutral", "strength": 0})}}
            elif agent == "fundamentals":
                health = 70 if direction == "bullish" else (30 if direction == "bearish" else 50)
                results["fundamentals"] = {"data": {"health_score": health}}
            elif agent == "macro":
                env = "risk_on" if direction == "bullish" else ("risk_off" if direction == "bearish" else "neutral")
                results["macro"] = {"data": {"risk_environment": env}}
            elif agent == "options":
                sig = direction
                results["options"] = {"data": {"overall_signal": sig}}
            elif agent == "sentiment":
                score = 0.5 if direction == "bullish" else (-0.5 if direction == "bearish" else 0.0)
                results["sentiment"] = {"data": {"overall_sentiment": score}}
        return results

    def test_override_buy_to_hold(self):
        """5 bearish agents + BUY recommendation → HOLD override."""
        agent_results = self._make_agent_results({
            "market": "bearish",
            "technical": "bearish",
            "fundamentals": "bearish",
            "macro": "bearish",
            "options": "bearish",
            "sentiment": "bullish",
        })
        report = run_validation(
            final_analysis={"recommendation": "BUY"},
            agent_results=agent_results,
        )
        assert report.get("override_recommendation") == "HOLD"

    def test_no_override_4_agents(self):
        """4 bearish agents + BUY recommendation → no override."""
        agent_results = self._make_agent_results({
            "market": "bearish",
            "technical": "bearish",
            "fundamentals": "bearish",
            "macro": "bearish",
            "options": "bullish",
            "sentiment": "bullish",
        })
        report = run_validation(
            final_analysis={"recommendation": "BUY"},
            agent_results=agent_results,
        )
        assert report.get("override_recommendation") is None

    def test_override_sell_to_hold(self):
        """5 bullish agents + SELL recommendation → HOLD override."""
        agent_results = self._make_agent_results({
            "market": "bullish",
            "technical": "bullish",
            "fundamentals": "bullish",
            "macro": "bullish",
            "options": "bullish",
            "sentiment": "bearish",
        })
        report = run_validation(
            final_analysis={"recommendation": "SELL"},
            agent_results=agent_results,
        )
        assert report.get("override_recommendation") == "HOLD"


# ═══════════════════════════════════════════════
# Transcript Extraction
# ═══════════════════════════════════════════════


class TestTranscriptExtraction:
    """FundamentalsAgent._extract_transcript_metrics — regex extraction."""

    def test_extract_revenue_guidance(self):
        text = "We expect revenue of $15 billion for the quarter, up from prior guidance."
        metrics = FundamentalsAgent._extract_transcript_metrics(text)
        assert "revenue_guidance" in metrics
        assert metrics["revenue_guidance"]["low"] == 15.0
        assert metrics["revenue_guidance"]["unit"] == "billion"

    def test_extract_revenue_range(self):
        text = "Revenue guidance is $94 billion to $98 billion in revenue for the full year."
        metrics = FundamentalsAgent._extract_transcript_metrics(text)
        assert "revenue_guidance" in metrics
        assert metrics["revenue_guidance"]["low"] == 94.0
        assert metrics["revenue_guidance"]["high"] == 98.0

    def test_extract_eps_range(self):
        text = "We expect diluted EPS of $1.50 to $1.55 for the quarter."
        metrics = FundamentalsAgent._extract_transcript_metrics(text)
        assert "eps_guidance" in metrics
        assert metrics["eps_guidance"]["low"] == 1.50
        assert metrics["eps_guidance"]["high"] == 1.55

    def test_extract_growth_target(self):
        text = "Services revenue grew 12% year-over-year, driven by strong subscription growth."
        metrics = FundamentalsAgent._extract_transcript_metrics(text)
        assert "growth_targets" in metrics
        assert any(t["value"] == 12.0 for t in metrics["growth_targets"])

    def test_no_guidance_returns_empty(self):
        text = "Thank you for joining today's call. We are pleased with our performance."
        metrics = FundamentalsAgent._extract_transcript_metrics(text)
        assert metrics == {} or all(v == {} for v in metrics.values() if isinstance(v, dict))

    def test_empty_content(self):
        assert FundamentalsAgent._extract_transcript_metrics("") == {}
        assert FundamentalsAgent._extract_transcript_metrics(None) == {}


# ═══════════════════════════════════════════════
# Equity Research Cross-Validation
# ═══════════════════════════════════════════════


class TestEquityResearchCrossValidation:
    """validate_equity_research — flag LLM claims that deviate from input data."""

    def test_pe_deviation_flagged(self):
        report = {
            "executive_summary": "With a P/E of 15, the company looks cheap.",
            "financial_health_check": {"valuation_analysis": "", "fcf_analysis": ""},
        }
        input_metrics = {"pe_ratio": 31.78}
        _, warnings = validate_equity_research(report, input_metrics)
        assert len(warnings) >= 1
        assert any("P/E" in w or "p/e" in w.lower() for w in warnings)

    def test_accurate_claims_no_warning(self):
        report = {
            "executive_summary": "At a P/E of 32, valuation is stretched.",
            "financial_health_check": {"valuation_analysis": "", "fcf_analysis": ""},
        }
        input_metrics = {"pe_ratio": 31.78}
        _, warnings = validate_equity_research(report, input_metrics)
        assert warnings == []

    def test_empty_report_no_crash(self):
        _, warnings = validate_equity_research({}, {})
        assert warnings == []
        _, warnings = validate_equity_research(None, None)
        assert warnings == []
