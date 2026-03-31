"""Tests for deterministic council consensus aggregation."""

import pytest
from src.council_synthesis import build_consensus


@pytest.fixture
def sample_council_results():
    return [
        {"investor": "druckenmiller", "investor_name": "Stanley Druckenmiller", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts rates", "action": "then add exposure", "conviction": "high"}]},
        {"investor": "ptj", "investor_name": "Paul Tudor Jones", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "price", "condition": "If price breaks 160", "action": "then trail stop", "conviction": "medium"}]},
        {"investor": "munger", "investor_name": "Charlie Munger", "stance": "CAUTIOUS", "thesis_health": "WATCHING", "disagreement_flag": "Disagrees with bullish macro thesis", "if_then_scenarios": [{"type": "event", "condition": "If margins compress", "action": "then reduce position", "conviction": "high"}]},
        {"investor": "dalio", "investor_name": "Ray Dalio", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If yield curve inverts further", "action": "then hedge", "conviction": "low"}]},
        {"investor": "marks", "investor_name": "Howard Marks", "stance": "BEARISH", "thesis_health": "DETERIORATING", "disagreement_flag": "Sees cycle top signals", "if_then_scenarios": []},
    ]


class TestStanceDistribution:
    def test_counts_stances(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["stance_distribution"]["bullish"] == 3
        assert consensus["stance_distribution"]["cautious"] == 1
        assert consensus["stance_distribution"]["bearish"] == 1
        assert consensus["stance_distribution"]["pass"] == 0

    def test_majority_stance(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["majority_stance"] == "BULLISH"

    def test_conviction_strength(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["conviction_strength"] == pytest.approx(0.6)


class TestTieBreaking:
    def test_tie_favors_bullish_over_cautious(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "CAUTIOUS", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["majority_stance"] == "BULLISH"

    def test_pass_excluded_from_conviction(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "PASS", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["conviction_strength"] == pytest.approx(1.0)


class TestDisagreements:
    def test_extracts_disagreement_flags(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert len(consensus["disagreements"]) == 2
        investors = [d["investor"] for d in consensus["disagreements"]]
        assert "munger" in investors
        assert "marks" in investors


class TestTopScenarios:
    def test_top_scenarios_sorted_by_conviction(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        scenarios = consensus["top_scenarios"]
        assert len(scenarios) <= 3
        high_scenarios = [s for s in scenarios if s["conviction"] == "high"]
        assert len(high_scenarios) >= 1

    def test_deduplicates_identical_conditions(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None,
             "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts rates", "action": "then add", "conviction": "high"}]},
            {"investor": "b", "investor_name": "B", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None,
             "if_then_scenarios": [{"type": "macro", "condition": "if fed cuts rates", "action": "then buy", "conviction": "high"}]},
        ]
        consensus = build_consensus(results)
        assert len(consensus["top_scenarios"]) == 1


class TestThesisHealthConsensus:
    def test_mode_of_health_values(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["thesis_health_consensus"] == "INTACT"

    def test_unknown_excluded_from_mode(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "WATCHING", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "BULLISH", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "c", "investor_name": "C", "stance": "BULLISH", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["thesis_health_consensus"] == "WATCHING"


class TestEmptyResults:
    def test_empty_council_returns_defaults(self):
        consensus = build_consensus([])
        assert consensus["majority_stance"] == "PASS"
        assert consensus["conviction_strength"] == 0.0
        assert consensus["disagreements"] == []
        assert consensus["top_scenarios"] == []
