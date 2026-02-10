"""Tests for Orchestrator agent coordination."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator import Orchestrator
from src.database import DatabaseManager
from src.av_rate_limiter import AVRateLimiter
from src.av_cache import AVCache


def _make_agent_result(agent_type, success=True, data=None):
    """Helper to create a mock agent result dict."""
    return {
        "success": success,
        "agent_type": agent_type,
        "data": data or {"test": True, "data_source": "mock"},
        "error": None if success else "Mock error",
        "duration_seconds": 1.0,
        "timestamp": "2025-02-07T12:00:00",
    }


def _make_solution_result():
    """Helper to create a mock solution agent result."""
    return {
        "success": True,
        "data": {
            "recommendation": "BUY",
            "score": 60,
            "confidence": 0.8,
            "reasoning": "Test reasoning.",
            "risks": ["Risk 1"],
            "opportunities": ["Opp 1"],
            "summary": "Test summary.",
            "price_targets": None,
            "position_size": "MEDIUM",
            "time_horizon": "MEDIUM_TERM",
        },
    }


class TestResolveAgents:
    """Tests for _resolve_agents() dependency resolution."""

    def test_default_includes_all_agents(self, test_config):
        """Default resolution includes all 6 agents."""
        orch = Orchestrator(config=test_config)
        agents = orch._resolve_agents(None)
        assert set(agents) == {"news", "market", "fundamentals", "technical", "macro", "sentiment"}

    def test_sentiment_auto_adds_news(self, test_config):
        """Requesting sentiment auto-adds news dependency."""
        orch = Orchestrator(config=test_config)
        agents = orch._resolve_agents(["sentiment"])
        assert "news" in agents
        assert "sentiment" in agents

    def test_custom_subset_respected(self, test_config):
        """Custom agent list is respected without extra agents added."""
        orch = Orchestrator(config=test_config)
        agents = orch._resolve_agents(["market", "technical"])
        assert set(agents) == {"market", "technical"}

    def test_macro_excluded_when_disabled(self, test_config):
        """Macro agent excluded when MACRO_AGENT_ENABLED is False."""
        config = {**test_config, "MACRO_AGENT_ENABLED": False}
        orch = Orchestrator(config=config)
        agents = orch._resolve_agents(None)
        assert "macro" not in agents
        assert "news" in agents  # Others still present

    def test_single_agent_no_dependencies(self, test_config):
        """A single agent with no deps returns just that agent."""
        orch = Orchestrator(config=test_config)
        agents = orch._resolve_agents(["market"])
        assert agents == ["market"]

    def test_all_agents_explicit(self, test_config):
        """Explicitly listing all agents works the same as None."""
        orch = Orchestrator(config=test_config)
        all_explicit = orch._resolve_agents(
            ["news", "market", "fundamentals", "technical", "macro", "sentiment"]
        )
        assert set(all_explicit) == {"news", "market", "fundamentals", "technical", "macro", "sentiment"}


class TestAnalyzeTicker:
    """Tests for analyze_ticker() end-to-end flow."""

    async def test_full_flow_with_mocked_agents(self, test_config, tmp_path):
        """End-to-end analyze_ticker with all agents mocked."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            # Configure data agents
            for mock_cls, name in [
                (MockNews, "news"),
                (MockMarket, "market"),
                (MockFund, "fundamentals"),
                (MockTech, "technical"),
                (MockMacro, "macro"),
            ]:
                instance = mock_cls.return_value
                instance.execute = AsyncMock(return_value=_make_agent_result(name))

            # Configure sentiment agent (has set_context_data)
            sent_instance = MockSent.return_value
            sent_instance.set_context_data = MagicMock()
            sent_instance.execute = AsyncMock(
                return_value=_make_agent_result("sentiment", data={
                    "overall_sentiment": 0.5,
                    "factors": {"earnings": {"score": 0.5, "weight": 0.3, "contribution": 0.15}},
                })
            )

            # Configure solution agent
            sol_instance = MockSolution.return_value
            sol_instance.execute = AsyncMock(return_value=_make_solution_result())

            orch = Orchestrator(
                config=test_config,
                db_manager=db_manager,
                rate_limiter=AVRateLimiter(100, 1000),
                av_cache=AVCache(),
            )
            result = await orch.analyze_ticker("AAPL")

            assert result["success"] is True
            assert result["ticker"] == "AAPL"
            assert result["analysis"]["recommendation"] == "BUY"
            assert result["analysis"]["score"] == 60
            assert result["analysis_id"] is not None
            assert result["duration_seconds"] > 0

    async def test_ticker_uppercased(self, test_config, tmp_path):
        """analyze_ticker uppercases the input ticker."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            for mock_cls, name in [
                (MockNews, "news"),
                (MockMarket, "market"),
                (MockFund, "fundamentals"),
                (MockTech, "technical"),
                (MockMacro, "macro"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())

            orch = Orchestrator(config=test_config, db_manager=db_manager)
            result = await orch.analyze_ticker("aapl")
            assert result["ticker"] == "AAPL"

    async def test_handles_agent_failure_gracefully(self, test_config, tmp_path):
        """Orchestrator handles individual agent failures without crashing."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)

        # Create mock agent classes that return instances with mock execute()
        def make_mock_agent_class(agent_name, success=True):
            mock_cls = MagicMock()
            mock_instance = MagicMock()
            mock_instance.execute = AsyncMock(return_value=_make_agent_result(agent_name, success=success))
            mock_cls.return_value = mock_instance
            return mock_cls

        mock_news = make_mock_agent_class("news", success=False)
        mock_market = make_mock_agent_class("market")
        mock_fund = make_mock_agent_class("fundamentals")
        mock_tech = make_mock_agent_class("technical")
        mock_macro = make_mock_agent_class("macro")
        mock_sent = make_mock_agent_class("sentiment")
        mock_sent.return_value.set_context_data = MagicMock()

        orch = Orchestrator(config=test_config, db_manager=db_manager)

        # Patch the AGENT_REGISTRY directly
        orch.AGENT_REGISTRY = {
            "news": {"class": mock_news, "requires": []},
            "market": {"class": mock_market, "requires": []},
            "fundamentals": {"class": mock_fund, "requires": []},
            "technical": {"class": mock_tech, "requires": []},
            "macro": {"class": mock_macro, "requires": []},
            "sentiment": {"class": mock_sent, "requires": ["news"]},
        }

        with patch("src.orchestrator.SolutionAgent") as MockSolution:
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())
            result = await orch.analyze_ticker("AAPL")

        # Overall analysis should still succeed
        assert result["success"] is True
        assert result["agent_results"]["news"]["success"] is False
        assert result["agent_results"]["market"]["success"] is True

    async def test_progress_callback_called(self, test_config, tmp_path):
        """Progress callback is invoked during analysis."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)
        progress_updates = []

        async def progress_cb(update):
            progress_updates.append(update)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            for mock_cls, name in [
                (MockNews, "news"),
                (MockMarket, "market"),
                (MockFund, "fundamentals"),
                (MockTech, "technical"),
                (MockMacro, "macro"),
            ]:
                mock_cls.return_value.execute = AsyncMock(return_value=_make_agent_result(name))

            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment"))
            MockSolution.return_value.execute = AsyncMock(return_value=_make_solution_result())

            orch = Orchestrator(
                config=test_config,
                db_manager=db_manager,
                progress_callback=progress_cb,
            )
            await orch.analyze_ticker("AAPL")

            assert len(progress_updates) > 0
            stages = [u["stage"] for u in progress_updates]
            assert "starting" in stages
            assert "complete" in stages


class TestInjectSharedResources:
    """Tests for _inject_shared_resources()."""

    def test_injects_session_and_cache_and_limiter(self, test_config):
        """Shared resources are injected onto the agent instance."""
        orch = Orchestrator(config=test_config)
        orch._shared_session = MagicMock()

        mock_agent = MagicMock()
        orch._inject_shared_resources(mock_agent)

        assert mock_agent._shared_session is orch._shared_session
        assert mock_agent._rate_limiter is orch._rate_limiter
        assert mock_agent._av_cache is orch._av_cache
