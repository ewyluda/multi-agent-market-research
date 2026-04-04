"""Tests for NarrativeAgent — models, data fetching, LLM flow, guardrails."""

import json as json_module

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


from src.llm_guardrails import validate_narrative_output


def _make_valid_narrative():
    """Build a valid narrative output dict."""
    return {
        "company_arc": "Apple transitioned from hardware to services over three years.",
        "year_sections": [
            {
                "year": 2023, "headline": "Consolidation year",
                "revenue_trajectory": "Revenue flat.", "margin_story": "Margins held.",
                "strategic_moves": [], "management_commentary": "Efficiency focus.",
                "capital_allocation": "Buybacks.", "quarterly_inflections": [],
            },
            {
                "year": 2024, "headline": "Growth resumed",
                "revenue_trajectory": "Revenue up 8%.", "margin_story": "Margins expanded.",
                "strategic_moves": ["Vision Pro launch"], "management_commentary": "AI focus.",
                "capital_allocation": "$90B buyback.",
                "quarterly_inflections": [
                    {"quarter": "Q3'24", "headline": "China decline", "details": "First decline.", "impact": "negative"},
                ],
            },
            {
                "year": 2025, "headline": "AI acceleration",
                "revenue_trajectory": "Revenue up 12%.", "margin_story": "Services mix lift.",
                "strategic_moves": ["AI assistant launch"], "management_commentary": "AI monetization.",
                "capital_allocation": "Continued buybacks.", "quarterly_inflections": [],
            },
        ],
        "narrative_chapters": [
            {
                "title": "The Services Transition",
                "years_covered": "2023-2025",
                "narrative": "Services grew from 20% to 28% of revenue.",
                "evidence": ["Services $85B in 2023", "Services $110B in 2025"],
            },
        ],
        "key_inflection_points": ["Q3'24 China decline", "AI assistant launch 2025"],
        "current_chapter": "Navigating AI transition.",
        "years_covered": 3,
        "data_completeness": 0.85,
        "data_sources_used": ["financials", "transcripts"],
    }


class TestNarrativeGuardrails:
    """Tests for validate_narrative_output() in llm_guardrails.py."""

    def test_valid_narrative_passes(self):
        narrative = _make_valid_narrative()
        validated, warnings = validate_narrative_output(narrative)
        assert validated["company_arc"] != ""
        assert isinstance(warnings, list)

    def test_year_ordering_flagged(self):
        narrative = _make_valid_narrative()
        # Reverse year order (should be chronological)
        narrative["year_sections"].reverse()
        validated, warnings = validate_narrative_output(narrative)
        assert any("order" in w.lower() or "chronolog" in w.lower() for w in warnings)

    def test_too_many_inflections_flagged(self):
        narrative = _make_valid_narrative()
        # Add 4 inflections to one year (>3 is suspicious)
        narrative["year_sections"][1]["quarterly_inflections"] = [
            {"quarter": f"Q{i}'24", "headline": f"Event {i}", "details": "Details.", "impact": "pivotal"}
            for i in range(1, 5)
        ]
        validated, warnings = validate_narrative_output(narrative)
        assert any("inflection" in w.lower() for w in warnings)

    def test_single_year_chapter_flagged(self):
        narrative = _make_valid_narrative()
        narrative["narrative_chapters"] = [
            {
                "title": "Single Year Theme",
                "years_covered": "2024",
                "narrative": "Only about one year.",
                "evidence": [],
            },
        ]
        validated, warnings = validate_narrative_output(narrative)
        assert any("chapter" in w.lower() or "span" in w.lower() for w in warnings)

    def test_data_completeness_preserved(self):
        narrative = _make_valid_narrative()
        narrative["data_completeness"] = 0.85
        validated, warnings = validate_narrative_output(narrative)
        # Completeness should be preserved (not overridden — narrative doesn't have agent_results in guardrails)
        assert validated["data_completeness"] == 0.85


# ── Mock LLM Responses ────────────────────────────────────────────────────────


MOCK_PASS1_RESPONSE = json_module.dumps({
    "per_year": [
        {
            "year": 2023, "revenue": "$355B", "revenue_growth": "1%",
            "gross_margin": "44%", "operating_margin": "29%",
            "key_events": ["iPhone 15 launch"],
            "management_themes": ["Operational efficiency"],
            "capital_moves": ["Continued buybacks"],
            "inflection_quarters": [],
        },
        {
            "year": 2024, "revenue": "$383B", "revenue_growth": "8%",
            "gross_margin": "46%", "operating_margin": "31%",
            "key_events": ["Vision Pro launch", "AI features announced"],
            "management_themes": ["AI integration", "Services growth"],
            "capital_moves": ["$90B buyback authorization"],
            "inflection_quarters": [
                {"quarter": "Q3'24", "event": "First China revenue decline in 3 years"},
            ],
        },
        {
            "year": 2025, "revenue": "$430B", "revenue_growth": "12%",
            "gross_margin": "47%", "operating_margin": "32%",
            "key_events": ["AI assistant launch", "India expansion"],
            "management_themes": ["AI monetization", "Geographic diversification"],
            "capital_moves": ["Increased capex for AI infrastructure"],
            "inflection_quarters": [],
        },
    ],
    "cross_year_themes": [
        "Services transition accelerating",
        "China exposure becoming a headwind",
        "AI as the next growth vector",
    ],
})

