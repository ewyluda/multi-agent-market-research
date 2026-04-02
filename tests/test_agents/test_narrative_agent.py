"""Tests for NarrativeAgent — models, data fetching, LLM flow, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import QuarterlyInflection, YearSection, NarrativeChapter, NarrativeOutput


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
