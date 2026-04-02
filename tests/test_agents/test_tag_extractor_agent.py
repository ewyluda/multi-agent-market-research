"""Tests for TagExtractorAgent — models, taxonomy, LLM flow."""

import pytest
from pydantic import ValidationError
from src.models import CompanyTag, TagExtractorOutput


class TestTagModels:
    """Pydantic model validation tests."""

    def test_company_tag_valid(self):
        tag = CompanyTag(
            tag="recurring_revenue",
            category="business_model",
            evidence="Services revenue 28% of total with high retention.",
        )
        assert tag.tag == "recurring_revenue"
        assert tag.category == "business_model"

    def test_company_tag_no_evidence(self):
        tag = CompanyTag(
            tag="debt_heavy",
            category="risk_flags",
        )
        assert tag.evidence is None

    def test_tag_extractor_output_valid(self):
        output = TagExtractorOutput(
            tags=[
                CompanyTag(tag="recurring_revenue", category="business_model", evidence="High retention."),
                CompanyTag(tag="ai_integration", category="growth_drivers", evidence="AI launched."),
            ],
            tags_count=2,
            data_sources_used=["fundamentals", "solution"],
        )
        assert output.tags_count == 2
        assert len(output.tags) == 2

    def test_tag_extractor_output_empty(self):
        output = TagExtractorOutput(
            tags=[],
            tags_count=0,
            data_sources_used=[],
        )
        assert output.tags_count == 0
