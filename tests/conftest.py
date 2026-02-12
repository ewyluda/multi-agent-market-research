"""Shared test fixtures for the multi-agent market research test suite."""

import json
import sqlite3
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.av_cache import AVCache
from src.av_rate_limiter import AVRateLimiter
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


# ─── AV Infrastructure Fixtures ───


@pytest.fixture
def av_cache():
    """Create a fresh AVCache instance."""
    return AVCache()


@pytest.fixture
def av_rate_limiter():
    """Create an AVRateLimiter with generous limits for testing."""
    return AVRateLimiter(requests_per_minute=100, requests_per_day=1000)


@pytest.fixture
def exhausted_rate_limiter():
    """Create an AVRateLimiter that is already daily-exhausted."""
    return AVRateLimiter(requests_per_minute=5, requests_per_day=0)


# ─── Mock AV Response Factories ───


@pytest.fixture
def av_global_quote_response():
    """Sample GLOBAL_QUOTE response from Alpha Vantage."""
    return {
        "Global Quote": {
            "01. symbol": "AAPL",
            "02. open": "182.3500",
            "03. high": "183.5800",
            "04. low": "181.9200",
            "05. price": "183.1500",
            "06. volume": "48425073",
            "07. latest trading day": "2025-02-07",
            "08. previous close": "182.3500",
            "09. change": "0.8000",
            "10. change percent": "0.4388%",
        }
    }


@pytest.fixture
def av_time_series_daily_response():
    """Sample TIME_SERIES_DAILY response (3 days)."""
    return {
        "Meta Data": {
            "1. Information": "Daily Prices",
            "2. Symbol": "AAPL",
        },
        "Time Series (Daily)": {
            "2025-02-07": {
                "1. open": "182.35",
                "2. high": "183.58",
                "3. low": "181.92",
                "4. close": "183.15",
                "5. volume": "48425073",
            },
            "2025-02-06": {
                "1. open": "181.00",
                "2. high": "182.50",
                "3. low": "180.50",
                "4. close": "182.35",
                "5. volume": "42000000",
            },
            "2025-02-05": {
                "1. open": "180.00",
                "2. high": "181.20",
                "3. low": "179.80",
                "4. close": "181.00",
                "5. volume": "39000000",
            },
        },
    }


@pytest.fixture
def av_news_sentiment_response():
    """Sample NEWS_SENTIMENT response."""
    return {
        "items": "3",
        "sentiment_score_definition": "...",
        "feed": [
            {
                "title": "Apple Reports Record Revenue",
                "url": "https://example.com/article1",
                "time_published": "20250207T120000",
                "authors": ["Jane Doe"],
                "summary": "Apple posted record quarterly revenue.",
                "source": "Reuters",
                "overall_sentiment_score": 0.35,
                "overall_sentiment_label": "Bullish",
                "ticker_sentiment": [
                    {
                        "ticker": "AAPL",
                        "relevance_score": "0.95",
                        "ticker_sentiment_score": "0.42",
                        "ticker_sentiment_label": "Bullish",
                    }
                ],
            },
        ],
    }


@pytest.fixture
def av_rsi_response():
    """Sample RSI technical indicator response."""
    return {
        "Meta Data": {"2: Indicator": "Relative Strength Index (RSI)"},
        "Technical Analysis: RSI": {
            "2025-02-07": {"RSI": "62.5"},
            "2025-02-06": {"RSI": "60.1"},
        },
    }


@pytest.fixture
def av_company_overview_response():
    """Sample COMPANY_OVERVIEW response."""
    return {
        "Symbol": "AAPL",
        "Name": "Apple Inc",
        "MarketCapitalization": "2800000000000",
        "PERatio": "28.5",
        "EPS": "6.42",
        "DividendYield": "0.005",
        "RevenueTTM": "383000000000",
        "ProfitMargin": "0.265",
        "52WeekHigh": "199.62",
        "52WeekLow": "164.08",
    }


@pytest.fixture
def av_macro_fed_funds_response():
    """Sample FEDERAL_FUNDS_RATE response."""
    return {
        "name": "Federal Funds Effective Rate",
        "data": [
            {"date": "2025-01-01", "value": "4.33"},
            {"date": "2024-12-01", "value": "4.33"},
        ],
    }


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
        "ALPHA_VANTAGE_API_KEY": "test_av_key",
        "NEWS_API_KEY": "test_news_key",
        "AGENT_TIMEOUT": 10,
        "AGENT_MAX_RETRIES": 1,
        "NEWS_LOOKBACK_DAYS": 7,
        "MAX_NEWS_ARTICLES": 10,
        "PARALLEL_AGENTS": True,
        "MACRO_AGENT_ENABLED": True,
        "OPTIONS_AGENT_ENABLED": True,
        "FUNDAMENTALS_LLM_ENABLED": False,
        "AV_RATE_LIMIT_PER_MINUTE": 100,
        "AV_RATE_LIMIT_PER_DAY": 1000,
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
        "ALPHA_VANTAGE_BASE_URL": "https://www.alphavantage.co/query",
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
def make_agent(test_config, av_cache, av_rate_limiter):
    """Factory to create an agent with injected test infrastructure."""

    def _make(agent_class, ticker="AAPL"):
        agent = agent_class(ticker, test_config)
        agent._av_cache = av_cache
        agent._rate_limiter = av_rate_limiter
        agent._shared_session = None  # Tests should use aioresponses or mock
        return agent

    return _make
