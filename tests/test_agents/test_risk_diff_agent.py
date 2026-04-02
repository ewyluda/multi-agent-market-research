"""Tests for RiskDiffAgent — models, EDGAR integration, HTML parsing, LLM flow, guardrails."""

import pytest
from pydantic import ValidationError
from src.models import RiskTopic, RiskChange, RiskDiffOutput


class TestRiskDiffModels:
    """Pydantic model validation tests."""

    def test_risk_topic_valid(self):
        rt = RiskTopic(
            topic="Supply Chain Concentration",
            severity="high",
            summary="Company depends on 3 suppliers for 80% of components.",
            text_excerpt="We rely on a limited number of suppliers...",
        )
        assert rt.severity == "high"
        assert rt.topic == "Supply Chain Concentration"

    def test_risk_change_valid(self):
        rc = RiskChange(
            risk_topic="Supply Chain Concentration",
            change_type="new",
            severity="high",
            current_text_excerpt="We now rely on a single supplier...",
            prior_text_excerpt="",
            analysis="New single-source dependency introduces material risk.",
        )
        assert rc.change_type == "new"
        assert rc.prior_text_excerpt == ""

    def test_risk_change_escalated(self):
        rc = RiskChange(
            risk_topic="Regulatory Risk",
            change_type="escalated",
            severity="high",
            current_text_excerpt="Material adverse effect on operations is likely...",
            prior_text_excerpt="Could impact our results...",
            analysis="Language escalated from 'could impact' to 'material adverse effect'.",
        )
        assert rc.change_type == "escalated"

    def test_risk_diff_output_full_diff(self):
        output = RiskDiffOutput(
            new_risks=[
                RiskChange(
                    risk_topic="AI Regulation",
                    change_type="new",
                    severity="medium",
                    current_text_excerpt="New AI regulations may...",
                    prior_text_excerpt="",
                    analysis="Newly disclosed risk from emerging AI regulation.",
                )
            ],
            removed_risks=[],
            changed_risks=[],
            risk_score=65.0,
            risk_score_delta=5.0,
            top_emerging_threats=["AI regulation exposure", "China supply chain"],
            summary="Risk profile moderately elevated due to new AI regulatory disclosure.",
            current_risk_inventory=[
                RiskTopic(
                    topic="AI Regulation",
                    severity="medium",
                    summary="New AI rules could affect operations.",
                    text_excerpt="New AI regulations may...",
                )
            ],
            filings_compared=[
                {"type": "10-K", "date": "2025-02-15", "accession_number": "0001234-25-000001"},
                {"type": "10-K", "date": "2024-02-15", "accession_number": "0001234-24-000001"},
            ],
            has_diff=True,
            extraction_methods=["pattern", "pattern"],
            data_completeness=0.85,
            data_sources_used=["fmp_filings", "edgar_html"],
        )
        assert output.has_diff is True
        assert len(output.new_risks) == 1
        assert output.risk_score == 65.0

    def test_risk_diff_output_inventory_only(self):
        output = RiskDiffOutput(
            new_risks=[],
            removed_risks=[],
            changed_risks=[],
            risk_score=50.0,
            risk_score_delta=0.0,
            top_emerging_threats=[],
            summary="Single filing available; risk inventory only.",
            current_risk_inventory=[
                RiskTopic(
                    topic="Market Competition",
                    severity="medium",
                    summary="Intense competition in key markets.",
                    text_excerpt="We face intense competition...",
                )
            ],
            filings_compared=[
                {"type": "10-K", "date": "2025-02-15", "accession_number": "0001234-25-000001"},
            ],
            has_diff=False,
            extraction_methods=["pattern"],
            data_completeness=0.40,
            data_sources_used=["fmp_filings", "edgar_html"],
        )
        assert output.has_diff is False
        assert len(output.new_risks) == 0
        assert output.risk_score_delta == 0.0

    def test_risk_diff_output_completeness_bounds(self):
        with pytest.raises(ValidationError):
            RiskDiffOutput(
                new_risks=[], removed_risks=[], changed_risks=[],
                risk_score=50.0, risk_score_delta=0.0,
                top_emerging_threats=[], summary="x",
                current_risk_inventory=[],
                filings_compared=[], has_diff=False,
                extraction_methods=[], data_completeness=1.5,
                data_sources_used=[],
            )

    def test_risk_diff_output_empty(self):
        output = RiskDiffOutput(
            new_risks=[], removed_risks=[], changed_risks=[],
            risk_score=0.0, risk_score_delta=0.0,
            top_emerging_threats=[], summary="No filings available.",
            current_risk_inventory=[],
            filings_compared=[], has_diff=False,
            extraction_methods=[], data_completeness=0.0,
            data_sources_used=[],
        )
        assert output.data_completeness == 0.0
        assert output.current_risk_inventory == []
