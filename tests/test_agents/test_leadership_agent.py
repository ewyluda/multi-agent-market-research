"""Tests for the Leadership Agent."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.leadership_agent import LeadershipAgent


@pytest.fixture
def leadership_config():
    """Test configuration for leadership agent."""
    return {
        "TAVILY_API_KEY": "test-api-key",
        "TAVILY_ENABLED": True,
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "LLM_PROVIDER": "anthropic",
        "LLM_MODEL": "claude-3-5-sonnet-20241022",
        "llm_config": {
            "provider": "anthropic",
            "api_key": "test-anthropic-key",
            "model": "claude-3-5-sonnet-20241022",
        },
    }


@pytest.fixture
def leadership_agent(leadership_config):
    """Create a LeadershipAgent instance for testing."""
    return LeadershipAgent("AAPL", leadership_config)


@pytest.fixture
def mock_tavily_articles():
    """Mock articles in the format returned by fetch_data (after processing)."""
    return [
        {
            "title": "Apple CEO Tim Cook's Leadership Journey",
            "source": "Reuters",
            "url": "https://example.com/cook-leadership",
            "published_at": "2026-01-15",
            "content": "Tim Cook has been CEO of Apple since 2011, bringing over 13 years of experience. Under his leadership, Apple has grown tremendously. He previously served as COO and has a strong operational background.",
            "snippet": "Profile of Apple's CEO",
            "relevance_score": 0.9,
        },
        {
            "title": "Apple Board of Directors Update",
            "source": "CNBC",
            "url": "https://example.com/apple-board",
            "published_at": "2026-02-01",
            "content": "Apple's board consists of 8 directors, 7 of whom are independent. The board has strong governance practices and regular meetings. 87% independent directors.",
            "snippet": "Board composition news",
            "relevance_score": 0.8,
        },
        {
            "title": "Apple Executive Team Stability",
            "source": "TechCrunch",
            "url": "https://example.com/apple-execs",
            "published_at": "2026-01-20",
            "content": "Apple's C-suite has remained stable with low turnover. Key executives like CFO Luca Maestri have been with the company for many years.",
            "snippet": "Executive team analysis",
            "relevance_score": 0.85,
        },
    ]


class TestLeadershipAgentFetchData:
    """Tests for the fetch_data method."""

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, leadership_agent, mock_tavily_articles):
        """Test successful data fetching with Tavily."""
        mock_tavily = MagicMock()
        mock_tavily.is_available = True
        # Mock the _client.search that _execute_tavily_search calls
        mock_tavily._client = MagicMock()
        mock_tavily._client.search = AsyncMock(return_value={
            "results": [
                {
                    "title": art["title"],
                    "source": art["source"],
                    "url": art["url"],
                    "published_date": art["published_at"],
                    "content": art["content"],
                    "raw_content": art["content"],
                    "score": art.get("relevance_score", 0.5),
                }
                for art in mock_tavily_articles
            ]
        })

        with patch("src.agents.leadership_agent.get_tavily_client", return_value=mock_tavily):
            with patch.object(leadership_agent, "_get_company_info", AsyncMock(return_value={
                "long_name": "Apple Inc",
                "short_name": "Apple"
            })):
                result = await leadership_agent.fetch_data()

        assert result["ticker"] == "AAPL"
        assert result["company_name"] == "Apple Inc"
        assert result["source"] == "tavily"
        assert len(result["articles"]) > 0
        assert "queries" in result

    @pytest.mark.asyncio
    async def test_fetch_data_tavily_unavailable(self, leadership_agent):
        """Test fallback when Tavily is unavailable."""
        mock_tavily = MagicMock()
        mock_tavily.is_available = False

        with patch("src.agents.leadership_agent.get_tavily_client", return_value=mock_tavily):
            with patch.object(leadership_agent, "_get_company_info", AsyncMock(return_value={
                "long_name": "Apple Inc",
                "short_name": "Apple"
            })):
                result = await leadership_agent.fetch_data()

        assert result["ticker"] == "AAPL"
        assert result["source"] == "tavily_unavailable"
        assert result["results"] == []


class TestLeadershipAgentAnalyze:
    """Tests for the analyze method."""

    @pytest.mark.asyncio
    async def test_analyze_produces_scorecard(self, leadership_agent):
        """Test that analyze produces a complete scorecard."""
        raw_data = {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "source": "tavily",
            "articles": [
                {
                    "title": "Apple CEO Tim Cook",
                    "content": "Tim Cook has been CEO for 13 years. Strong track record with extensive experience.",
                    "source": "Reuters",
                    "published_at": "2026-01-15",
                    "snippet": "",
                }
            ],
            "queries": ["query1", "query2"]
        }

        with patch.object(leadership_agent, "_generate_executive_summary", AsyncMock(return_value="Test summary")):
            result = await leadership_agent.analyze(raw_data)

        # Verify scorecard structure
        assert "overall_score" in result
        assert "grade" in result
        assert "four_capitals" in result
        assert "key_metrics" in result
        assert "red_flags" in result
        assert "executive_summary" in result

        # Verify four capitals
        capitals = result["four_capitals"]
        assert "individual" in capitals
        assert "relational" in capitals
        assert "organizational" in capitals
        assert "reputational" in capitals

        # Verify each capital has required fields
        for capital_name, capital_data in capitals.items():
            assert "score" in capital_data
            assert "grade" in capital_data
            assert "insights" in capital_data
            assert "red_flags" in capital_data
            assert 0 <= capital_data["score"] <= 100

    @pytest.mark.asyncio
    async def test_analyze_detects_red_flags(self, leadership_agent):
        """Test red flag detection in analysis."""
        raw_data = {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "source": "tavily",
            "articles": [
                {
                    "title": "CFO Departure",
                    "content": "The CFO resigned suddenly after only 18 months in the role. This follows the departure of two other senior executives in the past year.",
                    "source": "CNBC",
                    "published_at": "2026-02-01",
                    "snippet": "",
                }
            ],
            "queries": ["query1"]
        }

        with patch.object(leadership_agent, "_generate_executive_summary", AsyncMock(return_value="Test summary")):
            result = await leadership_agent.analyze(raw_data)

        # Should detect high turnover red flag
        assert len(result["red_flags"]) > 0
        flag_types = [f["type"] for f in result["red_flags"]]
        assert "high_turnover" in flag_types

    @pytest.mark.asyncio
    async def test_analyze_extracts_metrics(self, leadership_agent):
        """Test metric extraction from research data."""
        raw_data = {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "source": "tavily",
            "articles": [
                {
                    "title": "CEO Profile",
                    "content": "CEO has been appointed for 8.5 years. Board has 85% independent directors.",
                    "source": "Reuters",
                    "published_at": "2026-01-15",
                    "snippet": "",
                }
            ],
            "queries": ["query1"]
        }

        with patch.object(leadership_agent, "_generate_executive_summary", AsyncMock(return_value="Test summary")):
            result = await leadership_agent.analyze(raw_data)

        metrics = result["key_metrics"]
        # ceo_tenure_years extracted from "appointed for 8.5 years" pattern
        assert "ceo_tenure_years" in metrics or "board_independence_pct" in metrics


class TestLeadershipAgentGrading:
    """Tests for the grade calculation logic."""

    def test_grade_calculation_a_plus(self, leadership_agent):
        """Test A+ grade for scores 97-100."""
        assert leadership_agent._score_to_grade(100) == "A+"
        assert leadership_agent._score_to_grade(97) == "A+"

    def test_grade_calculation_a(self, leadership_agent):
        """Test A grade for scores 93-96."""
        assert leadership_agent._score_to_grade(96) == "A"
        assert leadership_agent._score_to_grade(93) == "A"

    def test_grade_calculation_a_minus(self, leadership_agent):
        """Test A- grade for scores 90-92."""
        assert leadership_agent._score_to_grade(92) == "A-"
        assert leadership_agent._score_to_grade(90) == "A-"

    def test_grade_calculation_b_plus(self, leadership_agent):
        """Test B+ grade for scores 87-89."""
        assert leadership_agent._score_to_grade(89) == "B+"
        assert leadership_agent._score_to_grade(87) == "B+"

    def test_grade_calculation_f(self, leadership_agent):
        """Test F grade for scores below 60."""
        assert leadership_agent._score_to_grade(59) == "F"
        assert leadership_agent._score_to_grade(0) == "F"


class TestLeadershipAgentRedFlagDetection:
    """Tests for red flag detection patterns."""

    def test_detect_high_turnover(self, leadership_agent):
        """Test detection of high turnover red flags."""
        articles = [{"title": "CFO departure", "content": "The cfo resigned suddenly after disagreements with the CEO."}]
        flags = leadership_agent._detect_red_flags(articles)

        flag_types = [f["type"] for f in flags]
        assert "high_turnover" in flag_types

    def test_detect_governance_issue(self, leadership_agent):
        """Test detection of governance red flags."""
        articles = [{"title": "SEC probe", "content": "The SEC is investigating accounting irregularities at the company."}]
        flags = leadership_agent._detect_red_flags(articles)

        flag_types = [f["type"] for f in flags]
        assert "governance_issue" in flag_types

    def test_detect_succession_risk(self, leadership_agent):
        """Test detection of succession risk."""
        articles = [{"title": "CEO future", "content": "The 68-year-old CEO nearing retirement has not named a successor."}]
        flags = leadership_agent._detect_red_flags(articles)

        flag_types = [f["type"] for f in flags]
        assert "succession_risk" in flag_types


class TestLeadershipAgentExecution:
    """Tests for the full execution flow."""

    @pytest.mark.asyncio
    async def test_execute_success(self, leadership_agent):
        """Test successful full execution."""
        mock_tavily = MagicMock()
        mock_tavily.is_available = True
        mock_tavily._client = MagicMock()
        mock_tavily._client.search = AsyncMock(return_value={
            "results": [
                {
                    "title": "Test",
                    "content": "CEO has 10 years experience with extensive background.",
                    "raw_content": "CEO has 10 years experience with extensive background.",
                    "source": "Test",
                    "url": "https://example.com/test",
                    "published_date": "2026-01-01",
                    "score": 0.8,
                }
            ]
        })

        with patch("src.agents.leadership_agent.get_tavily_client", return_value=mock_tavily):
            with patch.object(leadership_agent, "_get_company_info", AsyncMock(return_value={
                "long_name": "Test Corp",
                "short_name": "Test"
            })):
                with patch.object(leadership_agent, "_generate_executive_summary", AsyncMock(return_value="Test summary")):
                    result = await leadership_agent.execute()

        assert result["success"] is True
        assert result["agent_type"] == "leadership"
        assert result["data"] is not None
        assert "overall_score" in result["data"]
        assert "grade" in result["data"]
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_execute_handles_errors(self, leadership_agent):
        """Test that execution handles errors gracefully."""
        # Force an error by making fetch_data raise an exception
        with patch.object(leadership_agent, "fetch_data", AsyncMock(side_effect=Exception("Test error"))):
            result = await leadership_agent.execute()

        assert result["success"] is False
        assert result["error"] is not None
        assert result["agent_type"] == "leadership"


class TestLeadershipAgentIntegration:
    """Integration tests with real-like data."""

    @pytest.mark.asyncio
    async def test_integration_comprehensive_analysis(self, leadership_agent):
        """Test comprehensive analysis with realistic data."""
        raw_data = {
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
            "source": "tavily",
            "articles": [
                {
                    "title": "Satya Nadella's Leadership",
                    "content": "CEO Satya Nadella has transformed Microsoft over 10 years. Strong culture of growth mindset and strong team collaboration. Board is 90% independent with strong governance and strong board support.",
                    "source": "Forbes",
                    "published_at": "2026-01-10",
                    "snippet": "",
                },
                {
                    "title": "Microsoft Executive Team",
                    "content": "Low turnover in C-suite. Key executives have been with company 5+ years. Strong succession planning in place. Strong culture and employee satisfaction.",
                    "source": "Business Insider",
                    "published_at": "2026-01-15",
                    "snippet": "",
                },
                {
                    "title": "Microsoft ESG Score",
                    "content": "Microsoft receives high esg score for governance and social responsibility. Strong ethics policies. Respected leader Satya Nadella has strong governance track record. Pay for performance alignment.",
                    "source": "ESG Today",
                    "published_at": "2026-02-01",
                    "snippet": "",
                },
            ],
            "queries": leadership_agent.RESEARCH_QUERIES,
        }

        with patch.object(leadership_agent, "_generate_executive_summary", AsyncMock(return_value="Strong leadership.")):
            result = await leadership_agent.analyze(raw_data)

        # Verify reasonable scores for strong leadership
        assert result["overall_score"] >= 70  # Should be a good score
        assert result["grade"] in ["A+", "A", "A-", "B+", "B", "B-"]

        # Should have insights across all capitals
        for capital in result["four_capitals"].values():
            assert len(capital["insights"]) > 0 or len(capital["red_flags"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
