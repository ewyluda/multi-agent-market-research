"""Shared test fixtures for the multi-agent market research test suite."""

import json
import sqlite3
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.database import DatabaseManager


# ─── Database Fixtures ───


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary database file path."""
    return str(tmp_path / "test_market_research.db")


@pytest.fixture
def db_manager(tmp_db_path):
    """Create a fresh DatabaseManager with a temp database."""
    return DatabaseManager(tmp_db_path)


# ─── Data Provider Fixtures ───


@pytest.fixture
def mock_data_provider():
    """Create a mock OpenBBDataProvider for testing."""
    provider = MagicMock()
    # Make async methods return AsyncMock
    provider.get_quote = AsyncMock(return_value={})
    provider.get_price_history = AsyncMock(return_value={})
    provider.get_company_overview = AsyncMock(return_value={})
    provider.get_news = AsyncMock(return_value={})
    provider.get_technical_indicators = AsyncMock(return_value={})
    provider.get_options_chain = AsyncMock(return_value={})
    provider.get_macro_data = AsyncMock(return_value={})
    return provider


# ─── Mock LLM Response Fixtures ───


@pytest.fixture
def mock_llm_sentiment_response():
    """Mock LLM JSON response for sentiment analysis."""
    return json.dumps(
        {
            "overall_sentiment": 0.35,
            "confidence": 0.75,
            "factors": {
                "earnings": {"score": 0.5, "weight": 0.3, "contribution": 0.15},
                "guidance": {"score": 0.3, "weight": 0.4, "contribution": 0.12},
                "stock_reactions": {"score": 0.4, "weight": 0.2, "contribution": 0.08},
                "strategic_news": {"score": 0.2, "weight": 0.1, "contribution": 0.02},
            },
            "reasoning": "Positive earnings momentum.",
            "key_themes": ["earnings beat", "strong guidance", "AI growth"],
        }
    )


@pytest.fixture
def mock_llm_solution_response():
    """Mock LLM JSON response for solution agent synthesis."""
    return json.dumps(
        {
            "recommendation": "BUY",
            "score": 65,
            "confidence": 0.78,
            "reasoning": "1. Fundamentals are strong...\n2. Technical signals bullish...",
            "risks": ["Valuation stretched", "Macro headwinds"],
            "opportunities": ["AI tailwind", "Services growth"],
            "price_targets": {"entry": 180.0, "target": 200.0, "stop_loss": 170.0},
            "position_size": "MEDIUM",
            "time_horizon": "MEDIUM_TERM",
            "summary": "Buy with medium position size.",
        }
    )


# ─── Config Fixture ───


@pytest.fixture
def test_config():
    """Configuration dictionary suitable for testing (no real API keys)."""
    return {
        "NEWS_API_KEY": "test_news_key",
        "AGENT_TIMEOUT": 10,
        "AGENT_MAX_RETRIES": 1,
        "NEWS_LOOKBACK_DAYS": 7,
        "MAX_NEWS_ARTICLES": 10,
        "PARALLEL_AGENTS": True,
        "MACRO_AGENT_ENABLED": True,
        "OPTIONS_AGENT_ENABLED": True,
        "CATALYST_SCHEDULER_ENABLED": True,
        "CATALYST_SOURCE": "earnings",
        "CATALYST_PRE_DAYS": 1,
        "CATALYST_POST_DAYS": 1,
        "CATALYST_SCAN_INTERVAL_MINUTES": 60,
        "PORTFOLIO_ACTIONS_ENABLED": True,
        "MACRO_CATALYSTS_ENABLED": True,
        "MACRO_CATALYST_PRE_DAYS": 1,
        "MACRO_CATALYST_DAY_ENABLED": True,
        "MACRO_CATALYST_EVENT_TYPES": ["fomc", "cpi", "nfp"],
        "CALIBRATION_ENABLED": True,
        "CALIBRATION_TIMEZONE": "America/New_York",
        "CALIBRATION_CRON_HOUR": 17,
        "CALIBRATION_CRON_MINUTE": 30,
        "SIGNAL_CONTRACT_V2_ENABLED": True,
        "CALIBRATION_ECONOMICS_ENABLED": True,
        "PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
        "ALERTS_V2_ENABLED": True,
        "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": True,
        "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
        "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
        "SCHEDULED_ALERTS_V2_ENABLED": True,
        "VALIDATION_V1_ENABLED": True,
        "VALIDATION_SPOT_CHECK_RATE": 3,
        "VALIDATION_SPOT_CHECK_ON_CONTRADICTION": True,
        "FUNDAMENTALS_LLM_ENABLED": False,
        "DATABASE_PATH": ":memory:",
        "YFINANCE_TIMEOUT": 5,
        "RSI_PERIOD": 14,
        "MACD_FAST": 12,
        "MACD_SLOW": 26,
        "MACD_SIGNAL": 9,
        "BB_PERIOD": 20,
        "BB_STD": 2,
        "SEC_EDGAR_USER_AGENT": "Test/1.0",
        "SEC_EDGAR_BASE_URL": "https://data.sec.gov/api/xbrl",
        "NEWS_API_BASE_URL": "https://newsapi.org/v2",
        "llm_config": {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "api_key": "test_key",
            "temperature": 0.3,
            "max_tokens": 2048,
        },
    }


# ─── Agent Factory Fixture ───


@pytest.fixture
def make_agent(test_config, mock_data_provider):
    """Factory to create an agent with injected test infrastructure."""

    def _make(agent_class, ticker="AAPL"):
        agent = agent_class(ticker, test_config)
        agent._data_provider = mock_data_provider
        agent._shared_session = None  # Tests should use aioresponses or mock
        return agent

    return _make
