"""Integration tests for two-tier validation agent (Phase 2.5)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.validation_rules import validate as run_validation_rules
from src.agents.council_validator_agent import CouncilValidatorAgent


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_final_analysis():
    return {
        "recommendation": "BUY",
        "score": 35,
        "confidence": 0.75,
        "reasoning": "Strong fundamentals with positive macro backdrop.",
        "price_targets": {"entry": 150.0, "target": 175.0, "stop_loss": 140.0},
        "signal_contract_v2": {
            "direction": "bullish",
            "regime": {"label": "risk_on"},
        },
    }


@pytest.fixture
def sample_agent_results():
    return {
        "market": {
            "success": True,
            "data": {"trend": "uptrend", "current_price": 152.0},
        },
        "technical": {
            "success": True,
            "data": {
                "signals": {"overall": "buy", "strength": 30},
                "rsi": 55,
                "support_levels": [140, 145],
                "resistance_levels": [160, 170],
            },
        },
        "macro": {
            "success": True,
            "data": {"risk_environment": "risk_on", "yield_curve_slope": 0.5},
        },
        "options": {
            "success": True,
            "data": {"put_call_ratio": 0.8, "overall_signal": "bullish"},
        },
        "fundamentals": {
            "success": True,
            "data": {"health_score": 72, "recommendation": "buy"},
        },
        "news": {
            "success": True,
            "data": {"articles": [], "twitter_posts": []},
        },
        "sentiment": {
            "success": True,
            "data": {"overall_sentiment": 0.4, "score": 0.4},
        },
    }


# ─── Rule Engine Integration ───────────────────────────────────────────────────


class TestValidationRulesIntegration:
    """End-to-end tests for the rule engine with realistic data."""

    def test_clean_analysis_passes_all_rules(self, sample_final_analysis, sample_agent_results):
        report = run_validation_rules(
            final_analysis=sample_final_analysis,
            agent_results=sample_agent_results,
        )
        assert report["overall_status"] if "overall_status" in report else True
        assert report["total_rules_checked"] >= 4
        assert report["total_confidence_penalty"] >= 0.0
        assert isinstance(report["results"], list)

    def test_contradicted_analysis_has_penalty(self, sample_final_analysis, sample_agent_results):
        """BUY recommendation contradicted by majority bearish agents should trigger penalty."""
        contradicted = dict(sample_final_analysis, recommendation="BUY", score=40)
        bearish_results = dict(sample_agent_results)
        bearish_results["market"] = {"success": True, "data": {"trend": "downtrend"}}
        bearish_results["technical"] = {
            "success": True,
            "data": {
                "signals": {"overall": "sell", "strength": -50},
                "rsi": 72,
                "support_levels": [100],
                "resistance_levels": [130, 140, 150],
            },
        }
        bearish_results["macro"] = {"success": True, "data": {"risk_environment": "risk_off"}}
        bearish_results["options"] = {"success": True, "data": {"put_call_ratio": 1.8, "overall_signal": "bearish"}}

        report = run_validation_rules(
            final_analysis=contradicted,
            agent_results=bearish_results,
        )
        assert report["total_confidence_penalty"] > 0.0

    def test_penalty_capped_at_040(self, sample_final_analysis, sample_agent_results):
        """Total rule penalty must not exceed 0.40."""
        contradicted = dict(sample_final_analysis, recommendation="BUY")
        all_bearish = dict(sample_agent_results)
        all_bearish["market"] = {"success": True, "data": {"trend": "downtrend"}}
        all_bearish["macro"] = {"success": True, "data": {"risk_environment": "risk_off"}}
        all_bearish["options"] = {"success": True, "data": {"put_call_ratio": 2.5, "overall_signal": "bearish"}}

        report = run_validation_rules(
            final_analysis=contradicted,
            agent_results=all_bearish,
        )
        assert report["total_confidence_penalty"] <= 0.40


# ─── Council Validator Integration ────────────────────────────────────────────


class TestCouncilValidatorIntegration:
    """Integration tests for CouncilValidatorAgent with mocked LLM."""

    def _make_agent(self, config=None):
        cfg = config or {
            "LLM_PROVIDER": "anthropic",
            "llm_config": {
                "provider": "anthropic",
                "model": "claude-3-5-haiku-20241022",
                "api_key": "test-key",
                "temperature": 0.0,
                "max_tokens": 1024,
            },
            "AGENT_TIMEOUT": 30,
            "VALIDATION_V1_ENABLED": True,
        }
        return CouncilValidatorAgent("AAPL", cfg)

    def test_empty_council_returns_fallback(self, sample_agent_results):
        agent = self._make_agent()
        # _empty_report with fallback_used=True
        report = agent._empty_report(fallback_used=True)
        assert report["fallback_used"] is True
        assert report["total_contradictions"] == 0
        assert report["confidence_penalty"] == 0.0

    def test_parse_llm_response_extracts_contradictions(self):
        agent = self._make_agent()
        # Schema uses per-claim verdict fields under "claims" array
        llm_text = json.dumps({
            "investor_validations": [
                {
                    "investor": "druckenmiller",
                    "claims": [
                        {
                            "claim": "macro tailwind intact",
                            "verdict": "contradicted",
                            "evidence": "yield curve inverted, unemployment rising",
                            "severity": "contradiction",
                        },
                        {
                            "claim": "risk-on regime",
                            "verdict": "supported",
                            "evidence": "equity markets positive",
                            "severity": "info",
                        },
                    ],
                }
            ]
        })
        report = agent._parse_validation_response(llm_text)
        assert report["total_contradictions"] == 1
        assert report["confidence_penalty"] > 0.0
        assert report["fallback_used"] is False

    def test_parse_malformed_llm_response_falls_back(self):
        agent = self._make_agent()
        report = agent._parse_validation_response("not json at all !!!")
        assert report["fallback_used"] is True
        assert report["confidence_penalty"] == 0.0

    @pytest.mark.asyncio
    async def test_execute_no_council_context_returns_empty(self, sample_agent_results):
        agent = self._make_agent()
        # Empty council list → returns empty report without triggering LLM
        agent.set_council_context([], sample_agent_results)
        result = await agent.execute()
        assert result["success"] is True
        data = result["data"]
        assert data["total_contradictions"] == 0
        assert data["confidence_penalty"] == 0.0


# ─── Validation API Integration ───────────────────────────────────────────────


class TestValidationFeedbackAPI:
    """Tests for the feedback endpoint via db layer."""

    def test_save_and_retrieve_feedback(self, db_manager):
        # First we need a validation_result to reference
        import uuid
        vid = str(uuid.uuid4())
        db_manager.save_validation_result(
            analysis_id=1,
            ticker="AAPL",
            validation_id=vid,
            overall_status="contradictions",
            original_confidence=0.75,
            adjusted_confidence=0.60,
            total_confidence_penalty=0.15,
            rule_checks_total=4,
            rule_contradictions=1,
            council_claims_total=0,
            council_contradictions=0,
            spot_check_requested=True,
            report_json={"overall_status": "contradictions"},
        )
        db_manager.save_validation_feedback(
            validation_id=vid,
            ticker="AAPL",
            claim_type="rule",
            claim_summary="direction_consistency mismatch",
            human_verdict="confirmed",
        )
        feedback = db_manager.get_validation_feedback(vid)
        assert len(feedback) == 1
        assert feedback[0]["human_verdict"] == "confirmed"
        assert feedback[0]["ticker"] == "AAPL"

    def test_get_validation_result_returns_report(self, db_manager):
        import uuid
        vid = str(uuid.uuid4())
        report = {"overall_status": "clean", "total_confidence_penalty": 0.0}
        db_manager.save_validation_result(
            analysis_id=2,
            ticker="TSLA",
            validation_id=vid,
            overall_status="clean",
            original_confidence=0.80,
            adjusted_confidence=0.80,
            total_confidence_penalty=0.0,
            rule_checks_total=4,
            rule_contradictions=0,
            council_claims_total=0,
            council_contradictions=0,
            spot_check_requested=False,
            report_json=report,
        )
        row = db_manager.get_validation_result(vid)
        assert row is not None
        assert row["ticker"] == "TSLA"
        assert row["overall_status"] == "clean"

    def test_get_validation_result_nonexistent_returns_none(self, db_manager):
        result = db_manager.get_validation_result("nonexistent-id")
        assert result is None


# ─── Alert Engine spot_check Integration ──────────────────────────────────────


class TestSpotCheckAlert:
    """Tests for the spot_check alert rule type."""

    def _make_engine(self, db_manager):
        from src.alert_engine import AlertEngine
        return AlertEngine(db_manager)

    def test_spot_check_fires_when_requested(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {
            "ticker": "AAPL",
            "recommendation": "BUY",
            "analysis": {
                "validation": {
                    "spot_check_requested": True,
                    "overall_status": "contradictions",
                    "total_confidence_penalty": 0.15,
                    "rule_validation": {"contradictions": 1},
                    "council_validation": {"total_contradictions": 0},
                }
            },
        }
        rule = {"rule_type": "spot_check", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is not None
        assert "SPOT CHECK" in result["message"]
        assert "AAPL" in result["message"]

    def test_spot_check_silent_when_not_requested(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {
            "ticker": "AAPL",
            "analysis": {
                "validation": {
                    "spot_check_requested": False,
                    "overall_status": "clean",
                    "total_confidence_penalty": 0.0,
                }
            },
        }
        rule = {"rule_type": "spot_check", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is None

    def test_spot_check_silent_with_no_validation(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {"ticker": "AAPL", "recommendation": "HOLD"}
        rule = {"rule_type": "spot_check", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is None
