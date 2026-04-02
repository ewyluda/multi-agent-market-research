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


from src.agents.tag_extractor_agent import TagExtractorAgent, TAG_TAXONOMY, ALL_TAGS, TAG_TO_CATEGORY


def _make_agent_results():
    """Build mock agent_results for tag extraction."""
    return {
        "fundamentals": {
            "success": True,
            "data": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "revenue": 383e9,
                "gross_margin": 0.46,
                "business_description": "Designs consumer electronics and software services.",
                "data_source": "fmp",
            },
        },
        "news": {
            "success": True,
            "data": {
                "articles": [
                    {"title": "Apple AI push accelerates", "summary": "New AI features announced."},
                    {"title": "Services hit all-time high", "summary": "Recurring revenue grows."},
                ],
                "data_source": "tavily",
            },
        },
    }


class TestTagTaxonomy:
    """Tests for the fixed tag taxonomy."""

    def test_taxonomy_has_5_categories(self):
        assert len(TAG_TAXONOMY) == 5

    def test_all_tags_count(self):
        assert len(ALL_TAGS) == 36

    def test_tag_to_category_mapping(self):
        assert TAG_TO_CATEGORY["recurring_revenue"] == "business_model"
        assert TAG_TO_CATEGORY["activist_involved"] == "corporate_events"
        assert TAG_TO_CATEGORY["pricing_power"] == "growth_drivers"
        assert TAG_TO_CATEGORY["debt_heavy"] == "risk_flags"
        assert TAG_TO_CATEGORY["high_roic"] == "quality_indicators"

    def test_no_duplicate_tags_across_categories(self):
        all_tags = []
        for tags in TAG_TAXONOMY.values():
            all_tags.extend(tags)
        assert len(all_tags) == len(set(all_tags))


class TestTagExtractorContext:
    """Tests for context building from agent results."""

    def test_builds_context_from_agent_results(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        assert "Apple Inc." in context
        assert "Technology" in context

    def test_handles_missing_agents(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, {})
        context = agent._build_context()
        assert "AAPL" in context  # At minimum, ticker should be present

    def test_validates_tags_against_taxonomy(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        raw_tags = [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs"},
            {"tag": "made_up_tag", "category": "business_model", "evidence": "Fake"},
            {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Moat"},
        ]
        valid = agent._filter_valid_tags(raw_tags)
        assert len(valid) == 2
        assert all(t["tag"] in ALL_TAGS for t in valid)
