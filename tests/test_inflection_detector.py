"""Tests for inflection detection and convergence scoring."""

import pytest
from src.inflection_detector import InflectionDetector


class TestInflectionDetector:

    def _make_snapshot(self, kpi_name, category, value, agent):
        return {"kpi_name": kpi_name, "kpi_category": category, "value": value, "source_agent": agent}

    def test_detects_positive_growth_inflection(self):
        detector = InflectionDetector()
        prior = [self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals")]
        current = [self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals")]
        inflections = detector.detect(prior, current)
        assert len(inflections) == 1
        assert inflections[0]["kpi_name"] == "revenue_growth"
        assert inflections[0]["direction"] == "positive"
        assert inflections[0]["pct_change"] > 0

    def test_detects_negative_margin_inflection(self):
        detector = InflectionDetector()
        prior = [self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals")]
        current = [self._make_snapshot("profit_margins", "margins", 0.24, "fundamentals")]
        inflections = detector.detect(prior, current)
        assert len(inflections) == 1
        assert inflections[0]["direction"] == "negative"

    def test_valuation_decrease_is_positive(self):
        """Forward PE decrease is positive (lower = better)."""
        detector = InflectionDetector()
        prior = [self._make_snapshot("forward_pe", "valuation", 25.0, "fundamentals")]
        current = [self._make_snapshot("forward_pe", "valuation", 20.0, "fundamentals")]
        inflections = detector.detect(prior, current)
        assert len(inflections) == 1
        assert inflections[0]["direction"] == "positive"

    def test_below_threshold_not_detected(self):
        detector = InflectionDetector()
        prior = [self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals")]
        current = [self._make_snapshot("profit_margins", "margins", 0.295, "fundamentals")]
        inflections = detector.detect(prior, current)
        assert len(inflections) == 0

    def test_convergence_score_multiple_agents(self):
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),
            self._make_snapshot("rsi", "technical", 40.0, "technical"),
        ]
        current = [
            self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),
            self._make_snapshot("rsi", "technical", 70.0, "technical"),
        ]
        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)
        assert summary["convergence_score"] == 1.0
        assert summary["direction"] == "positive"

    def test_convergence_mixed_directions(self):
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),
        ]
        current = [
            self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),
        ]
        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)
        assert summary["convergence_score"] == 0.5

    def test_first_run_baseline(self):
        detector = InflectionDetector()
        inflections = detector.detect(prior=[], current=[
            self._make_snapshot("forward_pe", "valuation", 22.5, "fundamentals"),
        ])
        assert len(inflections) == 0

    def test_build_summary_empty_inflections(self):
        detector = InflectionDetector()
        summary = detector.build_summary([])
        assert summary["convergence_score"] == 0.0
        assert summary["inflection_count"] == 0
        assert summary["direction"] == "neutral"

    def test_multiple_kpis_same_agent_count_once(self):
        """Multiple inflections from same agent count as one for convergence."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("forward_pe", "valuation", 25.0, "fundamentals"),
            self._make_snapshot("profit_margins", "margins", 0.25, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),
        ]
        current = [
            self._make_snapshot("forward_pe", "valuation", 20.0, "fundamentals"),
            self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),
        ]
        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)
        assert summary["convergence_score"] == 1.0

    def test_macro_positive_directions(self):
        """Fed funds rate decrease is positive; GDP growth increase is positive."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("fed_funds_rate", "macro", 5.50, "macro"),
            self._make_snapshot("gdp_growth", "macro", 2.0, "macro"),
        ]
        current = [
            self._make_snapshot("fed_funds_rate", "macro", 5.00, "macro"),
            self._make_snapshot("gdp_growth", "macro", 3.0, "macro"),
        ]
        inflections = detector.detect(prior, current)
        for inf in inflections:
            assert inf["direction"] == "positive"
