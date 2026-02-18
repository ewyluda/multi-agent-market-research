"""Alpha Vantage API rate limiter using asyncio primitives."""

import asyncio
import time
import logging
from typing import List


class AVRateLimiter:
    """
    Sliding-window rate limiter for Alpha Vantage API requests.

    Enforces two limits:
    - Per-minute limit (default: 5 for AV free tier)
    - Per-day limit (default: 25 for AV free tier)

    All agents share a single instance via the orchestrator.
    Designed to be stored on app.state for cross-request daily tracking.
    """

    def __init__(
        self,
        requests_per_minute: int = 5,
        requests_per_day: int = 25,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day

        self._daily_count = 0
        self._daily_reset_time = time.time() + 86400
        self._minute_timestamps: List[float] = []
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def acquire(self) -> bool:
        """
        Acquire permission to make one AV API request.

        Blocks until a slot is available within the per-minute window.
        Returns False if the daily limit has been reached.

        Returns:
            True if request can proceed, False if daily limit exhausted
        """
        while True:
            async with self._lock:
                now = time.time()

                # Reset daily counter if 24h have passed
                if now >= self._daily_reset_time:
                    self._daily_count = 0
                    self._daily_reset_time = now + 86400

                # Check daily limit
                if self._daily_count >= self.requests_per_day:
                    self.logger.warning(
                        f"Alpha Vantage daily limit reached ({self.requests_per_day} requests). "
                        "Agents will use fallback sources."
                    )
                    return False

                # Clean up old timestamps (older than 60 seconds)
                self._minute_timestamps = [t for t in self._minute_timestamps if t > now - 60.0]

                # If minute window full, calculate wait time
                if len(self._minute_timestamps) >= self.requests_per_minute:
                    oldest = self._minute_timestamps[0]
                    wait_time = 60.0 - (now - oldest) + 0.1  # +0.1s buffer
                else:
                    # Slot available — record and return
                    self._minute_timestamps.append(time.time())
                    self._daily_count += 1
                    self.logger.debug(
                        f"AV rate limiter: {self._daily_count}/{self.requests_per_day} daily, "
                        f"{len(self._minute_timestamps)}/{self.requests_per_minute} per minute"
                    )
                    return True

            # Wait outside the lock if needed, then loop back to retry
            self.logger.info(f"Rate limiter: waiting {wait_time:.1f}s for AV minute window")
            await asyncio.sleep(wait_time)

    @property
    def daily_remaining(self) -> int:
        """Number of daily requests remaining."""
        return max(0, self.requests_per_day - self._daily_count)

    @property
    def is_daily_exhausted(self) -> bool:
        """True if daily limit has been reached."""
        return self._daily_count >= self.requests_per_day
