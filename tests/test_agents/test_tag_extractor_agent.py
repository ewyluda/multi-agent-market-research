"""Tests for TagExtractorAgent — models, taxonomy, LLM flow."""

import pytest
import json as json_module
from unittest.mock import patch as mock_patch, AsyncMock as MockAsync
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


MOCK_LLM_RESPONSE = json_module.dumps({
    "tags": [
        {"tag": "recurring_revenue", "category": "business_model", "evidence": "Services at 28% of revenue with high retention"},
        {"tag": "services_led", "category": "business_model", "evidence": "Services growing faster than hardware"},
        {"tag": "ai_integration", "category": "growth_drivers", "evidence": "AI assistant launched across product line"},
        {"tag": "pricing_power", "category": "growth_drivers", "evidence": "Premium pricing maintained despite competition"},
        {"tag": "consistent_buybacks", "category": "quality_indicators", "evidence": "$90B buyback authorization"},
        {"tag": "strong_free_cash_flow", "category": "quality_indicators", "evidence": "FCF of $90B annually"},
    ],
})


class TestTagExtractorLLMFlow:
    """Tests for LLM-based tag extraction."""

    @pytest.mark.asyncio
    async def test_full_flow_extracts_valid_tags(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_call_llm(prompt):
            return MOCK_LLM_RESPONSE

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 6
        tag_names = {t["tag"] for t in result["tags"]}
        assert "recurring_revenue" in tag_names
        assert "ai_integration" in tag_names

    @pytest.mark.asyncio
    async def test_invalid_tags_filtered_out(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        response_with_invalid = json_module.dumps({
            "tags": [
                {"tag": "recurring_revenue", "category": "business_model", "evidence": "Valid"},
                {"tag": "totally_made_up", "category": "nonsense", "evidence": "Invalid"},
            ],
        })

        async def mock_call_llm(prompt):
            return response_with_invalid

        with mock_patch.object(agent, "_call_llm", side_effect=mock_call_llm):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 1
        assert result["tags"][0]["tag"] == "recurring_revenue"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, _make_agent_results())

        async def mock_fail(prompt):
            raise Exception("LLM unavailable")

        with mock_patch.object(agent, "_call_llm", side_effect=mock_fail):
            result = await agent.analyze(agent.agent_results)

        assert result["tags_count"] == 0
        assert result["tags"] == []

    @pytest.mark.asyncio
    async def test_empty_context_returns_empty(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {"provider": "none"}}, {})

        result = await agent.analyze({})

        assert result["tags_count"] == 0


class TestTagExtractorPrompt:
    """Tests for prompt construction."""

    def test_prompt_contains_taxonomy(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        prompt = agent._build_prompt(context)
        assert "recurring_revenue" in prompt
        assert "activist_involved" in prompt
        assert "business_model" in prompt
        assert "risk_flags" in prompt

    def test_prompt_contains_company_context(self):
        agent = TagExtractorAgent("AAPL", {"llm_config": {}}, _make_agent_results())
        context = agent._build_context()
        prompt = agent._build_prompt(context)
        assert "Apple Inc." in prompt
        assert "Technology" in prompt
