"""Tests for NarrativeAgent — models, data fetching, LLM flow, guardrails."""

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import QuarterlyInflection, YearSection, NarrativeChapter, NarrativeOutput
from src.agents.narrative_agent import NarrativeAgent


class TestNarrativeModels:
    """Pydantic model validation tests."""

    def test_quarterly_inflection_valid(self):
        qi = QuarterlyInflection(
            quarter="Q2'25",
            headline="First China revenue decline in 3 years",
            details="China revenue fell 8% YoY driven by Huawei competition and macro weakness.",
            impact="negative",
        )
        assert qi.impact == "negative"
        assert qi.quarter == "Q2'25"

    def test_year_section_valid(self):
        ys = YearSection(
            year=2024,
            headline="Steady growth with services acceleration",
            revenue_trajectory="Revenue grew 8% to $383B driven by services.",
            margin_story="Gross margin expanded 100bps to 46% on services mix shift.",
            strategic_moves=["Vision Pro launch", "India manufacturing expansion"],
            management_commentary="CEO emphasized AI integration across product lines.",
            capital_allocation="$90B buyback authorization, 4% dividend increase.",
            quarterly_inflections=[
                QuarterlyInflection(
                    quarter="Q3'24",
                    headline="China weakness emerged",
                    details="First YoY decline in Greater China revenue.",
                    impact="negative",
                )
            ],
        )
        assert ys.year == 2024
        assert len(ys.quarterly_inflections) == 1
        assert len(ys.strategic_moves) == 2

    def test_year_section_no_inflections(self):
        ys = YearSection(
            year=2023,
            headline="Quiet year of consolidation",
            revenue_trajectory="Revenue flat at $355B.",
            margin_story="Margins held steady.",
            strategic_moves=[],
            management_commentary="Focus on operational efficiency.",
            capital_allocation="Continued buybacks.",
            quarterly_inflections=[],
        )
        assert len(ys.quarterly_inflections) == 0

    def test_narrative_chapter_valid(self):
        nc = NarrativeChapter(
            title="The Services Transition",
            years_covered="2023-2025",
            narrative="Apple's services business grew from 20% to 28% of revenue over three years.",
            evidence=["Services revenue $85B in 2023", "Services revenue $110B in 2025"],
        )
        assert nc.title == "The Services Transition"
        assert len(nc.evidence) == 2

    def test_narrative_output_valid(self):
        output = NarrativeOutput(
            company_arc="Apple transitioned from hardware dependence to a services-led model.",
            year_sections=[
                YearSection(
                    year=2024, headline="Growth year", revenue_trajectory="Up 8%.",
                    margin_story="Margins expanded.", strategic_moves=[], management_commentary="Positive.",
                    capital_allocation="Buybacks.", quarterly_inflections=[],
                )
            ],
            narrative_chapters=[
                NarrativeChapter(
                    title="AI Pivot", years_covered="2024-2025",
                    narrative="Invested heavily in AI.", evidence=["R&D up 20%"],
                )
            ],
            key_inflection_points=["Q3'24 China decline"],
            current_chapter="Navigating the AI transition while managing China headwinds.",
            years_covered=3,
            data_completeness=0.85,
            data_sources_used=["financials", "transcripts", "fundamentals"],
        )
        assert output.years_covered == 3
        assert len(output.year_sections) == 1
        assert len(output.narrative_chapters) == 1

    def test_narrative_output_completeness_clamped(self):
        with pytest.raises(ValidationError):
            NarrativeOutput(
                company_arc="x", year_sections=[], narrative_chapters=[],
                key_inflection_points=[], current_chapter="x",
                years_covered=0, data_completeness=1.5, data_sources_used=[],
            )


# ── Test Helpers ────────────────────────────────────────────────────────────