MOCK_PASS2_RESPONSE = json_module.dumps({
    "company_arc": "Over three years Apple evolved from a mature hardware company into an AI-powered services platform, navigating China headwinds while accelerating growth.",
    "year_sections": [
        {
            "year": 2023, "headline": "Consolidation: Flat revenue, margin preservation",
            "revenue_trajectory": "Revenue flat at $355B as iPhone cycle matured.",
            "margin_story": "Gross margin held at 44% through operational discipline.",
            "strategic_moves": ["iPhone 15 launch"],
            "management_commentary": "Focus on operational efficiency and services scale.",
            "capital_allocation": "Continued aggressive buyback program.",
            "quarterly_inflections": [],
        },
        {
            "year": 2024, "headline": "Inflection: Growth resumes, Vision Pro bets big",
            "revenue_trajectory": "Revenue accelerated to $383B (+8%) driven by services and iPhone upgrades.",
            "margin_story": "Gross margin expanded to 46% on services mix shift.",
            "strategic_moves": ["Vision Pro launch", "AI features announced across product line"],
            "management_commentary": "CEO pivoted messaging to AI integration as the next platform shift.",
            "capital_allocation": "$90B buyback authorization — largest in tech history.",
            "quarterly_inflections": [
                {"quarter": "Q3'24", "headline": "China cracks emerge", "details": "First YoY revenue decline in Greater China, driven by Huawei competition and macro headwinds.", "impact": "negative"},
            ],
        },
        {
            "year": 2025, "headline": "Acceleration: AI-driven growth hits its stride",
            "revenue_trajectory": "Revenue surged to $430B (+12%), the fastest growth in 4 years.",
            "margin_story": "Gross margin expanded further to 47% as AI services monetized.",
            "strategic_moves": ["AI assistant launch", "India manufacturing expansion"],
            "management_commentary": "AI monetization became the dominant narrative on earnings calls.",
            "capital_allocation": "Capex rose 30% for AI infrastructure while buybacks continued.",
            "quarterly_inflections": [],
        },
    ],
    "narrative_chapters": [
        {
            "title": "The Services Flywheel",
            "years_covered": "2023-2025",
            "narrative": "Services grew from 20% to 28% of revenue, becoming the primary margin driver and providing recurring revenue that smoothed hardware cycles.",
            "evidence": ["Services grew from $85B to $110B", "Gross margin expansion of 300bps driven by mix"],
        },
        {
            "title": "The China Question",
            "years_covered": "2024-2025",
            "narrative": "China shifted from growth engine to headwind as Huawei's resurgence and macro weakness eroded market share.",
            "evidence": ["Q3'24 first China decline", "Management pivoted messaging to India opportunity"],
        },
    ],
    "key_inflection_points": [
        "Q3'24: First China revenue decline signaled geographic risk",
        "Vision Pro launch marked Apple's next hardware bet",
        "2025 AI assistant launch as platform shift catalyst",
    ],
    "current_chapter": "Apple is in the early innings of AI monetization, with services growth providing a floor while China remains the key risk variable.",
})


class TestNarrativeLLMFlow:
    """Tests for two-pass LLM flow with mocked responses."""

    @pytest.mark.asyncio
    async def test_full_two_pass_flow(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            return MOCK_PASS2_RESPONSE

        mock_financials = _make_mock_financials(3)
        mock_transcripts = _make_mock_transcripts(12)

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            with patch("src.llm_guardrails.validate_narrative_output", return_value=({
                **json_module.loads(MOCK_PASS2_RESPONSE),
                "years_covered": 3,
                "data_completeness": 1.0,
                "data_sources_used": ["financials", "transcripts", "fundamentals"],
            }, [])):
                result = await agent.analyze({
                    "financials": mock_financials,
                    "transcripts": mock_transcripts,
                    "agent_results": _make_agent_results(),
                })

        assert call_count == 2
        assert result["company_arc"] != ""
        assert len(result["year_sections"]) == 3
        assert len(result["narrative_chapters"]) == 2
        assert result["years_covered"] == 3

    @pytest.mark.asyncio
    async def test_pass1_failure_returns_empty(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze({
                "financials": _make_mock_financials(3),
                "transcripts": _make_mock_transcripts(12),
                "agent_results": _make_agent_results(),
            })

        assert "error" in result or "insufficient" in result.get("company_arc", "").lower()
        assert result["year_sections"] == []

    @pytest.mark.asyncio
    async def test_pass2_failure_returns_fallback(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}, "NARRATIVE_YEARS": 3}, _make_agent_results())
        call_count = 0

        async def mock_call_llm(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MOCK_PASS1_RESPONSE
            raise Exception("Pass 2 failed")

        with patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze({
                "financials": _make_mock_financials(3),
                "transcripts": _make_mock_transcripts(12),
                "agent_results": _make_agent_results(),
            })

        assert result.get("pass2_failed") is True
        assert len(result["year_sections"]) == 3
        assert "extracted_facts" in result

    @pytest.mark.asyncio
    async def test_no_financials_returns_empty(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        result = await agent.analyze({
            "financials": None,
            "transcripts": [],
            "agent_results": _make_agent_results(),
        })

        assert result["years_covered"] == 0
        assert result["year_sections"] == []


class TestNarrativePrompt:
    """Tests for prompt construction."""

    def test_pass1_prompt_contains_ticker(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "AAPL" in prompt

    def test_pass1_prompt_contains_financials(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "FY2025" in prompt or "2025" in prompt
        assert "FY2023" in prompt or "2023" in prompt

    def test_pass2_prompt_contains_facts(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        facts = json_module.loads(MOCK_PASS1_RESPONSE)
        prompt = agent._build_pass2_prompt(facts, "AAPL")
        assert "AAPL" in prompt
        assert "$355B" in prompt  # 2023 revenue from facts

    def test_pass1_prompt_includes_guardrail_instructions(self):
        agent = NarrativeAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        financials = _make_mock_financials(3)
        transcripts = _make_mock_transcripts(4)
        years = agent._extract_available_years(financials)
        prompt = agent._build_pass1_prompt(financials, transcripts, years)
        assert "Do NOT infer" in prompt or "Do not infer" in prompt
