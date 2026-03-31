"""Tests for LLM-powered council synthesis narrative agent."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.council_synthesis_agent import CouncilSynthesisAgent


@pytest.fixture
def agent_config():
    return {
        "LLM_PROVIDER": "anthropic",
        "llm_config": {
            "provider": "anthropic",
            "model": "claude-3-5-haiku-20241022",
            "api_key": "test-key",
            "temperature": 0.0,
            "max_tokens": 1024,
        },
        "AGENT_TIMEOUT": 30,
    }


@pytest.fixture
def sample_context():
    return {
        "council_results": [
            {"investor": "druckenmiller", "stance": "BULLISH", "qualitative_analysis": "Macro tailwind intact.", "key_observations": ["Strong momentum"]},
            {"investor": "marks", "stance": "BEARISH", "qualitative_analysis": "Cycle top risk.", "key_observations": ["Overvaluation"]},
        ],
        "thesis_health": {"overall_health": "WATCHING", "indicators": [{"name": "RSI", "status": "drifting"}]},
        "signal_contract": {"direction": "bullish", "confidence": {"raw": 0.75}},
        "validation": {"overall_status": "clean", "total_confidence_penalty": 0.0},
    }


class TestCouncilSynthesisAgent:
    def test_empty_report_on_no_context(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        report = agent._empty_narrative()
        assert report["fallback_used"] is True
        assert report["narrative"] == ""
        assert report["position_implication"] == ""
        assert report["watch_item"] == ""

    def test_parses_valid_llm_response(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        llm_text = json.dumps({
            "narrative": "The council is split. Druckenmiller sees macro tailwinds while Marks flags cycle-top risk.",
            "position_implication": "Hold with tighter stop at 140",
            "watch_item": "Fed rate decision on June 18",
        })
        result = agent._parse_narrative_response(llm_text)
        assert result["fallback_used"] is False
        assert "split" in result["narrative"]
        assert result["position_implication"] != ""
        assert result["watch_item"] != ""

    def test_malformed_response_returns_fallback(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        result = agent._parse_narrative_response("this is not json at all!!!")
        assert result["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_execute_no_context_returns_empty(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        result = await agent.execute()
        assert result["success"] is True
        assert result["data"]["fallback_used"] is True

    def test_prompt_includes_council_and_health(self, agent_config, sample_context):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        agent.set_synthesis_context(**sample_context)
        prompt = agent._build_synthesis_prompt()
        assert "druckenmiller" in prompt.lower()
        assert "marks" in prompt.lower()
        assert "WATCHING" in prompt
