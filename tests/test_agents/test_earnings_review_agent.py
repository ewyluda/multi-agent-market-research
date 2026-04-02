"""Tests for EarningsReviewAgent — models, deterministic, LLM, guardrails."""

import pytest
import json as json_module
from unittest.mock import patch as mock_patch, AsyncMock as MockAsync
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


from src.llm_guardrails import validate_earnings_review_output


def _make_valid_review():
    """Build a valid earnings review output dict."""
    return {
        "executive_summary": "Strong quarter with EPS beat and raised guidance.",
        "beat_miss": [{"metric": "EPS", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63, "verdict": "beat"}],
        "guidance_deltas": [{"metric": "Revenue", "prior_value": "$90-92B", "new_value": "$93-95B", "direction": "raised"}],
        "kpi_table": [
            {"metric": "Gross Margin", "value": "46%", "prior_value": "45%", "yoy_change": "+1pp", "source": "reported"},
            {"metric": "ARR", "value": "$5.2B", "prior_value": "$4.8B", "yoy_change": "+8.3%", "source": "call_disclosed"},
        ],
        "management_tone": "confident",
        "notable_quotes": ["We see strong momentum in AI."],
        "thesis_impact": "Confirms bull case on growth.",
        "one_offs": ["$200M restructuring charge"],
        "sector_template": "Technology",
        "data_completeness": 0.85,
        "data_sources_used": ["earnings", "fundamentals"],
    }


class TestEarningsReviewGuardrails:
    """Tests for validate_earnings_review_output() in llm_guardrails.py."""

    def test_valid_review_passes_cleanly(self):
        review = _make_valid_review()
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert validated["executive_summary"] != ""
        assert isinstance(warnings, list)

    def test_unreasonable_kpi_flagged(self):
        review = _make_valid_review()
        review["kpi_table"].append(
            {"metric": "Gross Margin", "value": "150%", "prior_value": None, "yoy_change": None, "source": "reported"}
        )
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert any("margin" in w.lower() or "unreasonable" in w.lower() or "150" in w for w in warnings)

    def test_guidance_tone_contradiction_flagged(self):
        review = _make_valid_review()
        review["guidance_deltas"] = [{"metric": "Revenue", "prior_value": "$90B", "new_value": "$95B", "direction": "raised"}]
        results = _make_agent_results()
        results["earnings"]["data"]["tone"] = "defensive"
        validated, warnings = validate_earnings_review_output(review, results)
        assert any("guidance" in w.lower() or "tone" in w.lower() or "contradict" in w.lower() for w in warnings)

    def test_data_completeness_overridden(self):
        review = _make_valid_review()
        review["data_completeness"] = 0.99
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert validated["data_completeness"] != 0.99

    def test_beat_miss_sanity_check(self):
        review = _make_valid_review()
        # Verdict says beat but surprise is negative
        review["beat_miss"] = [{"metric": "EPS", "actual": 1.80, "estimate": 2.15, "surprise_pct": -16.28, "verdict": "beat"}]
        validated, warnings = validate_earnings_review_output(review, _make_agent_results())
        assert any("beat" in w.lower() or "verdict" in w.lower() or "mismatch" in w.lower() for w in warnings)


MOCK_LLM_RESPONSE = json_module.dumps({
    "executive_summary": "Apple delivered a strong Q1 with EPS beating estimates by 12%. Revenue guidance raised to $93-95B.",
    "guidance_deltas": [
        {"metric": "Revenue", "prior_value": "$90-92B", "new_value": "$93-95B", "direction": "raised"},
    ],
    "kpi_table": [
        {"metric": "Gross Margin", "value": "46%", "prior_value": "45%", "yoy_change": "+1pp", "source": "reported"},
        {"metric": "ARR", "value": "$5.2B", "prior_value": "$4.8B", "yoy_change": "+8.3%", "source": "call_disclosed"},
        {"metric": "R&D % of Revenue", "value": "7.2%", "prior_value": "6.8%", "yoy_change": "+0.4pp", "source": "calculated"},
    ],
    "management_tone": "confident",
    "notable_quotes": [
        "We see strong momentum in AI and expect it to be a meaningful revenue driver.",
        "Our services business continues to hit all-time highs.",
    ],
    "thesis_impact": "Confirms the bull case — growth is accelerating and guidance raise signals management confidence.",
    "one_offs": ["$200M restructuring charge related to workforce optimization"],
})


class TestEarningsReviewLLMFlow:
    """Tests for single-pass LLM flow with mocked responses."""

    @pytest.mark.asyncio
    async def test_full_flow_with_llm(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_call_llm(prompt):
            return MOCK_LLM_RESPONSE

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            with mock_patch("src.llm_guardrails.validate_earnings_review_output", return_value=({
                **json_module.loads(MOCK_LLM_RESPONSE),
                "beat_miss": [{"metric": "EPS", "actual": 2.40, "estimate": 2.15, "surprise_pct": 11.63, "verdict": "beat"}],
                "sector_template": "Technology",
                "data_completeness": 1.0,
                "data_sources_used": ["earnings", "fundamentals", "market"],
            }, [])):
                result = await agent.analyze(agent.agent_results)

        assert result["executive_summary"] != ""
        assert len(result["beat_miss"]) >= 1
        assert result["beat_miss"][0]["verdict"] == "beat"
        assert len(result["kpi_table"]) >= 3
        assert result["management_tone"] == "confident"
        assert result["sector_template"] == "Technology"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_partial(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with mock_patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze(agent.agent_results)

        # Should still have deterministic beat/miss
        assert result.get("partial") is True
        assert len(result["beat_miss"]) >= 1
        assert result["beat_miss"][0]["verdict"] == "beat"
        assert result["kpi_table"] == []

    @pytest.mark.asyncio
    async def test_no_transcript_returns_partial(self):
        results = _make_agent_results(has_transcript=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, results)

        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            return "{}"

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(results)

        assert call_count == 0  # LLM not called for partial
        assert result.get("partial") is True
        assert len(result["beat_miss"]) >= 1

    @pytest.mark.asyncio
    async def test_no_earnings_returns_empty(self):
        results = _make_agent_results(earnings=False)
        agent = EarningsReviewAgent("AAPL", {"llm_config": {"provider": "none"}}, results)

        result = await agent.analyze(results)

        # No earnings means no transcript → partial result path
        assert result.get("partial") is True
        assert result["beat_miss"] == []
        assert result["kpi_table"] == []


class TestEarningsReviewPrompt:
    """Tests for prompt construction."""

    def test_prompt_contains_ticker(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "AAPL" in prompt

    def test_prompt_contains_sector_template(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "ARR" in prompt  # Technology template includes ARR

    def test_prompt_contains_eps_history(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "2.40" in prompt or "Q1'26" in prompt

    def test_prompt_contains_market_context(self):
        agent = EarningsReviewAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        prompt = agent._build_prompt()
        assert "195" in prompt or "220" in prompt  # price or 52w high
