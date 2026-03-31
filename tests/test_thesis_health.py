"""Tests for thesis health indicator drift detection and aggregate rollup."""

import pytest
from src.thesis_health import evaluate_thesis_health, resolve_indicator_value


@pytest.fixture
def sample_agent_results():
    return {
        "market": {"success": True, "data": {"current_price": 152.0, "trend": "uptrend"}},
        "technical": {"success": True, "data": {"rsi": 55, "signals": {"overall": "buy", "strength": 30}}},
        "fundamentals": {"success": True, "data": {"health_score": 72, "revenue_growth": 0.28}},
        "options": {"success": True, "data": {"put_call_ratio": 0.8}},
        "sentiment": {"success": True, "data": {"overall_sentiment": 0.4}},
        "macro": {"success": True, "data": {"risk_environment": "risk_on", "yield_curve_slope": 0.5}},
    }


@pytest.fixture
def sample_thesis_card():
    return {
        "ticker": "NVDA",
        "structural_thesis": "AI compute leader",
        "load_bearing_assumption": "revenue growth above 20%",
        "health_indicators": [
            {"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": None},
            {"name": "Revenue Growth", "proxy_signal": "revenue_growth", "baseline_value": "0.28", "current_value": None},
            {"name": "Put/Call Ratio", "proxy_signal": "put_call_ratio", "baseline_value": "0.8", "current_value": None},
        ],
    }


class TestResolveIndicatorValue:
    def test_resolves_market_price(self, sample_agent_results):
        assert resolve_indicator_value("current_price", sample_agent_results) == "152.0"

    def test_resolves_rsi(self, sample_agent_results):
        assert resolve_indicator_value("rsi", sample_agent_results) == "55"

    def test_resolves_fundamentals_key(self, sample_agent_results):
        assert resolve_indicator_value("revenue_growth", sample_agent_results) == "0.28"

    def test_resolves_put_call_ratio(self, sample_agent_results):
        assert resolve_indicator_value("put_call_ratio", sample_agent_results) == "0.8"

    def test_resolves_sentiment(self, sample_agent_results):
        assert resolve_indicator_value("overall_sentiment", sample_agent_results) == "0.4"

    def test_resolves_macro_string(self, sample_agent_results):
        assert resolve_indicator_value("risk_environment", sample_agent_results) == "risk_on"

    def test_unknown_signal_returns_none(self, sample_agent_results):
        assert resolve_indicator_value("nonexistent_signal", sample_agent_results) is None


class TestDriftDetection:
    def test_all_stable_returns_intact(self, sample_thesis_card, sample_agent_results):
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health=None,
        )
        assert report["overall_health"] == "INTACT"
        assert all(ind["status"] == "stable" for ind in report["indicators"])

    def test_drifting_indicator_returns_watching(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 68
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="INTACT",
        )
        assert report["overall_health"] == "WATCHING"
        rsi_ind = next(i for i in report["indicators"] if i["proxy_signal"] == "rsi")
        assert rsi_ind["status"] == "drifting"

    def test_breached_indicator_returns_deteriorating(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 80
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="INTACT",
        )
        assert report["overall_health"] == "DETERIORATING"

    def test_two_breached_returns_broken(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 80
        sample_agent_results["options"]["data"]["put_call_ratio"] = 2.5
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="WATCHING",
        )
        assert report["overall_health"] == "BROKEN"

    def test_load_bearing_breach_returns_broken(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["fundamentals"]["data"]["revenue_growth"] = 0.10
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="INTACT",
        )
        assert report["overall_health"] == "BROKEN"


class TestHealthChange:
    def test_health_changed_when_different(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 68
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="INTACT",
        )
        assert report["health_changed"] is True
        assert report["previous_health"] == "INTACT"

    def test_health_unchanged_when_same(self, sample_thesis_card, sample_agent_results):
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card, agent_results=sample_agent_results, previous_health="INTACT",
        )
        assert report["health_changed"] is False


class TestBaselineSnapshot:
    def test_counts_baselines_needing_snapshot(self, sample_agent_results):
        card = {
            "ticker": "AAPL", "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "RSI", "proxy_signal": "rsi", "baseline_value": None, "current_value": None},
                {"name": "Price", "proxy_signal": "current_price", "baseline_value": None, "current_value": None},
            ],
        }
        report = evaluate_thesis_health(thesis_card=card, agent_results=sample_agent_results, previous_health=None)
        assert report["baselines_updated"] == 2
        assert report["overall_health"] == "INTACT"


class TestStringIndicators:
    def test_string_unchanged_is_stable(self, sample_agent_results):
        card = {
            "ticker": "TEST", "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "Risk Env", "proxy_signal": "risk_environment", "baseline_value": "risk_on", "current_value": None},
            ],
        }
        report = evaluate_thesis_health(thesis_card=card, agent_results=sample_agent_results, previous_health=None)
        assert report["indicators"][0]["status"] == "stable"

    def test_string_changed_is_breached(self, sample_agent_results):
        sample_agent_results["macro"]["data"]["risk_environment"] = "risk_off"
        card = {
            "ticker": "TEST", "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "Risk Env", "proxy_signal": "risk_environment", "baseline_value": "risk_on", "current_value": None},
            ],
        }
        report = evaluate_thesis_health(thesis_card=card, agent_results=sample_agent_results, previous_health=None)
        assert report["indicators"][0]["status"] == "breached"
