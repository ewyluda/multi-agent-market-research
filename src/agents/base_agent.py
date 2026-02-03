"""Base agent class for all market research agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import logging
from datetime import datetime


class BaseAgent(ABC):
    """Abstract base class for all market research agents."""

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
