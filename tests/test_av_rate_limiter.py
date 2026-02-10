"""Tests for Alpha Vantage API rate limiter."""

import asyncio

import pytest

from src.av_rate_limiter import AVRateLimiter


class TestAVRateLimiter:
    """Tests for AVRateLimiter."""

    async def test_acquire_succeeds_within_limits(self):
        """acquire() returns True when within both limits."""
        limiter = AVRateLimiter(requests_per_minute=5, requests_per_day=25)
        result = await limiter.acquire()
        assert result is True
        assert limiter.daily_remaining == 24

    async def test_daily_limit_exhaustion(self):
        """acquire() returns False when daily limit is reached."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=3)
        for _ in range(3):
            assert await limiter.acquire() is True

        # Fourth call should be rejected
        assert await limiter.acquire() is False
        assert limiter.is_daily_exhausted is True
        assert limiter.daily_remaining == 0

    async def test_daily_remaining_decrements(self):
        """daily_remaining decrements correctly with each acquire."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=10)
        assert limiter.daily_remaining == 10

        await limiter.acquire()
        assert limiter.daily_remaining == 9

        await limiter.acquire()
        assert limiter.daily_remaining == 8

    async def test_concurrent_acquire_is_serialized(self):
        """Multiple concurrent acquire() calls are serialized by the lock."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=5)
        results = await asyncio.gather(*[limiter.acquire() for _ in range(5)])
        assert all(r is True for r in results)
        assert limiter.daily_remaining == 0

    async def test_is_daily_exhausted_property(self):
        """is_daily_exhausted is True only when count >= limit."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=1)
        assert limiter.is_daily_exhausted is False

        await limiter.acquire()
        assert limiter.is_daily_exhausted is True

    async def test_zero_daily_limit_always_returns_false(self):
        """A daily limit of 0 means acquire() always returns False."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=0)
        assert await limiter.acquire() is False
        assert limiter.is_daily_exhausted is True

    async def test_daily_remaining_never_negative(self):
        """daily_remaining is clamped to 0, never negative."""
        limiter = AVRateLimiter(requests_per_minute=100, requests_per_day=1)
        await limiter.acquire()
        # Try again (will be rejected)
        await limiter.acquire()
        assert limiter.daily_remaining == 0