def _make_mock_financials(num_years=3):
    """Build mock financials with income_statement records for multiple years."""
    income = []
    for i in range(num_years):
        year = 2025 - i
        income.append({
            "period_ending": f"{year}-12-31",
            "fiscal_year": year,
            "revenue": (383 - i * 20) * 1e9,
            "gross_profit": (176 - i * 8) * 1e9,
            "operating_income": (115 - i * 5) * 1e9,
            "net_income": (97 - i * 4) * 1e9,
            "research_and_development": (27 + i * 1) * 1e9,
        })
    return {
        "income_statement": income,
        "balance_sheet": [{"period_ending": f"{2025-i}-12-31", "total_assets": 350e9} for i in range(num_years)],
        "cash_flow": [{"period_ending": f"{2025-i}-12-31", "free_cash_flow": 90e9} for i in range(num_years)],
        "data_source": "openbb",
    }


def _make_mock_transcripts(num_quarters=4):
    """Build mock transcript list."""
    transcripts = []
    for i in range(num_quarters):
        q = 4 - (i % 4)
        y = 2025 - (i // 4)
        transcripts.append({
            "quarter": q,
            "year": y,
            "date": f"{y}-{q*3:02d}-15",
            "content": f"Q{q} {y} earnings call transcript content. Management discussed growth and strategy.",
            "data_source": "fmp",
        })
    return transcripts


def _make_agent_results():
    """Build mock agent_results for latest analysis context."""
    return {
        "fundamentals": {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383e9,
                "revenue_growth": 0.08,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software.",
            },
        },
    }


class TestNarrativeDataFetching:
    """Tests for fetch_data() hybrid data sourcing."""

    @pytest.mark.asyncio
    async def test_fetch_data_calls_data_provider(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_financials = AsyncMock(return_value=_make_mock_financials())
        mock_dp.get_earnings_transcripts = AsyncMock(return_value=_make_mock_transcripts())
        agent._data_provider = mock_dp

        result = await agent.fetch_data()

        mock_dp.get_financials.assert_called_once_with("AAPL")
        mock_dp.get_earnings_transcripts.assert_called_once_with("AAPL", num_quarters=12)
        assert "financials" in result
        assert "transcripts" in result
        assert "agent_results" in result

    @pytest.mark.asyncio
    async def test_fetch_data_default_years(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        mock_dp = MagicMock()
        mock_dp.get_financials = AsyncMock(return_value=_make_mock_financials())
        mock_dp.get_earnings_transcripts = AsyncMock(return_value=_make_mock_transcripts())
        agent._data_provider = mock_dp

        await agent.fetch_data()

        # Default NARRATIVE_YEARS=3, so 3*4=12 quarters
        mock_dp.get_earnings_transcripts.assert_called_once_with("AAPL", num_quarters=12)


class TestNarrativeYearExtraction:
    """Tests for extracting years from financial data."""

    def test_extract_years_from_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(num_years=3)
        years = agent._extract_available_years(financials)
        assert years == [2023, 2024, 2025]

    def test_extract_years_empty_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        years = agent._extract_available_years(None)
        assert years == []

    def test_extract_years_empty_income(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        years = agent._extract_available_years({"income_statement": []})
        assert years == []


class TestNarrativeCompleteness:
    """Tests for data completeness scoring."""

    def test_full_completeness(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        assert score == pytest.approx(1.0, abs=0.01)

    def test_partial_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(1),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        # 1/3 * 0.60 + 1.0 * 0.30 + 0.10 = 0.20 + 0.30 + 0.10 = 0.60
        assert score == pytest.approx(0.60, abs=0.02)

    def test_no_transcripts(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=[],
            num_years_requested=3,
        )
        # 1.0 * 0.60 + 0 + 0.10 = 0.70
        assert score == pytest.approx(0.70, abs=0.01)

    def test_no_fundamentals_context(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, {})
        score = agent._compute_data_completeness(
            financials=_make_mock_financials(3),
            transcripts=_make_mock_transcripts(12),
            num_years_requested=3,
        )
        # 1.0 * 0.60 + 1.0 * 0.30 + 0 = 0.90
        assert score == pytest.approx(0.90, abs=0.01)

    def test_no_data_at_all(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}, "NARRATIVE_YEARS": 3}, {})
        score = agent._compute_data_completeness(
            financials=None,
            transcripts=[],
            num_years_requested=3,
        )
        assert score == pytest.approx(0.0, abs=0.01)
