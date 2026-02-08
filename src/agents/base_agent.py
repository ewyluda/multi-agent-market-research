"""Base agent class for all market research agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import logging
import asyncio
import random
from datetime import datetime

import aiohttp


class BaseAgent(ABC):
    """Abstract base class for all market research agents."""

    AV_BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, ticker: str, config: Dict[str, Any]):
        """
        Initialize base agent.

        Args:
            ticker: Stock ticker symbol
            config: Configuration dictionary
        """
        self.ticker = ticker.upper()
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.result = None
        self.error = None
        self.start_time = None
        self.end_time = None

    @abstractmethod
    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch raw data from external sources.

        Returns:
            Raw data dictionary

        Raises:
            Exception: If data fetching fails
        """
        pass

    @abstractmethod
    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze fetched data and generate insights.

        Args:
            raw_data: Raw data from fetch_data()

        Returns:
            Analysis results dictionary
        """
        pass

    async def _retry_fetch(self, func, max_retries: int = None, label: str = ""):
        """
        Retry a synchronous function with exponential backoff + jitter.

        Args:
            func: Callable to execute
            max_retries: Max retry attempts (defaults to config AGENT_MAX_RETRIES)
            label: Label for logging

        Returns:
            Result of func, or None if all retries fail
        """
        retries = max_retries if max_retries is not None else self.config.get("AGENT_MAX_RETRIES", 2)
        for attempt in range(retries + 1):
            try:
                return func()
            except Exception as e:
                if attempt == retries:
                    self.logger.warning(f"Failed to fetch {label} after {retries + 1} attempts: {e}")
                    return None
                wait = (2 ** attempt) + random.uniform(0, 1)
                self.logger.info(f"Retry {attempt + 1}/{retries} for {label} in {wait:.1f}s: {e}")
                await asyncio.sleep(wait)
        return None

    async def _av_request(self, params: Dict[str, str]) -> Optional[Dict]:
        """
        Make a request to Alpha Vantage API.

        Uses the shared session if available (set by orchestrator),
        otherwise creates a per-request session (backward compatible).

        Args:
            params: Query parameters (function, symbol, etc.) — apikey is added internally

        Returns:
            JSON response dict, or None on failure
        """
        api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            return None

        # Check cache first (params without apikey)
        cache = getattr(self, '_av_cache', None)
        if cache:
            cached = cache.get(params)
            if cached is not None:
                return cached

        # Check rate limiter
        rate_limiter = getattr(self, '_rate_limiter', None)
        if rate_limiter:
            allowed = await rate_limiter.acquire()
            if not allowed:
                self.logger.info("AV daily limit reached, skipping request")
                return None

        # Add apikey for the actual request
        request_params = {**params, "apikey": api_key}
        try:
            session = getattr(self, '_shared_session', None)
            if session and not session.closed:
                data = await self._do_av_request(session, request_params)
            else:
                async with aiohttp.ClientSession() as fallback_session:
                    data = await self._do_av_request(fallback_session, request_params)

            # Cache successful responses (cache key uses params without apikey)
            if data is not None and cache:
                cache.put(params, data)

            return data
        except Exception as e:
            self.logger.warning(f"Alpha Vantage request failed: {e}")
            return None

    async def _do_av_request(self, session: aiohttp.ClientSession, params: Dict[str, str]) -> Optional[Dict]:
        """
        Execute the actual AV HTTP request using the provided session.

        Args:
            session: aiohttp session to use
            params: Query parameters including apikey

        Returns:
            JSON response dict, or None on failure
        """
        async with session.get(
            self.AV_BASE_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                self.logger.warning(f"Alpha Vantage returned status {resp.status}")
                return None
            data = await resp.json(content_type=None)
            if "Error Message" in data or "Note" in data:
                msg = data.get("Error Message") or data.get("Note", "")
                self.logger.warning(f"Alpha Vantage API error: {msg}")
                return None
            if "Information" in data and "rate limit" in data.get("Information", "").lower():
                self.logger.warning(f"Alpha Vantage rate limited: {data['Information']}")
                return None
            return data

    async def execute(self) -> Dict[str, Any]:
        """
        Execute agent workflow: fetch → analyze → return result.

        Returns:
            Dict with execution result including:
                - success: bool
                - agent_type: str
                - data: analysis results or None
                - error: error message or None
                - duration_seconds: execution time
                - timestamp: ISO format timestamp
        """
        self.start_time = time.time()
        timestamp = datetime.utcnow().isoformat()

        try:
            self.logger.info(f"Starting {self.__class__.__name__} for {self.ticker}")

            # Fetch raw data
            raw_data = await self.fetch_data()
            self.logger.debug(f"Fetched data: {len(str(raw_data))} bytes")

            # Analyze data
            analysis_result = await self.analyze(raw_data)
            self.logger.debug(f"Analysis complete")

            self.result = analysis_result
            self.end_time = time.time()

            return {
                "success": True,
                "agent_type": self.get_agent_type(),
                "data": analysis_result,
                "error": None,
                "duration_seconds": self.get_duration(),
                "timestamp": timestamp
            }

        except Exception as e:
            self.error = str(e)
            self.end_time = time.time()
            self.logger.error(f"{self.__class__.__name__} failed: {e}", exc_info=True)

            return {
                "success": False,
                "agent_type": self.get_agent_type(),
                "data": None,
                "error": str(e),
                "duration_seconds": self.get_duration(),
                "timestamp": timestamp
            }

    def get_result(self) -> Optional[Dict[str, Any]]:
        """
        Get analysis result.

        Returns:
            Analysis result dictionary or None
        """
        return self.result

    def get_error(self) -> Optional[str]:
        """
        Get error message if execution failed.

        Returns:
            Error message or None
        """
        return self.error

    def get_duration(self) -> float:
        """
        Get execution duration in seconds.

        Returns:
            Duration in seconds, or 0 if not yet completed
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def get_agent_type(self) -> str:
        """
        Get agent type identifier.

        Returns:
            Agent type string (e.g., 'news', 'sentiment')
        """
        # Convert class name from CamelCase to snake_case
        name = self.__class__.__name__
        # Remove 'Agent' suffix if present
        if name.endswith('Agent'):
            name = name[:-5]

        # Convert to snake_case
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

        return name

    def validate_ticker(self) -> bool:
        """
        Validate ticker symbol format.

        Returns:
            True if ticker is valid format
        """
        if not self.ticker:
            return False

        # Basic validation: 1-5 uppercase letters
        import re
        return bool(re.match(r'^[A-Z]{1,5}$', self.ticker))

    def log_metrics(self, metrics: Dict[str, Any]):
        """
        Log agent-specific metrics.

        Args:
            metrics: Dictionary of metrics to log
        """
        self.logger.info(f"Metrics for {self.ticker}: {metrics}")
