"""Tests for EarningsReviewAgent — models, deterministic, LLM, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import BeatMiss, GuidanceDelta, KPIRow, EarningsReviewOutput


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
