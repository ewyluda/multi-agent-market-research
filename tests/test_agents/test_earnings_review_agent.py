"""Tests for EarningsReviewAgent — models, deterministic, LLM, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import BeatMiss, GuidanceDelta, KPIRow, EarningsReviewOutput
from src.agents.earnings_review_agent import EarningsReviewAgent, SECTOR_KPI_TEMPLATES, DEFAULT_KPI_TEMPLATE


class TestEarningsReviewModels:
    """Pydantic model validation tests."""

    def test_beat_miss_valid(self):
        bm = BeatMiss(
            metric="EPS",
            actual=2.40,
            estimate=2.15,
            surprise_pct=11.63,
            verdict="beat",
        )
        assert bm.verdict == "beat"
        assert bm.actual == 2.40

    def test_beat_miss_inline(self):
        bm = BeatMiss(
            metric="Revenue",
            actual=95.0,
            estimate=94.8,
            surprise_pct=0.2,
            verdict="inline",
        )
        assert bm.verdict == "inline"

    def test_guidance_delta_valid(self):
        gd = GuidanceDelta(
            metric="Revenue",
            prior_value="$90-92B",
            new_value="$93-95B",
            direction="raised",
        )
        assert gd.direction == "raised"

    def test_kpi_row_valid(self):
        kpi = KPIRow(
            metric="ARR",
            value="$5.2B",
            prior_value="$4.8B",
            yoy_change="+8.3%",
            source="call_disclosed",
        )
        assert kpi.source == "call_disclosed"

    def test_kpi_row_with_none_values(self):
        kpi = KPIRow(
            metric="Net Revenue Retention",
            value="112%",
            prior_value=None,
            yoy_change=None,
            source="reported",
        )
        assert kpi.prior_value is None

    def test_earnings_review_output_valid(self):
        output = EarningsReviewOutput(
            executive_summary="Strong quarter with EPS beat.",
            beat_miss=[BeatMiss(metric="EPS", actual=2.40, estimate=2.15, surprise_pct=11.63, verdict="beat")],
            guidance_deltas=[GuidanceDelta(metric="Revenue", prior_value="$90B", new_value="$93B", direction="raised")],
            kpi_table=[KPIRow(metric="ARR", value="$5.2B", prior_value=None, yoy_change=None, source="reported")],
            management_tone="confident",
            notable_quotes=["We see strong momentum in AI."],
            thesis_impact="Confirms bull case on growth.",
            one_offs=["$200M restructuring charge"],
            sector_template="Technology",
            data_completeness=0.85,
            data_sources_used=["earnings", "fundamentals"],
        )
        assert output.data_completeness == 0.85
        assert len(output.beat_miss) == 1

    def test_earnings_review_output_completeness_clamped(self):
        with pytest.raises(ValidationError):
            EarningsReviewOutput(
                executive_summary="x",
                beat_miss=[],
                guidance_deltas=[],
                kpi_table=[],
                management_tone="neutral",
                notable_quotes=[],
                thesis_impact="",
                one_offs=[],
                sector_template="default",
                data_completeness=1.5,
                data_sources_used=[],
            )


def _make_agent_results(
    earnings=True, fundamentals=True, market=True,
    has_transcript=True,
):
    """Build mock agent_results dict for earnings review tests."""
    results = {}
    if earnings:
        earnings_data = {
            "highlights": [
                {"tag": "BEAT", "text": "EPS beat by 12%"},
                {"tag": "NEW", "text": "Launched AI assistant product"},
            ],
            "guidance": [
                {"metric": "Revenue", "prior": "$90-92B", "current": "$93-95B", "direction": "raised"},
            ],
            "tone": "confident",
            "guidance_direction": "raised",
            "qa_highlights": [
                {"analyst": "John Smith", "firm": "Goldman Sachs", "topic": "AI spend",
                 "question": "What are your capex plans for AI?",
                 "answer": "We plan to increase AI investment significantly next year."},
            ],
            "tone_analysis": {"confidence": 78, "specificity": 65, "defensiveness": 20, "forward_looking": 72, "hedging": 30},
            "eps_history": [
                {"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63},
                {"quarter": "Q4'25", "actual": 2.10, "estimate": 2.05, "surprise_pct": 2.44},
                {"quarter": "Q3'25", "actual": 1.95, "estimate": 2.00, "surprise_pct": -2.50},
            ],
            "analysis": "Strong quarter driven by services growth.",
            "data_source": "fmp",
        }
        if not has_transcript:
            # Simulate EPS data available but no transcript analysis
            earnings_data = {
                "highlights": [],
                "guidance": [],
                "tone": "neutral",
                "guidance_direction": "maintained",
                "qa_highlights": [],
                "tone_analysis": {"confidence": 50, "specificity": 50, "defensiveness": 50, "forward_looking": 50, "hedging": 50},
                "eps_history": [
                    {"quarter": "Q1'26", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63},
                ],
                "analysis": "No earnings call transcripts available for analysis.",
                "data_source": "none",
            }
        results["earnings"] = {"success": True, "data": earnings_data}
    else:
        results["earnings"] = {"success": False, "data": None, "error": "No earnings data"}

    if fundamentals:
        results["fundamentals"] = {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383000000000,
                "revenue_growth": 0.08,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software.",
                "data_source": "fmp",
            },
        }
    else:
        results["fundamentals"] = {"success": False, "data": None, "error": "Mock disabled"}

    if market:
        results["market"] = {
            "success": True,
            "data": {
                "current_price": 195.0,
                "high_52w": 220.0,
                "low_52w": 165.0,
                "price_change_1m": 0.05,
                "data_source": "fmp",
            },
        }
    else:
        results["market"] = {"success": False, "data": None, "error": "Mock disabled"}

    return results


class TestDeterministicBeatMiss:
    """Tests for deterministic EPS/revenue beat/miss computation."""

    def test_eps_beat(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "beat"
        assert eps["actual"] == 2.40
        assert eps["estimate"] == 2.15
        assert eps["surprise_pct"] == 11.63

    def test_eps_miss(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = [
            {"quarter": "Q1'26", "actual": 1.80, "estimate": 2.15, "surprise_pct": -16.28},
        ]
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "miss"

    def test_eps_inline(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = [
            {"quarter": "Q1'26", "actual": 2.15, "estimate": 2.14, "surprise_pct": 0.47},
        ]
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        eps = next((bm for bm in beat_miss if bm["metric"] == "EPS"), None)
        assert eps is not None
        assert eps["verdict"] == "inline"

    def test_no_eps_history_returns_empty(self):
        results = _make_agent_results()
        results["earnings"]["data"]["eps_history"] = []
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        assert len(beat_miss) == 0

    def test_no_earnings_data_returns_empty(self):
        results = _make_agent_results(earnings=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        beat_miss = agent._compute_beat_miss()
        assert len(beat_miss) == 0


class TestSectorTemplates:
    """Tests for sector KPI template selection."""

    def test_technology_sector_returns_tech_template(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        template = agent._get_sector_template()
        assert template == SECTOR_KPI_TEMPLATES["Technology"]
        assert "ARR" in template

    def test_unknown_sector_returns_default(self):
        results = _make_agent_results()
        results["fundamentals"]["data"]["sector"] = "Space Mining"
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        template = agent._get_sector_template()
        assert template == DEFAULT_KPI_TEMPLATE

    def test_no_fundamentals_returns_default(self):
        results = _make_agent_results(fundamentals=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, results)
        template = agent._get_sector_template()
        assert template == DEFAULT_KPI_TEMPLATE

    def test_sector_template_name_tracked(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        name = agent._get_sector_template_name()
        assert name == "Technology"


class TestDataCompleteness:
    """Tests for deterministic completeness score."""

    def test_full_data_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        score = agent._compute_data_completeness()
        assert score == pytest.approx(1.0, abs=0.01)

    def test_no_market_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(market=False))
        score = agent._compute_data_completeness()
        # Missing market (0.20) = 0.80
        assert score == pytest.approx(0.80, abs=0.01)

    def test_partial_earnings_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(has_transcript=False))
        score = agent._compute_data_completeness()
        # Earnings partial (0.15 instead of 0.50) + fundamentals(0.30) + market(0.20) = 0.65
        assert score == pytest.approx(0.65, abs=0.01)

    def test_no_earnings_completeness(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results(earnings=False))
        score = agent._compute_data_completeness()
        # Missing earnings (0.50) = 0.50
        assert score == pytest.approx(0.50, abs=0.01)
