"""Orchestrator for coordinating all market research agents."""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .config import Config
from .agents.news_agent import NewsAgent
from .agents.sentiment_agent import SentimentAgent
from .agents.fundamentals_agent import FundamentalsAgent
from .agents.market_agent import MarketAgent
from .agents.technical_agent import TechnicalAgent
from .agents.solution_agent import SolutionAgent
from .database import DatabaseManager


class Orchestrator:
    """Coordinates execution of all market research agents."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_manager: Optional[DatabaseManager] = None,
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize orchestrator.

        Args:
            config: Configuration dictionary (uses Config class if not provided)
            db_manager: Database manager instance
            progress_callback: Optional callback for progress updates
        """
        self.config = config or self._get_config_dict()
        self.db_manager = db_manager or DatabaseManager(
            self.config.get("DATABASE_PATH", "market_research.db")
        )
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

    def _get_config_dict(self) -> Dict[str, Any]:
        """Convert Config class to dictionary."""
        config_dict = {}

        # Copy configuration attributes
        for attr in dir(Config):
            if not attr.startswith('_') and not callable(getattr(Config, attr)):
                config_dict[attr] = getattr(Config, attr)

        # Add LLM config
        config_dict["llm_config"] = Config.get_llm_config()

        return config_dict

    async def analyze_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Run full analysis on a ticker symbol.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Complete analysis result
        """
        start_time = time.time()
        ticker = ticker.upper()

        self.logger.info(f"Starting analysis for {ticker}")
        self._notify_progress("starting", ticker, 0)

        try:
            # Phase 1: Run data gathering agents in parallel
            self._notify_progress("gathering_data", ticker, 10)

            agent_results = await self._run_agents_parallel(ticker)

            # Phase 2: Run solution agent with aggregated results
            self._notify_progress("synthesizing", ticker, 80)

            final_analysis = await self._run_solution_agent(ticker, agent_results)

            # Phase 3: Save to database
            self._notify_progress("saving", ticker, 95)

            analysis_id = self._save_to_database(ticker, agent_results, final_analysis, time.time() - start_time)

            # Complete
            self._notify_progress("complete", ticker, 100)

            return {
                "success": True,
                "ticker": ticker,
                "analysis_id": analysis_id,
                "analysis": final_analysis,
                "agent_results": agent_results,
                "duration_seconds": time.time() - start_time
            }

        except Exception as e:
            self.logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
            self._notify_progress("error", ticker, 0, str(e))

            return {
                "success": False,
                "ticker": ticker,
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }

    async def _run_agents_parallel(self, ticker: str) -> Dict[str, Any]:
        """
        Run all data-gathering agents in parallel.

        Args:
            ticker: Stock ticker

        Returns:
            Dictionary of agent results
        """
        # Create agent instances
        news_agent = NewsAgent(ticker, self.config)
        fundamentals_agent = FundamentalsAgent(ticker, self.config)
        market_agent = MarketAgent(ticker, self.config)
        technical_agent = TechnicalAgent(ticker, self.config)

        # Run agents in parallel with timeout
        timeout = self.config.get("AGENT_TIMEOUT", 30)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self._run_agent_with_progress(news_agent, "news", ticker, 20),
                    self._run_agent_with_progress(fundamentals_agent, "fundamentals", ticker, 40),
                    self._run_agent_with_progress(market_agent, "market", ticker, 50),
                    self._run_agent_with_progress(technical_agent, "technical", ticker, 60),
                    return_exceptions=True
                ),
                timeout=timeout
            )

            # Unpack results
            news_result, fundamentals_result, market_result, technical_result = results

            # Now run sentiment agent (depends on news and market data)
            sentiment_agent = SentimentAgent(ticker, self.config)

            # Extract news articles and market data for sentiment
            news_articles = []
            if isinstance(news_result, dict) and news_result.get("success"):
                news_articles = news_result.get("data", {}).get("articles", [])

            market_data = {}
            if isinstance(market_result, dict) and market_result.get("success"):
                market_data = market_result.get("data", {})

            # Set context for sentiment agent
            sentiment_agent.set_context_data(news_articles, market_data)

            self._notify_progress("analyzing_sentiment", ticker, 70)
            try:
                sentiment_result = await asyncio.wait_for(
                    sentiment_agent.execute(),
                    timeout=timeout
                )
            except Exception as e:
                self.logger.error(f"Sentiment agent failed: {e}")
                sentiment_result = {"success": False, "error": str(e), "data": None, "agent_type": "sentiment", "duration_seconds": 0}

            return {
                "news": news_result if isinstance(news_result, dict) else {"success": False, "error": str(news_result)},
                "sentiment": sentiment_result if isinstance(sentiment_result, dict) else {"success": False, "error": str(sentiment_result)},
                "fundamentals": fundamentals_result if isinstance(fundamentals_result, dict) else {"success": False, "error": str(fundamentals_result)},
                "market": market_result if isinstance(market_result, dict) else {"success": False, "error": str(market_result)},
                "technical": technical_result if isinstance(technical_result, dict) else {"success": False, "error": str(technical_result)}
            }

        except asyncio.TimeoutError:
            self.logger.error(f"Agent execution timed out for {ticker}")
            raise Exception(f"Analysis timed out after {timeout} seconds")

    async def _run_agent_with_progress(
        self,
        agent,
        agent_name: str,
        ticker: str,
        progress_pct: int
    ):
        """Run agent and notify progress."""
        self._notify_progress(f"running_{agent_name}", ticker, progress_pct)
        return await agent.execute()

    async def _run_solution_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run solution agent to synthesize results.

        Args:
            ticker: Stock ticker
            agent_results: Results from all agents

        Returns:
            Final analysis
        """
        solution_agent = SolutionAgent(ticker, self.config, agent_results)

        timeout = self.config.get("AGENT_TIMEOUT", 30)

        try:
            result = await asyncio.wait_for(
                solution_agent.execute(),
                timeout=timeout
            )

            if result.get("success"):
                return result.get("data", {})
            else:
                raise Exception(f"Solution agent failed: {result.get('error')}")

        except asyncio.TimeoutError:
            raise Exception("Solution agent timed out")

    def _save_to_database(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
        final_analysis: Dict[str, Any],
        duration: float
    ) -> int:
        """
        Save analysis to database.

        Args:
            ticker: Stock ticker
            agent_results: Results from all agents
            final_analysis: Final analysis from solution agent
            duration: Total execution time

        Returns:
            Analysis ID
        """
        # Insert main analysis record
        analysis_id = self.db_manager.insert_analysis(
            ticker=ticker,
            recommendation=final_analysis.get("recommendation", "HOLD"),
            confidence_score=final_analysis.get("confidence", 0.0),
            overall_sentiment_score=((agent_results.get("sentiment") or {}).get("data") or {}).get("overall_sentiment", 0.0),
            solution_agent_reasoning=final_analysis.get("reasoning", ""),
            duration_seconds=duration
        )

        # Insert agent results
        for agent_type, result in agent_results.items():
            result = result or {}
            self.db_manager.insert_agent_result(
                analysis_id=analysis_id,
                agent_type=agent_type,
                success=result.get("success", False),
                data=result.get("data") or {},
                error=result.get("error"),
                duration_seconds=result.get("duration_seconds", 0.0)
            )

        # Insert sentiment scores
        sentiment_data = (agent_results.get("sentiment") or {}).get("data") or {}
        sentiment_factors = sentiment_data.get("factors", {})
        if sentiment_factors:
            self.db_manager.insert_sentiment_scores(analysis_id, sentiment_factors)

        # Cache price data
        market_data = (agent_results.get("market") or {}).get("data") or {}
        # Note: Would need to format price data properly from market agent

        # Cache news articles
        news_data = (agent_results.get("news") or {}).get("data") or {}
        news_articles = news_data.get("articles", [])
        if news_articles:
            self.db_manager.insert_news_articles(ticker, news_articles)

        self.logger.info(f"Saved analysis {analysis_id} for {ticker}")

        return analysis_id

    def _notify_progress(
        self,
        stage: str,
        ticker: str,
        progress: int,
        message: Optional[str] = None
    ):
        """
        Notify progress callback if set.

        Args:
            stage: Current stage
            ticker: Stock ticker
            progress: Progress percentage (0-100)
            message: Optional message
        """
        if self.progress_callback:
            try:
                self.progress_callback({
                    "stage": stage,
                    "ticker": ticker,
                    "progress": progress,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")

    def get_latest_analysis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get latest analysis for ticker from database.

        Args:
            ticker: Stock ticker

        Returns:
            Latest analysis or None
        """
        return self.db_manager.get_latest_analysis(ticker)

    def get_analysis_history(self, ticker: str, limit: int = 10) -> list:
        """
        Get analysis history for ticker.

        Args:
            ticker: Stock ticker
            limit: Number of records

        Returns:
            List of analyses
        """
        return self.db_manager.get_analysis_history(ticker, limit)
