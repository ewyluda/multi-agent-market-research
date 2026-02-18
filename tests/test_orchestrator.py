"""Tests for Orchestrator agent coordination."""

import asyncio
from datetime import datetime, timedelta, timezone
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
        """Default resolution includes all 7 agents."""
        orch = Orchestrator(config=test_config)
        agents = orch._resolve_agents(None)
        assert set(agents) == {"news", "market", "fundamentals", "technical", "macro", "options", "sentiment"}

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

    def test_options_excluded_when_disabled(self, test_config):
        """Options agent excluded when OPTIONS_AGENT_ENABLED is False."""
        config = {**test_config, "OPTIONS_AGENT_ENABLED": False}
        orch = Orchestrator(config=config)
        agents = orch._resolve_agents(None)
        assert "options" not in agents
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
            ["news", "market", "fundamentals", "technical", "macro", "options", "sentiment"]
        )
        assert set(all_explicit) == {"news", "market", "fundamentals", "technical", "macro", "options", "sentiment"}


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
            patch("src.orchestrator.OptionsAgent") as MockOptions,
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
                (MockOptions, "options"),
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
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            for mock_cls, name in [
                (MockNews, "news"),
                (MockMarket, "market"),
                (MockFund, "fundamentals"),
                (MockTech, "technical"),
                (MockMacro, "macro"),
                (MockOptions, "options"),
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
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            for mock_cls, name in [
                (MockNews, "news"),
                (MockMarket, "market"),
                (MockFund, "fundamentals"),
                (MockTech, "technical"),
                (MockMacro, "macro"),
                (MockOptions, "options"),
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

    async def test_change_summary_added_across_runs(self, test_config, tmp_path):
        """Orchestrator adds run-to-run change summary using previous analysis context."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)

        with (
            patch("src.orchestrator.NewsAgent") as MockNews,
            patch("src.orchestrator.MarketAgent") as MockMarket,
            patch("src.orchestrator.FundamentalsAgent") as MockFund,
            patch("src.orchestrator.TechnicalAgent") as MockTech,
            patch("src.orchestrator.MacroAgent") as MockMacro,
            patch("src.orchestrator.OptionsAgent") as MockOptions,
            patch("src.orchestrator.SentimentAgent") as MockSent,
            patch("src.orchestrator.SolutionAgent") as MockSolution,
        ):
            MockNews.return_value.execute = AsyncMock(return_value=_make_agent_result("news"))
            MockMarket.return_value.execute = AsyncMock(return_value=_make_agent_result("market", data={"trend": "uptrend"}))
            MockFund.return_value.execute = AsyncMock(return_value=_make_agent_result("fundamentals", data={"health_score": 55}))
            MockTech.return_value.execute = AsyncMock(return_value=_make_agent_result("technical", data={"signals": {"overall": "neutral", "strength": 5}}))
            MockMacro.return_value.execute = AsyncMock(return_value=_make_agent_result("macro", data={"risk_environment": "neutral"}))
            MockOptions.return_value.execute = AsyncMock(return_value=_make_agent_result("options", data={"overall_signal": "neutral", "put_call_ratio": 1.0}))
            MockSent.return_value.set_context_data = MagicMock()
            MockSent.return_value.execute = AsyncMock(return_value=_make_agent_result("sentiment", data={"overall_sentiment": 0.05}))

            MockSolution.return_value.execute = AsyncMock(side_effect=[
                {
                    "success": True,
                    "data": {
                        "recommendation": "HOLD",
                        "score": 5,
                        "confidence": 0.51,
                        "reasoning": "Baseline thesis.",
                        "risks": ["Risk 1"],
                        "opportunities": ["Opp 1"],
                        "summary": "Hold",
                        "price_targets": None,
                        "position_size": "SMALL",
                        "time_horizon": "SHORT_TERM",
                    },
                },
                {
                    "success": True,
                    "data": {
                        "recommendation": "BUY",
                        "score": 42,
                        "confidence": 0.73,
                        "reasoning": "Trend improving.",
                        "risks": ["Risk 1"],
                        "opportunities": ["Opp 1"],
                        "summary": "Buy",
                        "price_targets": None,
                        "position_size": "MEDIUM",
                        "time_horizon": "MEDIUM_TERM",
                    },
                },
            ])

            orch = Orchestrator(config=test_config, db_manager=db_manager)
            first = await orch.analyze_ticker("AAPL")
            second = await orch.analyze_ticker("AAPL")

            assert first["analysis"]["changes_since_last_run"]["has_previous"] is False
            assert second["analysis"]["changes_since_last_run"]["has_previous"] is True
            assert second["analysis"]["changes_since_last_run"]["change_count"] >= 1


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


class TestDiagnostics:
    """Tests for disagreement and data-quality diagnostics."""

    def test_disagreement_conflict_threshold(self, test_config):
        """Conflict triggers when bullish and bearish counts are both at least 2."""
        orch = Orchestrator(config=test_config)
        agent_results = {
            "market": _make_agent_result("market", data={"trend": "uptrend"}),
            "fundamentals": _make_agent_result("fundamentals", data={"health_score": 68, "data_source": "alpha_vantage"}),
            "technical": _make_agent_result("technical", data={"signals": {"overall": "sell", "strength": -40}, "data_source": "alpha_vantage"}),
            "options": _make_agent_result("options", data={"overall_signal": "bearish", "data_source": "alpha_vantage"}),
            "sentiment": _make_agent_result("sentiment", data={"overall_sentiment": 0.31}),
        }

        disagreement = orch._build_disagreement_diagnostics(agent_results)

        assert disagreement["bullish_count"] >= 2
        assert disagreement["bearish_count"] >= 2
        assert disagreement["is_conflicted"] is True
        assert "market" in disagreement["conflicting_agents"] or "technical" in disagreement["conflicting_agents"]

    def test_data_quality_levels_are_deterministic(self, test_config):
        """Quality classification follows success-rate and critical-failure thresholds."""
        orch = Orchestrator(config=test_config)

        fresh_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        good_results = {
            "news": _make_agent_result("news", data={"articles": [{"published_at": fresh_time}], "data_source": "alpha_vantage"}),
            "market": _make_agent_result("market", data={"data_source": "alpha_vantage"}),
            "fundamentals": _make_agent_result("fundamentals", data={"data_source": "alpha_vantage"}),
            "technical": _make_agent_result("technical", data={"data_source": "alpha_vantage"}),
            "macro": _make_agent_result("macro", data={"data_source": "alpha_vantage"}),
        }
        good = orch._build_data_quality_diagnostics(good_results)
        assert good["quality_level"] == "good"
        assert good["agent_success_rate"] == 1.0
        assert good["failed_agents"] == []

        warn_results = {
            "news": _make_agent_result("news", data={"articles": [{"published_at": fresh_time}], "data_source": "alpha_vantage"}),
            "market": _make_agent_result("market", data={"data_source": "yfinance"}),
            "fundamentals": _make_agent_result("fundamentals", success=False, data=None),
            "technical": _make_agent_result("technical", data={"data_source": "alpha_vantage"}),
            "macro": _make_agent_result("macro", data={"data_source": "alpha_vantage"}),
        }
        warn = orch._build_data_quality_diagnostics(warn_results)
        assert warn["quality_level"] == "warn"
        assert "fundamentals" in warn["failed_agents"]
        assert any(item["source"] == "yfinance" for item in warn["fallback_source_agents"])

        poor_results = {
            "news": _make_agent_result("news", success=False, data=None),
            "market": _make_agent_result("market", success=False, data=None),
            "fundamentals": _make_agent_result("fundamentals", success=False, data=None),
            "technical": _make_agent_result("technical", data={"data_source": "alpha_vantage"}),
            "macro": _make_agent_result("macro", data={"data_source": "none"}),
        }
        poor = orch._build_data_quality_diagnostics(poor_results)
        assert poor["quality_level"] == "poor"
        assert len(poor["failed_agents"]) >= 2
        assert any("critical agents failed" in w.lower() for w in poor["warnings"])


class TestCalibrationProbability:
    """Tests for predicted-up probability mapping used in calibration rows."""

    def test_derive_probability_falls_back_when_scenarios_non_informative(self, test_config):
        """Missing scenario returns should not force a hard zero probability."""
        orch = Orchestrator(config=test_config)
        probability = orch._derive_predicted_up_probability(
            {
                "recommendation": "BUY",
                "scenarios": {
                    "bull": {"probability": 0.5, "expected_return_pct": None},
                    "base": {"probability": 0.3, "expected_return_pct": "n/a"},
                    "bear": {"probability": 0.2},
                },
            }
        )
        assert probability == 0.65

    def test_derive_probability_uses_informative_scenarios_when_available(self, test_config):
        """When returns are provided, scenario probabilities should drive the result."""
        orch = Orchestrator(config=test_config)
        probability = orch._derive_predicted_up_probability(
            {
                "recommendation": "SELL",
                "scenarios": {
                    "bull": {"probability": 0.4, "expected_return_pct": 8.0},
                    "base": {"probability": 0.3, "expected_return_pct": 0.0},
                    "bear": {"probability": 0.3, "expected_return_pct": -6.0},
                },
            }
        )
        assert probability == pytest.approx(0.55, abs=1e-9)


class TestPortfolioAndCalibrationIntegration:
    """Tests for portfolio overlay and calibration enqueue path."""

    @pytest.mark.asyncio
    async def test_portfolio_action_overlay_attached(self, test_config, tmp_path):
        db_path = str(tmp_path / "portfolio_overlay.db")
        db_manager = DatabaseManager(db_path)
        config = {
            **test_config,
            "ALERTS_ENABLED": False,
            "PORTFOLIO_ACTIONS_ENABLED": True,
            "CALIBRATION_ENABLED": False,
        }

        orch = Orchestrator(config=config, db_manager=db_manager)
        orch._run_agents = AsyncMock(
            return_value={
                "market": _make_agent_result("market", data={"trend": "uptrend", "current_price": 100.0}),
                "news": _make_agent_result("news", data={"articles": []}),
                "fundamentals": _make_agent_result("fundamentals", data={"health_score": 70}),
                "technical": _make_agent_result("technical", data={"signals": {"overall": "buy", "strength": 30}}),
                "sentiment": _make_agent_result("sentiment", data={"overall_sentiment": 0.4}),
            }
        )
        orch._run_solution_agent = AsyncMock(
            return_value={
                "recommendation": "BUY",
                "score": 55,
                "confidence": 0.72,
                "reasoning": "Constructive setup.",
                "risks": [],
                "opportunities": [],
                "summary": "Buy setup.",
            }
        )

        result = await orch.analyze_ticker("AAPL")
        assert result["success"] is True
        assert result["analysis"]["portfolio_action"]["action"] == "add"
        assert "portfolio_summary" in result["analysis"]

    @pytest.mark.asyncio
    async def test_diagnostics_gate_downgrades_action(self, test_config, tmp_path):
        db_path = str(tmp_path / "portfolio_gate.db")
        db_manager = DatabaseManager(db_path)
        config = {
            **test_config,
            "ALERTS_ENABLED": False,
            "PORTFOLIO_ACTIONS_ENABLED": True,
            "CALIBRATION_ENABLED": False,
        }

        orch = Orchestrator(config=config, db_manager=db_manager)
        orch._run_agents = AsyncMock(
            return_value={
                "news": _make_agent_result("news", success=False, data=None),
                "market": _make_agent_result("market", success=False, data=None),
                "fundamentals": _make_agent_result("fundamentals", success=False, data=None),
                "technical": _make_agent_result("technical", data={"signals": {"overall": "buy", "strength": 15}}),
            }
        )
        orch._run_solution_agent = AsyncMock(
            return_value={
                "recommendation": "BUY",
                "score": 35,
                "confidence": 0.58,
                "reasoning": "Some positives remain.",
                "risks": [],
                "opportunities": [],
                "summary": "Guarded buy.",
            }
        )

        result = await orch.analyze_ticker("MSFT")
        assert result["success"] is True
        assert result["analysis"]["portfolio_action"]["action"] == "hold"

    @pytest.mark.asyncio
    async def test_outcome_rows_enqueued_after_success(self, test_config, tmp_path):
        db_path = str(tmp_path / "calibration_enqueue.db")
        db_manager = DatabaseManager(db_path)
        config = {
            **test_config,
            "ALERTS_ENABLED": False,
            "PORTFOLIO_ACTIONS_ENABLED": False,
            "CALIBRATION_ENABLED": True,
        }

        orch = Orchestrator(config=config, db_manager=db_manager)
        orch._run_agents = AsyncMock(
            return_value={
                "market": _make_agent_result("market", data={"trend": "uptrend", "current_price": 150.0}),
                "sentiment": _make_agent_result("sentiment", data={"overall_sentiment": 0.2}),
            }
        )
        orch._run_solution_agent = AsyncMock(
            return_value={
                "recommendation": "BUY",
                "score": 48,
                "confidence": 0.66,
                "reasoning": "Positive skew.",
                "risks": [],
                "opportunities": [],
                "summary": "Buy bias.",
                "scenarios": {
                    "bull": {"probability": 0.4, "expected_return_pct": 8.0, "thesis": "Upside"},
                    "base": {"probability": 0.4, "expected_return_pct": 2.0, "thesis": "Base"},
                    "bear": {"probability": 0.2, "expected_return_pct": -5.0, "thesis": "Downside"},
                },
            }
        )

        result = await orch.analyze_ticker("NVDA")
        assert result["success"] is True

        due = db_manager.list_due_outcomes("2100-01-01")
        rows_for_analysis = [row for row in due if row["analysis_id"] == result["analysis_id"]]
        assert len(rows_for_analysis) == 3


@pytest.mark.asyncio
async def test_db_write_failure_still_returns_analysis(test_config, tmp_db_path):
    """If _save_to_database fails, analyze_ticker still returns the analysis result."""
    db = DatabaseManager(tmp_db_path)
    orch = Orchestrator(config=test_config, db_manager=db)

    mock_results = {
        "news": _make_agent_result("news"),
        "market": _make_agent_result("market", data={"current_price": 150.0, "trend": "uptrend"}),
        "fundamentals": _make_agent_result("fundamentals"),
        "technical": _make_agent_result("technical"),
        "macro": _make_agent_result("macro"),
        "options": _make_agent_result("options"),
        "sentiment": _make_agent_result("sentiment"),
    }

    with patch.object(orch, "_run_agents", new_callable=AsyncMock, return_value=mock_results), \
         patch.object(orch, "_run_solution_agent", new_callable=AsyncMock, return_value=_make_solution_result()["data"]), \
         patch.object(orch, "_save_to_database", side_effect=Exception("DB locked")), \
         patch.object(orch, "_create_shared_session", new_callable=AsyncMock), \
         patch.object(orch, "_close_shared_session", new_callable=AsyncMock), \
         patch.object(orch, "_notify_progress", new_callable=AsyncMock):
        result = await orch.analyze_ticker("AAPL")

    assert result["success"] is True
    assert result["analysis_id"] is None
    assert result["analysis"]["recommendation"] == "BUY"
    assert result.get("db_write_warning") is not None
