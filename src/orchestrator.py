"""Orchestrator for coordinating all market research agents."""

import asyncio
import inspect
import logging
import time
from typing import Dict, Any, Optional, Callable, List

import aiohttp
from datetime import datetime

from .config import Config
from .agents.news_agent import NewsAgent
from .agents.sentiment_agent import SentimentAgent
from .agents.fundamentals_agent import FundamentalsAgent
from .agents.market_agent import MarketAgent
from .agents.technical_agent import TechnicalAgent
from .agents.macro_agent import MacroAgent
from .agents.options_agent import OptionsAgent
from .agents.solution_agent import SolutionAgent
from .database import DatabaseManager
from .av_rate_limiter import AVRateLimiter
from .av_cache import AVCache


class Orchestrator:
    """Coordinates execution of all market research agents."""

    # Agent registry: maps agent name to class and dependencies
    AGENT_REGISTRY = {
        "news": {"class": NewsAgent, "requires": []},
        "market": {"class": MarketAgent, "requires": []},
        "fundamentals": {"class": FundamentalsAgent, "requires": []},
        "technical": {"class": TechnicalAgent, "requires": []},
        "macro": {"class": MacroAgent, "requires": []},
        "options": {"class": OptionsAgent, "requires": []},
        "sentiment": {"class": SentimentAgent, "requires": ["news"]},
    }

    DEFAULT_AGENTS = ["news", "market", "fundamentals", "technical", "macro", "options", "sentiment"]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_manager: Optional[DatabaseManager] = None,
        progress_callback: Optional[Callable] = None,
        rate_limiter: Optional[AVRateLimiter] = None,
        av_cache: Optional[AVCache] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            config: Configuration dictionary (uses Config class if not provided)
            db_manager: Database manager instance
            progress_callback: Optional callback for progress updates
            rate_limiter: Shared AV rate limiter (persists across requests via app.state)
            av_cache: Shared AV response cache (persists across requests via app.state)
        """
        self.config = config or self._get_config_dict()
        self.db_manager = db_manager or DatabaseManager(
            self.config.get("DATABASE_PATH", "market_research.db")
        )
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

        # Shared AV infrastructure
        self._rate_limiter = rate_limiter or AVRateLimiter(
            requests_per_minute=self.config.get("AV_RATE_LIMIT_PER_MINUTE", 5),
            requests_per_day=self.config.get("AV_RATE_LIMIT_PER_DAY", 25),
        )
        self._av_cache = av_cache or AVCache()
        self._shared_session: Optional[aiohttp.ClientSession] = None

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

    async def _create_shared_session(self) -> aiohttp.ClientSession:
        """Create a shared aiohttp session for all agents in this analysis."""
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
        )
        self._shared_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=15),
        )
        return self._shared_session

    async def _close_shared_session(self):
        """Close the shared session and its connector."""
        if self._shared_session and not self._shared_session.closed:
            await self._shared_session.close()
            self._shared_session = None

    def _inject_shared_resources(self, agent):
        """Inject shared AV resources into an agent instance."""
        agent._shared_session = self._shared_session
        agent._rate_limiter = self._rate_limiter
        agent._av_cache = self._av_cache

    def _resolve_agents(self, requested: Optional[List[str]] = None) -> List[str]:
        """
        Resolve the final list of agents to run, enforcing dependencies.

        Args:
            requested: User-requested agents, or None for all defaults

        Returns:
            List of agent names to run
        """
        if not requested:
            agents = list(self.DEFAULT_AGENTS)
            if not self.config.get("MACRO_AGENT_ENABLED", True):
                agents = [a for a in agents if a != "macro"]
            if not self.config.get("OPTIONS_AGENT_ENABLED", True):
                agents = [a for a in agents if a != "options"]
            return agents

        agents = set(requested)

        # Add dependencies automatically
        for agent_name in list(agents):
            deps = self.AGENT_REGISTRY.get(agent_name, {}).get("requires", [])
            for dep in deps:
                if dep not in agents:
                    self.logger.info(f"Auto-adding '{dep}' agent (dependency of '{agent_name}')")
                    agents.add(dep)

        return list(agents)

    async def analyze_ticker(
        self,
        ticker: str,
        requested_agents: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run full analysis on a ticker symbol.

        Args:
            ticker: Stock ticker symbol
            requested_agents: Optional list of agent names to run (default: all)

        Returns:
            Complete analysis result
        """
        start_time = time.time()
        ticker = ticker.upper()

        # Resolve which agents to run
        agents_to_run = self._resolve_agents(requested_agents)

        self.logger.info(f"Starting analysis for {ticker} (agents: {', '.join(sorted(agents_to_run))})")
        await self._notify_progress("starting", ticker, 0)

        # Create shared session for this analysis run
        await self._create_shared_session()

        try:
            # Phase 1: Run data gathering agents
            await self._notify_progress("gathering_data", ticker, 10)

            agent_results = await self._run_agents(ticker, agents_to_run)

            # Phase 2: Run solution agent with aggregated results
            await self._notify_progress("synthesizing", ticker, 80)

            final_analysis = await self._run_solution_agent(ticker, agent_results)
            previous_analysis = self.db_manager.get_latest_analysis(ticker)
            final_analysis["signal_snapshot"] = self._build_signal_snapshot(final_analysis, agent_results)
            change_summary = self._build_change_summary(previous_analysis, final_analysis)
            final_analysis["changes_since_last_run"] = change_summary
            final_analysis["change_summary"] = change_summary

            # Phase 3: Save to database
            await self._notify_progress("saving", ticker, 95)

            analysis_id = self._save_to_database(ticker, agent_results, final_analysis, time.time() - start_time)

            # Evaluate alert rules
            alerts_triggered = []
            if self.config.get("ALERTS_ENABLED", True):
                try:
                    from .alert_engine import AlertEngine
                    alert_engine = AlertEngine(self.db_manager)
                    alerts_triggered = alert_engine.evaluate_alerts(ticker, analysis_id)
                except Exception as e:
                    self.logger.warning(f"Alert evaluation failed: {e}")

            # Complete
            await self._notify_progress("complete", ticker, 100)

            return {
                "success": True,
                "ticker": ticker,
                "analysis_id": analysis_id,
                "analysis": final_analysis,
                "agent_results": agent_results,
                "alerts_triggered": alerts_triggered,
                "duration_seconds": time.time() - start_time
            }

        except Exception as e:
            self.logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
            await self._notify_progress("error", ticker, 0, str(e))

            return {
                "success": False,
                "ticker": ticker,
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }

        finally:
            await self._close_shared_session()

    async def _run_agents(self, ticker: str, agents_to_run: List[str]) -> Dict[str, Any]:
        """
        Run data-gathering agents, optionally in parallel.

        Args:
            ticker: Stock ticker
            agents_to_run: List of agent names to run

        Returns:
            Dictionary of agent results
        """
        # Separate data agents from sentiment (which depends on news/market)
        data_agent_names = [a for a in agents_to_run if a != "sentiment"]
        run_sentiment = "sentiment" in agents_to_run

        # Create data agent instances
        progress_map = {"news": 20, "fundamentals": 40, "market": 50, "macro": 55, "options": 57, "technical": 60}
        agents = {}
        for name in data_agent_names:
            agent_info = self.AGENT_REGISTRY.get(name)
            if agent_info:
                agent = agent_info["class"](ticker, self.config)
                self._inject_shared_resources(agent)
                agents[name] = agent

        timeout = self.config.get("AGENT_TIMEOUT", 30)
        use_parallel = self.config.get("PARALLEL_AGENTS", True)

        if use_parallel:
            results = await self._run_data_agents_parallel(agents, ticker, timeout, progress_map)
        else:
            results = await self._run_data_agents_sequential(agents, ticker, timeout, progress_map)

        # Run sentiment agent if requested (depends on news + market data)
        if run_sentiment:
            sentiment_agent = SentimentAgent(ticker, self.config)
            self._inject_shared_resources(sentiment_agent)

            news_articles = []
            twitter_posts = []
            news_result = results.get("news")
            if isinstance(news_result, dict) and news_result.get("success"):
                news_data = news_result.get("data", {})
                news_articles = news_data.get("articles", [])
                twitter_posts = news_data.get("twitter_posts", [])

            market_data = {}
            market_result = results.get("market")
            if isinstance(market_result, dict) and market_result.get("success"):
                market_data = market_result.get("data", {})

            sentiment_agent.set_context_data(news_articles, market_data, twitter_posts)

            await self._notify_progress("analyzing_sentiment", ticker, 70)
            try:
                sentiment_result = await asyncio.wait_for(
                    sentiment_agent.execute(),
                    timeout=timeout
                )
                results["sentiment"] = sentiment_result if isinstance(sentiment_result, dict) else {"success": False, "error": str(sentiment_result)}
            except Exception as e:
                self.logger.error(f"Sentiment agent failed: {e}")
                results["sentiment"] = {"success": False, "error": str(e), "data": None, "agent_type": "sentiment", "duration_seconds": 0}

        return results

    async def _run_data_agents_parallel(
        self,
        agents: Dict[str, Any],
        ticker: str,
        timeout: int,
        progress_map: Dict[str, int],
    ) -> Dict[str, Any]:
        """Run data agents in parallel using asyncio.gather."""
        tasks = []
        agent_order = []
        for name, agent in agents.items():
            progress_pct = progress_map.get(name, 30)
            tasks.append(self._run_agent_with_progress(agent, name, ticker, progress_pct))
            agent_order.append(name)

        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self.logger.error(f"Agent execution timed out for {ticker}")
            raise Exception(f"Analysis timed out after {timeout} seconds")

        results = {}
        for i, name in enumerate(agent_order):
            r = raw_results[i]
            results[name] = r if isinstance(r, dict) else {"success": False, "error": str(r)}
        return results

    async def _run_data_agents_sequential(
        self,
        agents: Dict[str, Any],
        ticker: str,
        timeout: int,
        progress_map: Dict[str, int],
    ) -> Dict[str, Any]:
        """Run data agents sequentially."""
        results = {}
        for name, agent in agents.items():
            progress_pct = progress_map.get(name, 30)
            try:
                r = await asyncio.wait_for(
                    self._run_agent_with_progress(agent, name, ticker, progress_pct),
                    timeout=timeout,
                )
                results[name] = r if isinstance(r, dict) else {"success": False, "error": str(r)}
            except asyncio.TimeoutError:
                results[name] = {"success": False, "error": f"{name} agent timed out"}
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
        return results

    async def _run_agent_with_progress(
        self,
        agent,
        agent_name: str,
        ticker: str,
        progress_pct: int
    ):
        """Run agent and notify progress."""
        await self._notify_progress(f"running_{agent_name}", ticker, progress_pct)
        return await agent.execute()

    async def _run_solution_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
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
            duration_seconds=duration,
            score=final_analysis.get("score"),
            decision_card=final_analysis.get("decision_card"),
            change_summary=final_analysis.get("changes_since_last_run") or final_analysis.get("change_summary"),
            analysis_payload=final_analysis,
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

    def _safe_float(self, value: Any) -> Optional[float]:
        """Convert value to float when possible."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _classify_market_regime(self, trend: Optional[str]) -> str:
        """Normalize free-form trend text into a regime bucket."""
        if not trend:
            return "unknown"
        t = str(trend).lower()
        if any(keyword in t for keyword in ["uptrend", "bull", "rally"]):
            return "bullish"
        if any(keyword in t for keyword in ["downtrend", "bear", "selloff"]):
            return "bearish"
        return "neutral"

    def _classify_sentiment_regime(self, sentiment_score: Optional[float]) -> str:
        """Map sentiment score to bullish/neutral/bearish regime."""
        score = self._safe_float(sentiment_score)
        if score is None:
            return "unknown"
        if score >= 0.2:
            return "bullish"
        if score <= -0.2:
            return "bearish"
        return "neutral"

    def _build_signal_snapshot(self, final_analysis: Dict[str, Any], agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Capture high-signal fields so next runs can compute meaningful deltas."""
        market_data = (agent_results.get("market") or {}).get("data") or {}
        fundamentals_data = (agent_results.get("fundamentals") or {}).get("data") or {}
        technical_data = (agent_results.get("technical") or {}).get("data") or {}
        macro_data = (agent_results.get("macro") or {}).get("data") or {}
        options_data = (agent_results.get("options") or {}).get("data") or {}
        sentiment_data = (agent_results.get("sentiment") or {}).get("data") or {}

        market_trend = market_data.get("trend")
        sentiment_score = self._safe_float(sentiment_data.get("overall_sentiment"))

        return {
            "recommendation": final_analysis.get("recommendation"),
            "score": self._safe_float(final_analysis.get("score")),
            "confidence": self._safe_float(final_analysis.get("confidence")),
            "market_trend": market_trend,
            "market_regime": self._classify_market_regime(market_trend),
            "fundamentals_health_score": self._safe_float(fundamentals_data.get("health_score")),
            "technical_signal": (technical_data.get("signals") or {}).get("overall"),
            "technical_strength": self._safe_float((technical_data.get("signals") or {}).get("strength")),
            "sentiment_score": sentiment_score,
            "sentiment_regime": self._classify_sentiment_regime(sentiment_score),
            "options_signal": options_data.get("overall_signal"),
            "options_put_call_ratio": self._safe_float(options_data.get("put_call_ratio")),
            "macro_risk_environment": macro_data.get("risk_environment"),
            "macro_cycle": macro_data.get("economic_cycle"),
        }

    def _build_change_summary(
        self,
        previous_analysis: Optional[Dict[str, Any]],
        current_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute material run-to-run deltas for user-facing actionability."""
        if not previous_analysis:
            return {
                "has_previous": False,
                "summary": "No previous analysis to compare against yet.",
                "material_changes": [],
                "change_count": 0,
            }

        prev_payload = previous_analysis.get("analysis") or previous_analysis.get("analysis_payload") or {}
        curr_payload = current_analysis or {}

        prev_snapshot = prev_payload.get("signal_snapshot") or {}
        curr_snapshot = curr_payload.get("signal_snapshot") or {}
        changes: List[Dict[str, Any]] = []

        def add_change(change_type: str, label: str, previous: Any, current: Any, impact: str = "medium"):
            if previous == current:
                return
            changes.append({
                "type": change_type,
                "label": label,
                "previous": previous,
                "current": current,
                "impact": impact,
            })

        prev_rec = prev_payload.get("recommendation") or previous_analysis.get("recommendation")
        curr_rec = curr_payload.get("recommendation")
        if prev_rec and curr_rec and prev_rec != curr_rec:
            add_change(
                "recommendation_change",
                f"Recommendation changed from {prev_rec} to {curr_rec}",
                prev_rec,
                curr_rec,
                impact="high",
            )

        prev_score = self._safe_float(prev_payload.get("score", previous_analysis.get("score")))
        curr_score = self._safe_float(curr_payload.get("score"))
        if prev_score is not None and curr_score is not None and abs(curr_score - prev_score) >= 15:
            add_change(
                "score_shift",
                f"Score moved from {prev_score:+.0f} to {curr_score:+.0f}",
                prev_score,
                curr_score,
                impact="high" if abs(curr_score - prev_score) >= 25 else "medium",
            )

        prev_conf = self._safe_float(prev_payload.get("confidence", previous_analysis.get("confidence_score")))
        curr_conf = self._safe_float(curr_payload.get("confidence"))
        if prev_conf is not None and curr_conf is not None and abs(curr_conf - prev_conf) >= 0.10:
            add_change(
                "confidence_shift",
                f"Confidence moved from {prev_conf:.0%} to {curr_conf:.0%}",
                prev_conf,
                curr_conf,
                impact="medium",
            )

        prev_market_regime = prev_snapshot.get("market_regime") or self._classify_market_regime(prev_snapshot.get("market_trend"))
        curr_market_regime = curr_snapshot.get("market_regime") or self._classify_market_regime(curr_snapshot.get("market_trend"))
        if prev_market_regime != "unknown" and curr_market_regime != "unknown" and prev_market_regime != curr_market_regime:
            add_change(
                "market_regime_flip",
                f"Market trend regime flipped from {prev_market_regime} to {curr_market_regime}",
                prev_market_regime,
                curr_market_regime,
                impact="high",
            )

        prev_sent_regime = prev_snapshot.get("sentiment_regime") or self._classify_sentiment_regime(prev_snapshot.get("sentiment_score"))
        curr_sent_regime = curr_snapshot.get("sentiment_regime") or self._classify_sentiment_regime(curr_snapshot.get("sentiment_score"))
        if prev_sent_regime != "unknown" and curr_sent_regime != "unknown" and prev_sent_regime != curr_sent_regime:
            add_change(
                "sentiment_regime_flip",
                f"Sentiment regime shifted from {prev_sent_regime} to {curr_sent_regime}",
                prev_sent_regime,
                curr_sent_regime,
                impact="high",
            )

        prev_health = self._safe_float(prev_snapshot.get("fundamentals_health_score"))
        curr_health = self._safe_float(curr_snapshot.get("fundamentals_health_score"))
        if prev_health is not None and curr_health is not None and abs(curr_health - prev_health) >= 10:
            add_change(
                "fundamentals_shift",
                f"Fundamentals health score moved from {prev_health:.0f} to {curr_health:.0f}",
                prev_health,
                curr_health,
                impact="medium",
            )

        prev_options_signal = prev_snapshot.get("options_signal")
        curr_options_signal = curr_snapshot.get("options_signal")
        if prev_options_signal and curr_options_signal and prev_options_signal != curr_options_signal:
            add_change(
                "options_signal_change",
                f"Options signal changed from {prev_options_signal} to {curr_options_signal}",
                prev_options_signal,
                curr_options_signal,
                impact="medium",
            )

        prev_put_call = self._safe_float(prev_snapshot.get("options_put_call_ratio"))
        curr_put_call = self._safe_float(curr_snapshot.get("options_put_call_ratio"))
        if prev_put_call is not None and curr_put_call is not None and abs(curr_put_call - prev_put_call) >= 0.20:
            add_change(
                "options_skew_shift",
                f"Put/Call ratio moved from {prev_put_call:.2f} to {curr_put_call:.2f}",
                prev_put_call,
                curr_put_call,
                impact="medium",
            )

        prev_macro = prev_snapshot.get("macro_risk_environment")
        curr_macro = curr_snapshot.get("macro_risk_environment")
        if prev_macro and curr_macro and prev_macro != curr_macro:
            add_change(
                "macro_regime_change",
                f"Macro risk environment shifted from {prev_macro} to {curr_macro}",
                prev_macro,
                curr_macro,
                impact="high",
            )

        # Keep output concise by default.
        changes = changes[:6]
        if changes:
            summary = "; ".join(change["label"] for change in changes[:3])
            if len(changes) > 3:
                summary += f"; and {len(changes) - 3} more change(s)"
        else:
            summary = "No material signal changes versus the previous run."

        return {
            "has_previous": True,
            "summary": summary,
            "material_changes": changes,
            "change_count": len(changes),
            "compared_to_analysis_id": previous_analysis.get("id"),
            "compared_to_timestamp": previous_analysis.get("timestamp"),
        }

    async def _notify_progress(
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
                update = {
                    "stage": stage,
                    "ticker": ticker,
                    "progress": progress,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                if inspect.iscoroutinefunction(self.progress_callback):
                    await self.progress_callback(update)
                else:
                    self.progress_callback(update)
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
