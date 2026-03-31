"""Integration tests for thesis health monitor + council synthesis."""

import json
import pytest
from src.thesis_health import evaluate_thesis_health
from src.council_synthesis import build_consensus


class TestThesisHealthEndToEnd:
    """Full flow: thesis card + agent results → health report → alert check."""

    def test_full_health_check_flow(self, db_manager):
        # Create a thesis card
        card = db_manager.upsert_thesis_card("NVDA", {
            "structural_thesis": "AI compute leader",
            "load_bearing_assumption": "revenue growth",
            "health_indicators": [
                {"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": None},
                {"name": "Revenue Growth", "proxy_signal": "revenue_growth", "baseline_value": "0.28", "current_value": None},
            ],
        })
        assert card["ticker"] == "NVDA"

        # Run health check with stable data
        agent_results = {
            "technical": {"success": True, "data": {"rsi": 55}},
            "fundamentals": {"success": True, "data": {"revenue_growth": 0.28}},
        }
        report = evaluate_thesis_health(
            thesis_card=card,
            agent_results=agent_results,
            previous_health=None,
        )
        assert report["overall_health"] == "INTACT"

        # Save snapshot
        row_id = db_manager.save_thesis_health_snapshot(
            analysis_id=1, ticker="NVDA",
            overall_health=report["overall_health"],
            previous_health=report.get("previous_health"),
            health_changed=report["health_changed"],
            indicators_json=report["indicators"],
            baselines_updated=report["baselines_updated"],
        )
        assert row_id is not None

        # Run health check with drifted data (RSI 55 → 62 = ~12.7% drift = "drifting" → WATCHING)
        agent_results["technical"]["data"]["rsi"] = 62
        report2 = evaluate_thesis_health(
            thesis_card=card,
            agent_results=agent_results,
            previous_health="INTACT",
        )
        assert report2["overall_health"] == "WATCHING"
        assert report2["health_changed"] is True

        # Verify alert engine catches it
        from src.alert_engine import AlertEngine
        engine = AlertEngine(db_manager)
        current = {"ticker": "NVDA", "analysis": {"thesis_health": report2}}
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is not None
        assert "INTACT → WATCHING" in result["message"]


class TestCouncilSynthesisEndToEnd:
    """Full flow: council results → consensus + DB persistence."""

    def test_consensus_and_persist(self, db_manager):
        council_results = [
            {"investor": "druckenmiller", "investor_name": "Druckenmiller", "stance": "BULLISH", "thesis_health": "INTACT",
             "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts", "action": "add", "conviction": "high"}]},
            {"investor": "marks", "investor_name": "Marks", "stance": "BEARISH", "thesis_health": "DETERIORATING",
             "disagreement_flag": "Cycle top risk", "if_then_scenarios": []},
        ]
        consensus = build_consensus(council_results)
        assert consensus["majority_stance"] == "BULLISH"
        assert len(consensus["disagreements"]) == 1

        synthesis = {"consensus": consensus, "narrative": {"narrative": "", "fallback_used": True}}
        row_id = db_manager.save_council_synthesis("AAPL", 1, synthesis)
        assert row_id is not None

        loaded = db_manager.get_latest_council_synthesis("AAPL")
        assert loaded is not None
        assert loaded["consensus_json"]["majority_stance"] == "BULLISH"
