"""In-memory TTL cache for Alpha Vantage API responses."""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Tuple


class AVCache:
    """
    In-memory TTL cache for Alpha Vantage API responses.

    Cache key is derived from the AV function name and symbol.
    TTL varies by data type (prices are short-lived, fundamentals longer).

    Shared across agents via the orchestrator. Store on app.state for
    cross-request caching within the same server lifetime.
    """

    # Default TTLs by AV function category (in seconds)
    DEFAULT_TTLS = {
        # Price/quote data: 5 minutes
        "GLOBAL_QUOTE": 300,
        "TIME_SERIES_DAILY": 300,

        # Technical indicators: 5 minutes
        "RSI": 300,
        "MACD": 300,
        "BBANDS": 300,
        "SMA": 300,

        # News: 1 hour
        "NEWS_SENTIMENT": 3600,

        # Fundamentals: 1 day
        "COMPANY_OVERVIEW": 86400,
        "EARNINGS": 86400,
        "BALANCE_SHEET": 86400,
        "CASH_FLOW": 86400,
        "INCOME_STATEMENT": 86400,

        # Macroeconomic data: 1 day (changes slowly)
        "FEDERAL_FUNDS_RATE": 86400,
        "CPI": 86400,
        "REAL_GDP": 86400,
        "TREASURY_YIELD": 86400,
        "UNEMPLOYMENT": 86400,
        "INFLATION": 86400,
    }

    def __init__(self, ttl_overrides: Optional[Dict[str, int]] = None):
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (data, expiry_timestamp)
        self._ttls = {**self.DEFAULT_TTLS}
        if ttl_overrides:
            self._ttls.update(ttl_overrides)
        self.logger = logging.getLogger(__name__)
        self._hits = 0
        self._misses = 0
        self._coalesced = 0
        self._in_flight: Dict[str, asyncio.Future] = {}

    def _make_key(self, params: Dict[str, str]) -> str:
        """
        Generate cache key from request parameters.

        Key is based on: function + symbol + any other distinguishing params
        (e.g., time_period for SMA, outputsize for daily).
        API key is excluded from the cache key.
        """
        key_params = {k: v for k, v in sorted(params.items()) if k != "apikey"}
        return "&".join(f"{k}={v}" for k, v in key_params.items())

    def get(self, params: Dict[str, str]) -> Optional[Dict]:
        """
        Retrieve cached response for the given AV request params.

        Args:
            params: The AV API query parameters (without apikey)

        Returns:
            Cached response dict, or None if not cached or expired
        """
        key = self._make_key(params)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        data, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        func_name = params.get("function", "unknown")
        symbol = params.get("symbol", params.get("tickers", "unknown"))
        self.logger.debug(f"AV cache HIT: {func_name} for {symbol}")
        return data

    def put(self, params: Dict[str, str], data: Dict) -> None:
        """
        Store a response in the cache.

        Args:
            params: The AV API query parameters (without apikey)
            data: The API response to cache
        """
        key = self._make_key(params)
        func_name = params.get("function", "")
        ttl = self._ttls.get(func_name, 300)  # Default 5 minutes
        expiry = time.time() + ttl

        self._cache[key] = (data, expiry)
        self.logger.debug(f"AV cache PUT: {func_name} (TTL={ttl}s)")

    def get_in_flight(self, params: Dict[str, str]) -> Optional[asyncio.Future]:
        """Return the Future for an in-flight request with the same cache key, or None."""
        key = self._make_key(params)
        future = self._in_flight.get(key)
        if future is not None and not future.done():
            self._coalesced += 1
            return future
        return None

    def set_in_flight(self, params: Dict[str, str]) -> asyncio.Future:
        """Register a new in-flight request and return a Future for concurrent callers to await."""
        key = self._make_key(params)
        future = asyncio.get_running_loop().create_future()
        self._in_flight[key] = future
        return future

    def remove_in_flight(self, params: Dict[str, str]) -> None:
        """Remove in-flight tracking for the given params. Call in a finally block."""
        key = self._make_key(params)
        self._in_flight.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._in_flight.clear()
        self._hits = 0
        self._misses = 0
        self._coalesced = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "coalesced": self._coalesced,
            "size": len(self._cache),
            "hit_rate": round(self._hits / max(1, total), 3),
            "in_flight": len(self._in_flight),
        }
