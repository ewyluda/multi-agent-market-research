"""Tests for the LLM-powered council validator agent."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.council_validator_agent import CouncilValidatorAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def council_results():
    """Minimal council results with one investor."""
    return [
        {
            "investor": "druckenmiller",
            "stance": "BULLISH",
            "thesis_health": "INTACT",
            "qualitative_analysis": "Macro tailwind intact. Fed is dovish and liquidity is expanding.",
            "key_observations": [
                "Fed cutting rates supports risk assets",
                "Revenue growth accelerating to 30%",
            ],
            "if_then_scenarios": [
                {
                    "type": "macro",
                    "condition": "If Fed reverses course and hikes",
                    "action": "then exit position",
                    "conviction": "high",
                }
            ],
        }
    ]


@pytest.fixture
def agent_results():
    """Minimal agent results for validation."""
    return {
        "macro": {
            "success": True,
            "data": {
                "economic_cycle": "expansion",
                "risk_environment": "risk_on",
                "fed_funds_rate": 4.5,
            },
        },
        "fundamentals": {
            "success": True,
            "data": {
                "key_metrics": {"revenue_growth": 0.18},
            },
        },
    }


@pytest.fixture
def validator(test_config):
    return CouncilValidatorAgent("AAPL", test_config)


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestCouncilValidatorAgent:

    def test_agent_type(self, validator):
        assert validator.get_agent_type() == "council_validator"

    @pytest.mark.asyncio
    async def test_returns_empty_report_when_no_council_results(self, validator):
        validator.set_council_context(council_results=[], agent_results={})
        result = await validator.execute()
        assert result["success"] is True
        report = result["data"]
        assert report["total_claims_checked"] == 0
        assert report["total_contradictions"] == 0
        assert report["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_returns_fallback_when_llm_fails(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )
        # No API key configured → LLM call will fail
        validator.config["llm_config"] = {"provider": "anthropic", "api_key": ""}
        result = await validator.execute()
        assert result["success"] is True
        report = result["data"]
        assert report["fallback_used"] is True
        assert report["confidence_penalty"] == 0.0

    @pytest.mark.asyncio
    async def test_parses_llm_validation_response(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )

        mock_response = json.dumps({
            "investor_validations": [
                {
                    "investor": "druckenmiller",
                    "claims": [
                        {
                            "claim": "Macro tailwind intact",
                            "verdict": "supported",
                            "evidence": "Macro data confirms expansion and risk_on"
                        },
                        {
                            "claim": "Revenue growth accelerating to 30%",
                            "verdict": "contradicted",
                            "evidence": "Fundamentals show revenue growth at 18%, not 30%",
                            "severity": "contradiction"
                        }
                    ]
                }
            ]
        })

        with patch.object(validator, "_call_llm", new_callable=AsyncMock, return_value=mock_response):
            result = await validator.execute()

        assert result["success"] is True
        report = result["data"]
        assert report["total_claims_checked"] == 2
        assert report["total_contradictions"] == 1
        assert report["confidence_penalty"] == 0.05
        assert len(report["investor_validations"]) == 1
        inv = report["investor_validations"][0]
        assert inv["investor"] == "druckenmiller"
        assert inv["claims_supported"] == 1
        assert inv["claims_contradicted"] == 1

    @pytest.mark.asyncio
    async def test_penalty_capped_at_025(self, validator, agent_results):
        """Even with many contradictions, council penalty caps at 0.25."""
        many_investors = []
        for name in ["druckenmiller", "munger", "dalio", "ptj", "marks", "buffett"]:
            many_investors.append({
                "investor": name,
                "stance": "BULLISH",
                "qualitative_analysis": "Everything is great.",
                "key_observations": ["growth is strong", "macro is favorable", "options bullish"],
                "if_then_scenarios": [],
            })

        validator.set_council_context(council_results=many_investors, agent_results=agent_results)

        mock_validations = []
        for inv in many_investors:
            mock_validations.append({
                "investor": inv["investor"],
                "claims": [
                    {"claim": c, "verdict": "contradicted", "evidence": "Data disagrees", "severity": "contradiction"}
                    for c in inv["key_observations"]
                ],
            })

        mock_response = json.dumps({"investor_validations": mock_validations})

        with patch.object(validator, "_call_llm", new_callable=AsyncMock, return_value=mock_response):
            result = await validator.execute()

        assert result["data"]["confidence_penalty"] <= 0.25


class TestPromptConstruction:

    def test_build_validation_prompt_includes_claims_and_data(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )
        prompt = validator._build_validation_prompt()
        assert "druckenmiller" in prompt.lower()
        assert "Macro tailwind intact" in prompt
        assert "macro" in prompt.lower()
        assert "revenue_growth" in prompt.lower() or "revenue growth" in prompt.lower()
