"""Tests for the EarningsAgent."""

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
