"""Tests for Alpha Vantage in-memory TTL cache."""

import asyncio
import time

import pytest

from src.av_cache import AVCache


class TestAVCache:
    """Tests for AVCache."""

    def test_put_and_get_returns_cached_data(self, av_cache):
        """put() stores data; get() retrieves it before TTL expires."""
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        data = {"Global Quote": {"05. price": "183.15"}}
        av_cache.put(params, data)
        result = av_cache.get(params)
        assert result == data
        assert av_cache.stats["hits"] == 1

    def test_get_returns_none_for_missing_key(self, av_cache):
        """get() returns None for uncached params and increments misses."""
        result = av_cache.get({"function": "GLOBAL_QUOTE", "symbol": "ZZZZZ"})
        assert result is None
        assert av_cache.stats["misses"] == 1

    def test_ttl_expiry(self, av_cache):
        """Cached entry expires after TTL."""
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        data = {"Global Quote": {"05. price": "183.15"}}

        # Override TTL to 0 seconds for this test
        av_cache._ttls["GLOBAL_QUOTE"] = 0
        av_cache.put(params, data)

        # Small sleep to ensure expiry
        time.sleep(0.01)
        assert av_cache.get(params) is None
        assert av_cache.stats["misses"] == 1

    def test_cache_key_excludes_apikey(self, av_cache):
        """apikey parameter is excluded from cache key."""
        params_a = {"function": "GLOBAL_QUOTE", "symbol": "AAPL", "apikey": "key1"}
        params_b = {"function": "GLOBAL_QUOTE", "symbol": "AAPL", "apikey": "key2"}
        assert av_cache._make_key(params_a) == av_cache._make_key(params_b)

    def test_different_symbols_different_keys(self, av_cache):
        """Different symbols produce different cache keys."""
        key_a = av_cache._make_key({"function": "GLOBAL_QUOTE", "symbol": "AAPL"})
        key_b = av_cache._make_key({"function": "GLOBAL_QUOTE", "symbol": "NVDA"})
        assert key_a != key_b

    def test_different_functions_different_keys(self, av_cache):
        """Different AV functions produce different cache keys."""
        key_a = av_cache._make_key({"function": "GLOBAL_QUOTE", "symbol": "AAPL"})
        key_b = av_cache._make_key({"function": "RSI", "symbol": "AAPL"})
        assert key_a != key_b

    async def test_in_flight_coalescing(self, av_cache):
        """set_in_flight returns a Future; get_in_flight returns it for same key."""
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        future = av_cache.set_in_flight(params)

        retrieved = av_cache.get_in_flight(params)
        assert retrieved is future
        assert av_cache.stats["coalesced"] == 1

        # Resolve the future and clean up
        future.set_result({"data": True})
        av_cache.remove_in_flight(params)
        assert av_cache.get_in_flight(params) is None

    async def test_in_flight_done_future_returns_none(self, av_cache):
        """get_in_flight returns None if the existing future is already done."""
        params = {"function": "RSI", "symbol": "NVDA"}
        future = av_cache.set_in_flight(params)
        future.set_result({"data": True})

        # Future is done — should return None (not coalesce)
        assert av_cache.get_in_flight(params) is None

    def test_clear_resets_everything(self, av_cache):
        """clear() empties cache, in-flight, and stats."""
        av_cache.put({"function": "RSI", "symbol": "AAPL"}, {"data": True})
        av_cache.get({"function": "RSI", "symbol": "AAPL"})  # +1 hit
        av_cache.clear()
        assert av_cache.stats["size"] == 0
        assert av_cache.stats["hits"] == 0
        assert av_cache.stats["misses"] == 0
        assert av_cache.stats["coalesced"] == 0

    def test_stats_property_structure(self, av_cache):
        """stats returns correct structure with all expected keys."""
        stats = av_cache.stats
        expected_keys = {"hits", "misses", "coalesced", "size", "hit_rate", "in_flight"}
        assert set(stats.keys()) == expected_keys

    def test_stats_hit_rate_calculation(self, av_cache):
        """hit_rate is computed correctly."""
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        av_cache.put(params, {"data": True})

        av_cache.get(params)  # hit
        av_cache.get(params)  # hit
        av_cache.get({"function": "GLOBAL_QUOTE", "symbol": "MISS"})  # miss

        assert av_cache.stats["hit_rate"] == round(2 / 3, 3)

    def test_put_overwrites_existing(self, av_cache):
        """put() overwrites an existing entry with the same key."""
        params = {"function": "GLOBAL_QUOTE", "symbol": "AAPL"}
        av_cache.put(params, {"price": "100"})
        av_cache.put(params, {"price": "200"})
        assert av_cache.get(params) == {"price": "200"}
        assert av_cache.stats["size"] == 1

    def test_default_ttl_for_unknown_function(self, av_cache):
        """Unknown function names use default 5-minute TTL (don't crash)."""
        params = {"function": "UNKNOWN_FUNC", "symbol": "AAPL"}
        av_cache.put(params, {"data": True})
        assert av_cache.get(params) == {"data": True}

    def test_ttl_overrides_at_init(self):
        """TTL overrides passed at init are respected."""
        cache = AVCache(ttl_overrides={"GLOBAL_QUOTE": 1})
        assert cache._ttls["GLOBAL_QUOTE"] == 1
        # Other TTLs remain default
        assert cache._ttls["RSI"] == 300
