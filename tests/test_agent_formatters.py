"""Tests for agent API formatting utilities."""

import pytest
from datetime import datetime, timezone, timedelta

from src.routers.agent_formatters import (
    format_summary,
    format_analysis,
    format_changes,
    clean_for_agent,
    agent_error,
    relative_time,
    truncate_text,
)


def _make_analysis_record(**overrides):
    """Create a minimal analysis record for testing."""
    base = {
        "id": 1,
        "ticker": "AAPL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendation": "BUY",
        "confidence_score": 0.81,
        "overall_sentiment_score": 0.62,
        "score": 72.0,
        "ev_score_7d": 1.2,
        "confidence_calibrated": 0.74,
        "data_quality_score": 87.0,
        "regime_label": "risk_on",
        "rationale_summary": "Strong fundamentals with AI catalyst.",
        "solution_agent_reasoning": "The company shows strong growth metrics...",
        "decision_card": None,
        "signal_contract_v2": None,
        "analysis": {
            "recommendation": "BUY",
            "score": 72,
            "confidence": 0.81,
            "reasoning": "A " * 200,
            "risks": ["Risk 1", "Risk 2", "Risk 3", "Risk 4", "Risk 5", "Risk 6"],
            "opportunities": ["Opp 1", "Opp 2", "Opp 3"],
            "price_targets": {"entry": 185.0, "target": 210.0, "stop_loss": 175.0},
            "position_size": "MEDIUM",
            "time_horizon": "MEDIUM_TERM",
            "signal_contract_v2": {
                "confidence": {"raw": 0.81, "calibrated": 0.74},
                "risk": {"data_quality_score": 87.0},
            },
        },
        "agent_results": {
            "fundamentals": {
                "success": True,
                "data": {"health_score": 82, "pe_ratio": 28.4},
                "duration_seconds": 2.5,
            },
            "sentiment": {
                "success": True,
                "data": {"overall_sentiment": 0.62, "confidence": 0.8},
                "duration_seconds": 3.1,
            },
        },
    }
    base.update(overrides)
    return base


class TestFormatSummary:
    def test_returns_required_fields(self):
        record = _make_analysis_record()
        result = format_summary(record)
        assert result["ticker"] == "AAPL"
        assert result["recommendation"] == "BUY"
        assert result["score"] == 72
        assert result["confidence"] == 0.81
        assert result["sentiment"] == 0.62
        assert "data_age_minutes" in result

    def test_extracts_price_targets(self):
        record = _make_analysis_record()
        result = format_summary(record)
        assert result["entry"] == 185.0
        assert result["target"] == 210.0
        assert result["stop_loss"] == 175.0

    def test_caps_risks_at_5(self):
        record = _make_analysis_record()
        result = format_summary(record)
        assert len(result["top_risks"]) <= 5

    def test_truncates_reasoning(self):
        record = _make_analysis_record()
        result = format_summary(record)
        words = result["reasoning_short"].split()
        assert len(words) <= 105

    def test_handles_missing_analysis(self):
        record = _make_analysis_record(analysis=None)
        result = format_summary(record)
        assert result["recommendation"] == "BUY"
        assert result.get("entry") is None

    def test_data_age_minutes_computed(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        record = _make_analysis_record(timestamp=old_ts)
        result = format_summary(record)
        assert 55 <= result["data_age_minutes"] <= 65


class TestFormatAnalysis:
    def test_standard_detail_includes_agent_sections(self):
        record = _make_analysis_record()
        result = format_analysis(record, detail="standard")
        assert "agents" in result
        assert "fundamentals" in result["agents"]

    def test_section_filtering(self):
        record = _make_analysis_record()
        result = format_analysis(record, detail="standard", sections=["sentiment"])
        assert "sentiment" in result["agents"]
        assert "fundamentals" not in result["agents"]

    def test_full_detail_returns_raw_analysis(self):
        record = _make_analysis_record()
        result = format_analysis(record, detail="full")
        assert "analysis" in result
        assert "agent_results" in result

    def test_summary_detail_same_as_format_summary(self):
        record = _make_analysis_record()
        result = format_analysis(record, detail="summary")
        assert "recommendation" in result
        assert "agents" not in result


class TestFormatChanges:
    def test_detects_recommendation_change(self):
        current = _make_analysis_record(recommendation="BUY", score=72.0)
        previous = _make_analysis_record(recommendation="HOLD", score=50.0)
        result = format_changes(current, previous)
        assert result["recommendation_changed"] is True
        assert result["previous_recommendation"] == "HOLD"
        assert result["score_delta"] == 22.0

    def test_no_previous_returns_first_analysis(self):
        current = _make_analysis_record()
        result = format_changes(current, None)
        assert result["is_first_analysis"] is True


class TestCleanForAgent:
    def test_removes_none_values(self):
        data = {"a": 1, "b": None, "c": "hello"}
        result = clean_for_agent(data)
        assert "b" not in result
        assert result["a"] == 1

    def test_rounds_floats(self):
        data = {"price": 185.123456789}
        result = clean_for_agent(data)
        assert result["price"] == 185.1235

    def test_nested_cleaning(self):
        data = {"outer": {"a": None, "b": 1.23456789}}
        result = clean_for_agent(data)
        assert "a" not in result["outer"]
        assert result["outer"]["b"] == 1.2346

    def test_flattens_single_element_lists(self):
        data = {"items": ["only_one"]}
        result = clean_for_agent(data)
        assert result["items"] == "only_one"


class TestAgentError:
    def test_basic_error(self):
        result = agent_error("Something went wrong")
        assert result["error"] is True
        assert result["message"] == "Something went wrong"
        assert "suggestion" not in result

    def test_error_with_suggestion(self):
        result = agent_error("No analysis found", suggestion="run_analysis")
        assert result["suggestion"] == "run_analysis"


class TestRelativeTime:
    def test_recent_timestamp(self):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        result = relative_time(ts)
        assert "30 min ago" in result or "29 min ago" in result

    def test_hours_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = relative_time(ts)
        assert "3 hours ago" in result

    def test_old_timestamp_returns_iso(self):
        ts = "2026-01-01T00:00:00+00:00"
        result = relative_time(ts)
        assert "2026-01-01" in result


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert truncate_text("hello world", 100) == "hello world"

    def test_long_text_truncated(self):
        long = " ".join(["word"] * 200)
        result = truncate_text(long, 10)
        assert len(result.split()) <= 11
        assert result.endswith("...")
