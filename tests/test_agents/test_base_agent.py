"""Tests for BaseAgent abstract base class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base_agent import BaseAgent
from src.av_cache import AVCache
from src.av_rate_limiter import AVRateLimiter


# Concrete subclass for testing (BaseAgent is abstract)
class ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing BaseAgent methods."""

    async def fetch_data(self):
        return {"ticker": self.ticker, "data": "test_data"}

    async def analyze(self, raw_data):
        return {"status": "analyzed", "ticker": raw_data["ticker"]}


class FailingFetchAgent(BaseAgent):
    """Agent whose fetch_data always raises."""

    async def fetch_data(self):
        raise ValueError("Data source unavailable")

    async def analyze(self, raw_data):
        return {}


class FailingAnalyzeAgent(BaseAgent):
    """Agent whose analyze always raises."""

    async def fetch_data(self):
        return {"ticker": self.ticker}

    async def analyze(self, raw_data):
        raise RuntimeError("Analysis engine error")


class TestBaseAgentGetAgentType:
    """Tests for get_agent_type() snake_case conversion."""

    def test_simple_name(self, test_config):
        """Single-word class name (without Agent suffix)."""
        agent = ConcreteAgent("AAPL", test_config)
        assert agent.get_agent_type() == "concrete"

    def test_multi_word_name(self, test_config):
        """CamelCase name gets converted to snake_case."""

        class MyCustomAgent(BaseAgent):
            async def fetch_data(self):
                return {}

            async def analyze(self, raw_data):
                return {}

        agent = MyCustomAgent("AAPL", test_config)
        assert agent.get_agent_type() == "my_custom"


class TestBaseAgentExecute:
    """Tests for execute() workflow."""

    async def test_execute_success_flow(self, test_config):
        """execute() calls fetch_data -> analyze -> returns success dict."""
        agent = ConcreteAgent("AAPL", test_config)
        result = await agent.execute()

        assert result["success"] is True
        assert result["agent_type"] == "concrete"
        assert result["data"]["status"] == "analyzed"
        assert result["data"]["ticker"] == "AAPL"
        assert result["error"] is None
        assert result["duration_seconds"] >= 0
        assert "timestamp" in result

    async def test_execute_handles_fetch_error(self, test_config):
        """execute() catches fetch_data exceptions and returns success=False."""
        agent = FailingFetchAgent("AAPL", test_config)
        result = await agent.execute()

        assert result["success"] is False
        assert "Data source unavailable" in result["error"]
        assert result["data"] is None

    async def test_execute_handles_analyze_error(self, test_config):
        """execute() catches analyze() exceptions and returns success=False."""
        agent = FailingAnalyzeAgent("AAPL", test_config)
        result = await agent.execute()

        assert result["success"] is False
        assert "Analysis engine error" in result["error"]

    async def test_execute_records_duration(self, test_config):
        """execute() records start/end time and reports duration."""
        agent = ConcreteAgent("AAPL", test_config)
        result = await agent.execute()

        assert result["duration_seconds"] >= 0
        assert agent.start_time is not None
        assert agent.end_time is not None
        assert agent.get_duration() > 0


class TestBaseAgentAVRequest:
    """Tests for _av_request() method."""

    async def test_returns_none_without_api_key(self, test_config):
        """_av_request returns None when ALPHA_VANTAGE_API_KEY is empty."""
        config = {**test_config, "ALPHA_VANTAGE_API_KEY": ""}
        agent = ConcreteAgent("AAPL", config)

        result = await agent._av_request({"function": "GLOBAL_QUOTE", "symbol": "AAPL"})
        assert result is None

    async def test_returns_cached_data(self, test_config):
        """_av_request returns cached data without making HTTP request."""
        av_cache = AVCache()
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        cached_data = {"Global Quote": {"05. price": "183.15"}}
        av_cache.put(params, cached_data)

        agent = ConcreteAgent("AAPL", test_config)
        agent._av_cache = av_cache
        agent._rate_limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=100)

        result = await agent._av_request(params)
        assert result == cached_data

    async def test_returns_none_when_rate_limited(self, test_config):
        """_av_request returns None when daily rate limit is exhausted."""
        av_cache = AVCache()
        rate_limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=0)

        agent = ConcreteAgent("AAPL", test_config)
        agent._av_cache = av_cache
        agent._rate_limiter = rate_limiter

        result = await agent._av_request({"function": "GLOBAL_QUOTE", "symbol": "AAPL"})
        assert result is None


class TestBaseAgentRetryFetch:
    """Tests for _retry_fetch() with exponential backoff."""

    async def test_retry_succeeds_after_failures(self, test_config):
        """_retry_fetch retries and succeeds on later attempt."""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient failure")
            return {"success": True}

        agent = ConcreteAgent("AAPL", test_config)
        result = await agent._retry_fetch(flaky_func, max_retries=2, label="test")

        assert result == {"success": True}
        assert call_count == 2

    async def test_retry_returns_none_after_all_failures(self, test_config):
        """_retry_fetch returns None when all retries are exhausted."""

        def always_fails():
            raise Exception("permanent failure")

        agent = ConcreteAgent("AAPL", test_config)
        result = await agent._retry_fetch(always_fails, max_retries=1, label="test")

        assert result is None

    async def test_retry_respects_max_retries(self, test_config):
        """_retry_fetch calls func exactly max_retries + 1 times."""
        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            raise Exception("always fails")

        agent = ConcreteAgent("AAPL", test_config)
        await agent._retry_fetch(counting_func, max_retries=3, label="test")

        assert call_count == 4  # initial + 3 retries
