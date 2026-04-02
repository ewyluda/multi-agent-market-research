"""Tests for the EarningsAgent."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.earnings_agent import EarningsAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────


SAMPLE_TRANSCRIPT = {
    "quarter": 1,
    "year": 2026,
    "date": "2026-01-30",
    "content": (
        "Good afternoon. Welcome to the Q1 2026 earnings call. "
        "Revenue came in at $124.3 billion, exceeding our guidance of $117 to $121 billion. "
        "EPS of $2.40 versus consensus of $2.35. Gross margin expanded 80 basis points year over year. "
        "We are raising our full-year revenue guidance to $125 billion to $130 billion. "
        "EPS guidance is now $2.42 to $2.50, up from $2.28 to $2.35. "
        "Capital expenditure expected at $13 billion, up from prior $11 billion. "
        "We announced a $110 billion share buyback authorization. "
        "China revenue declined 2% quarter over quarter. "
        "\n\nQuestion-and-Answer Session\n\n"
        "Erik Woodring, Morgan Stanley: How is Apple Intelligence adoption tracking? "
        "Tim Cook: We are seeing 60% plus adoption on supported devices with incredible engagement. "
        "Michael Ng, Goldman Sachs: Can you quantify the China competitive impact? "
        "Luca Maestri: Competitive dynamics exist but our installed base loyalty and Services attach rate are durable. "
        "Toni Sacconaghi, Bernstein: What drives margin expansion? "
        "Luca Maestri: Services mix shift and favorable component pricing. We guide similar or better margins next quarter."
    ),
    "symbol": "AAPL",
    "data_source": "fmp",
}

SAMPLE_EARNINGS_HISTORY = {
    "eps_history": [
        {"date": "2026-01-30", "reported_eps": 2.40, "estimated_eps": 2.35},
        {"date": "2025-10-31", "reported_eps": 2.18, "estimated_eps": 2.10},
        {"date": "2025-07-31", "reported_eps": 1.95, "estimated_eps": 2.00},
        {"date": "2025-04-30", "reported_eps": 1.82, "estimated_eps": 1.78},
    ],
    "latest_eps": {"reported_eps": 2.40, "estimated_eps": 2.35},
    "data_source": "fmp",
}


@pytest.fixture
def agent(test_config):
    agent = EarningsAgent("AAPL", test_config)
    agent._data_provider = AsyncMock()
    return agent


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestEarningsAgentFetchData:

    @pytest.mark.asyncio
    async def test_fetch_data_returns_transcripts_and_earnings(self, agent):
        agent._data_provider.get_earnings_transcripts = AsyncMock(
            return_value=[SAMPLE_TRANSCRIPT]
        )
        agent._data_provider.get_earnings = AsyncMock(
            return_value=SAMPLE_EARNINGS_HISTORY
        )

        raw = await agent.fetch_data()

        assert "transcripts" in raw
        assert "earnings_history" in raw
        assert len(raw["transcripts"]) == 1
        assert raw["transcripts"][0]["quarter"] == 1
        agent._data_provider.get_earnings_transcripts.assert_awaited_once_with(
            "AAPL", num_quarters=4
        )

    @pytest.mark.asyncio
    async def test_fetch_data_empty_transcripts(self, agent):
        agent._data_provider.get_earnings_transcripts = AsyncMock(return_value=[])
        agent._data_provider.get_earnings = AsyncMock(return_value=SAMPLE_EARNINGS_HISTORY)

        raw = await agent.fetch_data()

        assert raw["transcripts"] == []

    def test_agent_type(self, agent):
        assert agent.get_agent_type() == "earnings"


class TestEarningsAgentAnalyze:

    MOCK_LLM_RESPONSE = json.dumps({
        "highlights": [
            {"tag": "BEAT", "text": "Revenue of $124.3B exceeded consensus"},
            {"tag": "NEW", "text": "Announced $110B share buyback"},
            {"tag": "WATCH", "text": "China revenue declined 2% QoQ"},
        ],
        "guidance": [
            {"metric": "Revenue", "prior": "$117-121B", "current": "$125-130B", "direction": "raised"},
            {"metric": "EPS", "prior": "$2.28-2.35", "current": "$2.42-2.50", "direction": "raised"},
        ],
        "qa_highlights": [
            {
                "analyst": "Erik Woodring",
                "firm": "Morgan Stanley",
                "topic": "AI Strategy",
                "question": "How is Apple Intelligence adoption tracking?",
                "answer": "Management highlighted 60%+ adoption rate on supported devices.",
            },
        ],
        "tone_analysis": {
            "confidence": 85,
            "specificity": 62,
            "defensiveness": 20,
            "forward_looking": 78,
            "hedging": 45,
        },
        "tone": "confident",
        "guidance_direction": "raised",
        "stance": "bullish",
        "analysis": "Strong quarter with beats across revenue and EPS.",
    })

    @pytest.mark.asyncio
    async def test_analyze_returns_structured_output(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            return_value=self.MOCK_LLM_RESPONSE,
        ):
            result = await agent.analyze(raw_data)

        assert result["tone"] == "confident"
        assert result["guidance_direction"] == "raised"
        assert result["stance"] == "bullish"
        assert len(result["highlights"]) == 3
        assert result["highlights"][0]["tag"] == "BEAT"
        assert len(result["guidance"]) == 2
        assert len(result["qa_highlights"]) == 1
        assert result["tone_analysis"]["confidence"] == 85
        assert "analysis" in result
        assert result["data_source"] == "fmp"

    @pytest.mark.asyncio
    async def test_analyze_builds_eps_history(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            return_value=self.MOCK_LLM_RESPONSE,
        ):
            result = await agent.analyze(raw_data)

        assert "eps_history" in result
        assert len(result["eps_history"]) == 4
        assert result["eps_history"][0]["actual"] == 2.40
        assert result["eps_history"][0]["estimate"] == 2.35
        assert abs(result["eps_history"][0]["surprise_pct"] - 2.13) < 0.1

    @pytest.mark.asyncio
    async def test_analyze_empty_transcripts(self, agent):
        raw_data = {"transcripts": [], "earnings_history": {}}

        result = await agent.analyze(raw_data)

        assert result["stance"] == "neutral"
        assert "no earnings call transcripts" in result["analysis"].lower()

    @pytest.mark.asyncio
    async def test_analyze_llm_failure_fallback(self, agent):
        raw_data = {
            "transcripts": [SAMPLE_TRANSCRIPT],
            "earnings_history": SAMPLE_EARNINGS_HISTORY,
        }

        with patch.object(
            agent, "_call_llm", new_callable=AsyncMock,
            side_effect=Exception("LLM timeout"),
        ):
            result = await agent.analyze(raw_data)

        # Should return a fallback result, not raise
        assert result["stance"] == "neutral"
        assert "data_source" in result
