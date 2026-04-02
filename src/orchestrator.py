"""Orchestrator for coordinating all market research agents."""

import asyncio
import inspect
import logging
import time
from typing import Dict, Any, Optional, Callable, List

import aiohttp
from datetime import datetime, timezone

from .config import Config
from .agents.news_agent import NewsAgent
from .agents.sentiment_agent import SentimentAgent
from .agents.fundamentals_agent import FundamentalsAgent
from .agents.market_agent import MarketAgent
from .agents.technical_agent import TechnicalAgent
from .agents.macro_agent import MacroAgent
from .agents.options_agent import OptionsAgent
from .agents.leadership_agent import LeadershipAgent
from .agents.earnings_agent import EarningsAgent
from .agents.thesis_agent import ThesisAgent
from .agents.earnings_review_agent import EarningsReviewAgent
from .agents.narrative_agent import NarrativeAgent
from .agents.solution_agent import SolutionAgent
from .agents.council_validator_agent import CouncilValidatorAgent
from .database import DatabaseManager
from .data_provider import OpenBBDataProvider
from .portfolio_engine import PortfolioEngine
from .signal_contract import build_signal_contract_v2, validate_signal_contract_v2, _safe_float as safe_float
from .validation_rules import validate as run_validation_rules
from .thesis_health import evaluate_thesis_health
from .perception_ledger import extract_kpi_snapshots
from .repositories.perception_repo import PerceptionRepository
from .inflection_detector import InflectionDetector


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
        "leadership": {"class": LeadershipAgent, "requires": []},
        "earnings": {"class": EarningsAgent, "requires": []},
        "thesis": {"class": ThesisAgent, "requires": []},
        "earnings_review": {"class": EarningsReviewAgent, "requires": []},
        "narrative": {"class": NarrativeAgent, "requires": []},
        "sentiment": {"class": SentimentAgent, "requires": ["news"]},
    }

    DEFAULT_AGENTS = ["news", "market", "fundamentals", "technical", "macro", "options", "leadership", "earnings", "sentiment"]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_manager: Optional[DatabaseManager] = None,
        progress_callback: Optional[Callable] = None,
        data_provider: Optional[OpenBBDataProvider] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            config: Configuration dictionary (uses Config class if not provided)
            db_manager: Database manager instance
            progress_callback: Optional callback for progress updates
            data_provider: Shared OpenBB data provider (persists across requests via app.state)
        """
        self.config = config or self._get_config_dict()
        self.db_manager = db_manager or DatabaseManager(
            self.config.get("DATABASE_PATH", "market_research.db")
        )
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

        # Shared data provider (OpenBB SDK)
        self._data_provider = data_provider or OpenBBDataProvider(self.config)
        self._shared_session: Optional[aiohttp.ClientSession] = None
        self._validated_tickers: set = set()

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

    async def _validate_ticker(self, ticker: str) -> bool:
        """
        Validate that a ticker symbol corresponds to a real tradeable security.

        Uses yfinance for a lightweight check. Caches validated tickers in-memory.
        Fails open (returns True) if yfinance is unavailable.
        """
        if ticker in self._validated_tickers:
            return True

        try:
            import yfinance as yf

            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: yf.Ticker(ticker).info
            )
            short_name = (info or {}).get("shortName")
            if not short_name:
                return False

            self._validated_tickers.add(ticker)
            return True
        except Exception as e:
            self.logger.warning(f"Ticker validation skipped for {ticker} (yfinance error: {e})")
            return True  # Fail-open

    def _inject_shared_resources(self, agent):
        """Inject shared resources into an agent instance."""
        agent._shared_session = self._shared_session
        agent._data_provider = self._data_provider

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
            if not self.config.get("EARNINGS_AGENT_ENABLED", True):
                agents = [a for a in agents if a != "earnings"]
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

        # Validate ticker is a real symbol before burning API budget
        if not await self._validate_ticker(ticker):
            return {
                "success": False,
                "ticker": ticker,
                "error": f"Unknown ticker symbol: {ticker}",
                "duration_seconds": time.time() - start_time,
            }

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

            final_analysis, thesis_result, earnings_review_result, narrative_result = await asyncio.gather(
                self._run_solution_agent(ticker, agent_results),
                self._run_thesis_agent(ticker, agent_results),
                self._run_earnings_review_agent(ticker, agent_results),
                self._run_narrative_agent(ticker, agent_results),
            )
            if thesis_result:
                final_analysis["thesis"] = thesis_result
            if earnings_review_result:
                final_analysis["earnings_review"] = earnings_review_result
            if narrative_result:
                final_analysis["narrative"] = narrative_result
            previous_analysis = self.db_manager.get_latest_analysis(ticker)
            final_analysis["signal_snapshot"] = self._build_signal_snapshot(final_analysis, agent_results)
            diagnostics = self._build_diagnostics(agent_results)
            final_analysis["diagnostics"] = diagnostics
            final_analysis["diagnostics_summary"] = self._build_diagnostics_summary(diagnostics)
            change_summary = self._build_change_summary(previous_analysis, final_analysis)
            final_analysis["changes_since_last_run"] = change_summary
            final_analysis["change_summary"] = change_summary
            self._attach_signal_contract_v2(ticker, final_analysis, agent_results, diagnostics)

            # Phase 2.5: Two-tier validation
            validation_report: Optional[Dict[str, Any]] = None
            if self.config.get("VALIDATION_V1_ENABLED", True):
                await self._notify_progress("validating", ticker, 88)
                try:
                    validation_report = await self._run_validation(ticker, final_analysis, agent_results)
                    penalty = validation_report.get("total_confidence_penalty", 0.0)
                    if penalty > 0:
                        raw_conf = float(final_analysis.get("confidence") or 0.5)
                        final_analysis["confidence"] = max(raw_conf - penalty, 0.05)
                    # Apply hard recommendation override if supermajority disagrees
                    override_rec = (
                        validation_report.get("rule_validation", {}).get("override_recommendation")
                    )
                    if override_rec:
                        self.logger.warning(
                            f"Recommendation override for {ticker}: "
                            f"{final_analysis.get('recommendation')} → {override_rec} "
                            f"(supermajority agent disagreement)"
                        )
                        final_analysis["recommendation"] = override_rec
                        final_analysis["recommendation_overridden"] = True
                    sc = final_analysis.get("signal_contract_v2")
                    if isinstance(sc, dict):
                        sc["validation"] = {
                            "status": validation_report.get("overall_status", "clean"),
                            "confidence_penalty": penalty,
                            "contradictions_count": (
                                validation_report.get("rule_validation", {}).get("contradictions", 0)
                                + validation_report.get("council_validation", {}).get("total_contradictions", 0)
                            ),
                            "spot_check_requested": validation_report.get("spot_check_requested", False),
                        }
                    final_analysis["validation"] = validation_report
                except Exception as _val_exc:
                    self.logger.warning(f"Validation phase failed (non-blocking): {_val_exc}")

            # Phase 2.6: Thesis Health Check
            thesis_health_report: Optional[Dict[str, Any]] = None
            if self.config.get("THESIS_HEALTH_ENABLED", True):
                thesis_card = self.db_manager.get_thesis_card(ticker)
                if thesis_card and thesis_card.get("health_indicators"):
                    try:
                        prev_snapshot = self.db_manager.get_latest_thesis_health(ticker)
                        prev_health = prev_snapshot.get("overall_health") if prev_snapshot else None

                        thesis_health_report = evaluate_thesis_health(
                            thesis_card=thesis_card,
                            agent_results=agent_results,
                            previous_health=prev_health,
                        )

                        # Auto-snapshot baselines back to thesis card
                        if thesis_health_report.get("baselines_updated", 0) > 0:
                            for ind in thesis_health_report["indicators"]:
                                for tc_ind in thesis_card.get("health_indicators", []):
                                    if tc_ind["proxy_signal"] == ind["proxy_signal"] and not tc_ind.get("baseline_value"):
                                        tc_ind["baseline_value"] = ind["current_value"]
                            self.db_manager.upsert_thesis_card(ticker, thesis_card)

                        final_analysis["thesis_health"] = thesis_health_report
                    except Exception as _th_exc:
                        self.logger.warning(f"Thesis health check failed (non-blocking): {_th_exc}")

            # Baseline observability for rollout gating and regression tracking.
            self._log_baseline_metrics(
                ticker=ticker,
                started_at=start_time,
                agent_results=agent_results,
                diagnostics=diagnostics,
            )

            if self.config.get("PORTFOLIO_ACTIONS_ENABLED", True):
                try:
                    portfolio_snapshot = self.db_manager.get_portfolio_snapshot()
                    portfolio_overlay = PortfolioEngine(portfolio_snapshot).evaluate(
                        ticker=ticker,
                        analysis=final_analysis,
                        diagnostics=diagnostics,
                    )
                    if not self.config.get("PORTFOLIO_OPTIMIZER_V2_ENABLED", False):
                        portfolio_overlay.pop("portfolio_action_v2", None)
                        portfolio_overlay.pop("portfolio_summary_v2", None)
                    final_analysis.update(portfolio_overlay)
                except Exception as exc:
                    self.logger.warning(f"Portfolio advisory overlay failed: {exc}")

            # Phase 3: Save to database
            await self._notify_progress("saving", ticker, 95)

            analysis_id = None
            db_write_warning = None
            try:
                analysis_id = self._save_to_database(ticker, agent_results, final_analysis, time.time() - start_time)
            except Exception as db_exc:
                self.logger.error(f"Database write failed for {ticker}: {db_exc}", exc_info=True)
                db_write_warning = f"Analysis completed but database save failed: {db_exc}"

            # Persist validation result now that analysis_id is available
            if analysis_id and validation_report is not None:
                try:
                    self.db_manager.save_validation_result(
                        analysis_id=analysis_id,
                        ticker=ticker,
                        validation_id=validation_report["validation_id"],
                        overall_status=validation_report["overall_status"],
                        original_confidence=validation_report["original_confidence"],
                        adjusted_confidence=validation_report["adjusted_confidence"],
                        total_confidence_penalty=validation_report["total_confidence_penalty"],
                        rule_checks_total=validation_report.get("rule_validation", {}).get("total_rules_checked", 0),
                        rule_contradictions=validation_report.get("rule_validation", {}).get("contradictions", 0),
                        council_claims_total=validation_report.get("council_validation", {}).get("total_claims_checked", 0),
                        council_contradictions=validation_report.get("council_validation", {}).get("total_contradictions", 0),
                        spot_check_requested=validation_report.get("spot_check_requested", False),
                        report_json=validation_report,
                    )
                except Exception as _db_exc:
                    self.logger.warning(f"Failed to save validation result: {_db_exc}")

            # Capture perception snapshots + detect inflections
            inflection_summary = None
            if analysis_id:
                try:
                    data_quality = (final_analysis.get("diagnostics") or {}).get("data_quality", {})
                    quality_score = data_quality.get("agent_success_rate", 0.8)
                    snapshots = extract_kpi_snapshots(agent_results, confidence=quality_score)
                    if snapshots:
                        perception_repo = PerceptionRepository(self.db_manager)
                        perception_repo.insert_snapshots(ticker, analysis_id, snapshots)
                        self.logger.info(f"Captured {len(snapshots)} perception snapshots for {ticker}")

                        # Detect inflections against prior snapshots
                        prior = perception_repo.get_prior_snapshots(ticker, analysis_id)
                        if prior:
                            detector = InflectionDetector()
                            inflections = detector.detect(prior, snapshots)
                            inflection_summary = detector.build_summary(inflections)

                            if inflections:
                                perception_repo.insert_inflection_events(
                                    ticker, analysis_id, inflections,
                                )
                                for inf in inflections:
                                    inf["convergence_score"] = inflection_summary["convergence_score"]
                                    inf["source_agents"] = [inf["source_agent"]]
                                self.logger.info(
                                    f"Detected {len(inflections)} inflections for {ticker} "
                                    f"(convergence={inflection_summary['convergence_score']:.2f})"
                                )
                except Exception as e:
                    self.logger.warning(f"Perception/inflection processing failed: {e}")

            # Persist thesis health snapshot
            if analysis_id and thesis_health_report is not None:
                try:
                    self.db_manager.save_thesis_health_snapshot(
                        analysis_id=analysis_id,
                        ticker=ticker,
                        overall_health=thesis_health_report["overall_health"],
                        previous_health=thesis_health_report.get("previous_health"),
                        health_changed=thesis_health_report.get("health_changed", False),
                        indicators_json=thesis_health_report.get("indicators", []),
                        baselines_updated=thesis_health_report.get("baselines_updated", 0),
                    )
                except Exception as _db_exc:
                    self.logger.warning(f"Failed to save thesis health snapshot: {_db_exc}")

            if analysis_id and self.config.get("CALIBRATION_ENABLED", True):
                try:
                    baseline_price = self._extract_baseline_price(agent_results, final_analysis)
                    predicted_up_probability = self._derive_predicted_up_probability(final_analysis)
                    if baseline_price is not None:
                        portfolio_profile = self.db_manager.get_portfolio_profile()
                        self.db_manager.create_outcome_rows_for_analysis(
                            analysis_id=analysis_id,
                            ticker=ticker,
                            baseline_price=baseline_price,
                            confidence=final_analysis.get("confidence"),
                            predicted_up_probability=predicted_up_probability,
                            transaction_cost_bps=portfolio_profile.get("default_transaction_cost_bps"),
                            slippage_bps=5.0,
                        )
                except Exception as exc:
                    self.logger.warning(f"Failed to enqueue calibration outcomes: {exc}")

            # Evaluate alert rules
            alerts_triggered = []
            if analysis_id and self.config.get("ALERTS_ENABLED", True):
                try:
                    from .alert_engine import AlertEngine
                    alert_engine = AlertEngine(self.db_manager)
                    alerts_triggered = alert_engine.evaluate_alerts(ticker, analysis_id)
                except Exception as e:
                    self.logger.warning(f"Alert evaluation failed: {e}")

            # Complete
            await self._notify_progress("complete", ticker, 100)

            result = {
                "success": True,
                "ticker": ticker,
                "analysis_id": analysis_id,
                "analysis": final_analysis,
                "agent_results": agent_results,
                "alerts_triggered": alerts_triggered,
                "inflection_summary": inflection_summary,
                "duration_seconds": time.time() - start_time,
            }
            if db_write_warning:
                result["db_write_warning"] = db_write_warning
            return result

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
        progress_map = {"news": 20, "fundamentals": 40, "market": 50, "macro": 55, "options": 57, "earnings": 58, "leadership": 59, "technical": 60}
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

        # Inject calibration context if available
        try:
            hit_rate_by_horizon = {}
            for horizon in (1, 7, 30):
                row = self.db_manager.get_reliability_hit_rate(horizon_days=horizon, confidence_raw=0.5)
                if row:
                    hit_rate_by_horizon[f"{horizon}d"] = row
            if hit_rate_by_horizon:
                solution_agent.calibration_context = hit_rate_by_horizon
        except Exception as e:
            self.logger.debug(f"Could not load calibration context: {e}")

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

    async def _run_thesis_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Run thesis agent to generate bull/bear debate (non-blocking).

        Args:
            ticker: Stock ticker
            agent_results: Results from all data agents

        Returns:
            Thesis output dict, or None on failure
        """
        try:
            thesis_agent = ThesisAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(thesis_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                thesis_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Thesis agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Thesis agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Thesis agent error for {ticker}: {e}")
            return None

    async def _run_earnings_review_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Run earnings review agent for structured earnings digest (non-blocking).
        """
        try:
            review_agent = EarningsReviewAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(review_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                review_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Earnings review agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Earnings review agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Earnings review agent error for {ticker}: {e}")
            return None

    async def _run_narrative_agent(
        self,
        ticker: str,
        agent_results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Run narrative agent for multi-year financial story (non-blocking)."""
        try:
            narrative_agent = NarrativeAgent(ticker, self.config, agent_results)
            self._inject_shared_resources(narrative_agent)
            timeout = self.config.get("AGENT_TIMEOUT", 30)
            result = await asyncio.wait_for(
                narrative_agent.execute(),
                timeout=timeout,
            )
            if result.get("success"):
                return result.get("data")
            else:
                self.logger.warning(f"Narrative agent failed for {ticker}: {result.get('error')}")
                return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Narrative agent timed out for {ticker}")
            return None
        except Exception as e:
            self.logger.warning(f"Narrative agent error for {ticker}: {e}")
            return None

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
            solution_agent_reasoning=self._reasoning_for_persistence(final_analysis),
            duration_seconds=duration,
            score=final_analysis.get("score"),
            decision_card=final_analysis.get("decision_card"),
            change_summary=final_analysis.get("changes_since_last_run") or final_analysis.get("change_summary"),
            analysis_payload=final_analysis,
            analysis_schema_version=final_analysis.get("analysis_schema_version", "v1"),
            signal_contract_v2=final_analysis.get("signal_contract_v2"),
            ev_score_7d=final_analysis.get("ev_score_7d"),
            confidence_calibrated=final_analysis.get("confidence_calibrated"),
            data_quality_score=final_analysis.get("data_quality_score"),
            regime_label=final_analysis.get("regime_label"),
            rationale_summary=final_analysis.get("rationale_summary"),
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

    def _reasoning_for_persistence(self, final_analysis: Dict[str, Any]) -> str:
        """Persist concise rationale unless CoT persistence is explicitly enabled."""
        if self.config.get("COT_PERSISTENCE_ENABLED", False):
            return str(final_analysis.get("reasoning") or final_analysis.get("rationale_summary") or "")
        return str(final_analysis.get("rationale_summary") or final_analysis.get("summary") or "").strip()

    def _attach_signal_contract_v2(
        self,
        ticker: str,
        final_analysis: Dict[str, Any],
        agent_results: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> None:
        """Attach deterministic signal_contract_v2 when the feature flag is enabled."""
        if not self.config.get("SIGNAL_CONTRACT_V2_ENABLED", False):
            final_analysis["analysis_schema_version"] = "v1"
            return

        confidence_raw = self._safe_float(final_analysis.get("confidence"))
        hit_rate_by_horizon: Dict[str, Dict[str, Any]] = {}
        for horizon in (1, 7, 30):
            row = self.db_manager.get_reliability_hit_rate(horizon_days=horizon, confidence_raw=confidence_raw)
            if row:
                hit_rate_by_horizon[f"{horizon}d"] = row

        contract = build_signal_contract_v2(
            analysis=final_analysis,
            agent_results=agent_results,
            diagnostics=diagnostics,
            hit_rate_by_horizon=hit_rate_by_horizon,
        )
        is_valid, errors = validate_signal_contract_v2(contract)
        if not is_valid:
            self.logger.warning(
                "Signal contract validation failed for %s: %s",
                ticker,
                "; ".join(errors),
            )

        final_analysis["signal_contract_v2"] = contract
        final_analysis["analysis_schema_version"] = "v2"
        final_analysis["ev_score_7d"] = contract.get("ev_score_7d")
        final_analysis["confidence_calibrated"] = (contract.get("confidence") or {}).get("calibrated")
        final_analysis["data_quality_score"] = ((contract.get("risk") or {}).get("data_quality_score"))
        final_analysis["regime_label"] = ((contract.get("risk") or {}).get("regime_label"))
        final_analysis["rationale_summary"] = contract.get("rationale_summary")

        # Enforce concise reasoning on outbound payloads when CoT persistence is disabled.
        if not self.config.get("COT_PERSISTENCE_ENABLED", False):
            final_analysis["reasoning"] = contract.get("rationale_summary") or final_analysis.get("summary", "")

    async def _run_validation(
        self,
        ticker: str,
        final_analysis: Dict[str, Any],
        agent_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run Phase 2.5 validation: Tier 1a (deterministic rules) + Tier 1b (council LLM)."""
        import uuid
        from datetime import datetime, timezone as tz

        # Tier 1a: deterministic rule engine (sync, always runs)
        rule_report = run_validation_rules(
            final_analysis=final_analysis,
            agent_results=agent_results,
        )

        # Tier 1b: LLM-powered council validator (async, graceful fallback)
        _empty_council = {
            "investor_validations": [],
            "total_claims_checked": 0,
            "total_contradictions": 0,
            "confidence_penalty": 0.0,
            "llm_provider": "",
            "fallback_used": True,
        }
        council_report = _empty_council
        council_results = self._extract_council_results(agent_results)
        if council_results:
            try:
                cv_agent = CouncilValidatorAgent(ticker, self.config)
                self._inject_shared_resources(cv_agent)
                cv_agent.set_council_context(council_results, agent_results)
                cv_result = await asyncio.wait_for(
                    cv_agent.execute(),
                    timeout=self.config.get("AGENT_TIMEOUT", 30),
                )
                if cv_result.get("success") and cv_result.get("data"):
                    council_report = cv_result["data"]
            except Exception as exc:
                self.logger.warning(f"Council validator failed (non-blocking): {exc}")

        # Merge penalties (combined cap 0.50)
        rule_penalty = float(rule_report.get("total_confidence_penalty", 0.0))
        council_penalty = float(council_report.get("confidence_penalty", 0.0))
        total_penalty = min(rule_penalty + council_penalty, 0.50)

        # Determine overall status
        total_contradictions = (
            rule_report.get("contradictions", 0)
            + council_report.get("total_contradictions", 0)
        )
        total_warnings = rule_report.get("warnings", 0)
        if total_contradictions > 0:
            overall_status = "contradictions"
        elif total_warnings > 0:
            overall_status = "warnings"
        else:
            overall_status = "clean"

        # Tier 2: spot-check sampling
        run_count = self._get_analysis_run_count(ticker)
        spot_check_rate = int(self.config.get("VALIDATION_SPOT_CHECK_RATE", 3))
        spot_check_on_contradiction = bool(self.config.get("VALIDATION_SPOT_CHECK_ON_CONTRADICTION", True))
        spot_check_requested = (
            (spot_check_rate > 0 and run_count % spot_check_rate == 0)
            or (spot_check_on_contradiction and overall_status == "contradictions")
        )

        original_conf = float(final_analysis.get("confidence") or 0.5)
        return {
            "schema_version": "1.0",
            "timestamp": datetime.now(tz.utc).isoformat(),
            "ticker": ticker,
            "validation_id": str(uuid.uuid4()),
            "overall_status": overall_status,
            "total_confidence_penalty": total_penalty,
            "original_confidence": original_conf,
            "adjusted_confidence": max(original_conf - total_penalty, 0.05),
            "rule_validation": rule_report,
            "council_validation": council_report,
            "spot_check_requested": spot_check_requested,
            "spot_check_status": "pending" if spot_check_requested else "skipped",
        }

    def _extract_council_results(self, agent_results: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract council investor results from agent_results if present."""
        council_data = (agent_results.get("council") or {}).get("data") or {}
        investors = council_data.get("investors") or council_data.get("results")
        if investors and isinstance(investors, list):
            return investors
        return None

    def _get_analysis_run_count(self, ticker: str) -> int:
        """Return total number of analyses for a ticker (used for spot-check sampling)."""
        try:
            history = self.db_manager.get_analysis_history(ticker, limit=9999)
            return len(history) if history else 1
        except Exception:
            return 1

    def _log_baseline_metrics(
        self,
        *,
        ticker: str,
        started_at: float,
        agent_results: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> None:
        """Emit baseline metrics used for rollout and regression tracking."""
        elapsed = max(0.0, time.time() - started_at)
        data_quality = diagnostics.get("data_quality") or {}
        success_rate = self._safe_float(data_quality.get("agent_success_rate")) or 0.0
        freshness = self._safe_float(data_quality.get("news_freshness_hours"))
        freshness_text = "n/a" if freshness is None else f"{freshness:.2f}h"
        self.logger.info(
            "baseline_metrics ticker=%s latency_s=%.3f agent_success_rate=%.3f news_freshness=%s agent_count=%d",
            ticker,
            elapsed,
            success_rate,
            freshness_text,
            len(agent_results),
        )

    def _safe_float(self, value: Any) -> Optional[float]:
        """Convert value to float when possible."""
        return safe_float(value)

    def _derive_predicted_up_probability(self, final_analysis: Dict[str, Any]) -> float:
        """Map analysis output into P(up) for calibration tracking."""
        recommendation = str(final_analysis.get("recommendation", "HOLD")).upper()

        def _fallback_for_recommendation() -> float:
            if recommendation == "BUY":
                return 0.65
            if recommendation == "SELL":
                return 0.35
            return 0.50

        scenarios = final_analysis.get("scenarios") if isinstance(final_analysis.get("scenarios"), dict) else {}
        if scenarios:
            prob_up = 0.0
            informative_scenario_found = False
            for scenario in scenarios.values():
                if not isinstance(scenario, dict):
                    continue
                probability = self._safe_float(scenario.get("probability"))
                if probability is None:
                    continue
                expected_return = self._safe_float(scenario.get("expected_return_pct"))
                if expected_return is None:
                    continue
                informative_scenario_found = True
                if expected_return > 0:
                    prob_up += probability
                elif expected_return == 0:
                    prob_up += 0.5 * probability

            if informative_scenario_found:
                return max(0.0, min(1.0, prob_up))
            return _fallback_for_recommendation()

        return _fallback_for_recommendation()

    def _extract_baseline_price(
        self,
        agent_results: Dict[str, Any],
        final_analysis: Dict[str, Any],
    ) -> Optional[float]:
        """Extract baseline price for outcome tracking from market payload or fallback targets."""
        market_data = (agent_results.get("market") or {}).get("data") or {}
        candidate_values = [
            market_data.get("current_price"),
            market_data.get("price"),
            market_data.get("close"),
            (market_data.get("price_change_1m") or {}).get("current_price"),
            (final_analysis.get("decision_card") or {}).get("entry_zone", {}).get("reference"),
            (final_analysis.get("price_targets") or {}).get("entry"),
        ]

        for value in candidate_values:
            parsed = self._safe_float(value)
            if parsed is not None and parsed > 0:
                return parsed
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

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Best-effort datetime parsing for freshness diagnostics."""
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            dt = None
            parse_attempts = [
                lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                lambda s: datetime.strptime(s, "%Y-%m-%d"),
                lambda s: datetime.strptime(s, "%Y%m%dT%H%M%S"),
            ]
            for parser in parse_attempts:
                try:
                    dt = parser(text)
                    break
                except Exception:
                    continue
            if dt is None:
                return None
        else:
            return None

        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _direction_from_market(self, market_data: Dict[str, Any]) -> str:
        """Infer directional stance from market trend."""
        regime = self._classify_market_regime(market_data.get("trend"))
        return regime if regime in {"bullish", "bearish"} else "neutral"

    def _direction_from_fundamentals(self, fundamentals_data: Dict[str, Any]) -> str:
        """Infer directional stance from fundamentals health and recommendation."""
        health_score = self._safe_float(fundamentals_data.get("health_score"))
        if health_score is not None:
            if health_score >= 60:
                return "bullish"
            if health_score <= 40:
                return "bearish"

        recommendation = str(fundamentals_data.get("recommendation", "")).lower()
        if recommendation in {"buy", "strong_buy"}:
            return "bullish"
        if recommendation in {"sell", "strong_sell"}:
            return "bearish"
        return "neutral"

    def _direction_from_technical(self, technical_data: Dict[str, Any]) -> str:
        """Infer directional stance from technical overall signal/strength."""
        signal = str((technical_data.get("signals") or {}).get("overall", "")).lower()
        if signal in {"buy", "bullish"}:
            return "bullish"
        if signal in {"sell", "bearish"}:
            return "bearish"

        strength = self._safe_float((technical_data.get("signals") or {}).get("strength"))
        if strength is not None:
            if strength >= 20:
                return "bullish"
            if strength <= -20:
                return "bearish"
        return "neutral"

    def _direction_from_macro(self, macro_data: Dict[str, Any]) -> str:
        """Infer directional stance from macro risk regime."""
        risk_env = str(macro_data.get("risk_environment", "")).lower()
        if risk_env in {"risk_on", "supportive"}:
            return "bullish"
        if risk_env in {"risk_off", "restrictive"}:
            return "bearish"

        cycle = str(macro_data.get("economic_cycle", "")).lower()
        if cycle in {"expansion", "recovery"}:
            return "bullish"
        if cycle in {"contraction", "recession"}:
            return "bearish"
        return "neutral"

    def _direction_from_options(self, options_data: Dict[str, Any]) -> str:
        """Infer directional stance from options flow signal."""
        signal = str(options_data.get("overall_signal", "")).lower()
        if signal == "bullish":
            return "bullish"
        if signal == "bearish":
            return "bearish"
        return "neutral"

    def _direction_from_sentiment(self, sentiment_data: Dict[str, Any]) -> str:
        """Infer directional stance from sentiment score."""
        score = self._safe_float(sentiment_data.get("overall_sentiment"))
        if score is None:
            return "neutral"
        if score >= 0.2:
            return "bullish"
        if score <= -0.2:
            return "bearish"
        return "neutral"

    def _build_disagreement_diagnostics(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compute agent disagreement diagnostics."""
        direction_resolvers = {
            "market": self._direction_from_market,
            "fundamentals": self._direction_from_fundamentals,
            "technical": self._direction_from_technical,
            "macro": self._direction_from_macro,
            "options": self._direction_from_options,
            "sentiment": self._direction_from_sentiment,
        }

        agent_directions: Dict[str, str] = {}
        for agent_name, resolver in direction_resolvers.items():
            result = agent_results.get(agent_name) or {}
            if not result.get("success"):
                continue
            data = result.get("data") or {}
            agent_directions[agent_name] = resolver(data)

        bullish_agents = [name for name, d in agent_directions.items() if d == "bullish"]
        bearish_agents = [name for name, d in agent_directions.items() if d == "bearish"]
        neutral_agents = [name for name, d in agent_directions.items() if d == "neutral"]

        is_conflicted = len(bullish_agents) >= 2 and len(bearish_agents) >= 2
        conflicting_agents = bullish_agents + bearish_agents if is_conflicted else []

        return {
            "agent_directions": agent_directions,
            "bullish_count": len(bullish_agents),
            "bearish_count": len(bearish_agents),
            "neutral_count": len(neutral_agents),
            "is_conflicted": is_conflicted,
            "conflicting_agents": conflicting_agents,
        }

    def _build_data_quality_diagnostics(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compute data-quality diagnostics for the current run."""
        total_agents = len(agent_results)
        if total_agents == 0:
            return {
                "agent_success_rate": 0.0,
                "failed_agents": [],
                "fallback_source_agents": [],
                "news_freshness_hours": None,
                "quality_level": "poor",
                "warnings": ["No agent results available for quality assessment."],
            }

        failed_agents = [
            agent_name
            for agent_name, result in agent_results.items()
            if not (result or {}).get("success")
        ]
        success_count = total_agents - len(failed_agents)
        success_rate = success_count / total_agents

        fallback_source_agents = []
        tavily_enabled_agents = []
        for agent_name, result in agent_results.items():
            if not (result or {}).get("success"):
                continue
            data = (result or {}).get("data") or {}
            source = str(data.get("data_source") or data.get("source") or "").lower()
            if source in {"yfinance", "none"}:
                fallback_source_agents.append({"agent": agent_name, "source": source})
            if source == "tavily" or data.get("tavily_summary") or data.get("tavily_context"):
                tavily_enabled_agents.append(agent_name)

        news_freshness_hours = None
        news_data = ((agent_results.get("news") or {}).get("data") or {})
        articles = news_data.get("articles") or []
        if isinstance(articles, list) and articles:
            parsed_times = []
            for article in articles:
                if not isinstance(article, dict):
                    continue
                published_at = (
                    article.get("published_at")
                    or article.get("publishedAt")
                    or article.get("time_published")
                )
                parsed = self._parse_datetime(published_at)
                if parsed:
                    parsed_times.append(parsed)

            if parsed_times:
                newest = max(parsed_times)
                now = datetime.now(timezone.utc)
                hours = max(0.0, (now - newest).total_seconds() / 3600.0)
                news_freshness_hours = round(hours, 2)

        critical_agents = {"news", "market", "fundamentals", "technical"}
        critical_failure_count = sum(1 for agent in failed_agents if agent in critical_agents)

        if success_rate < 0.60 or critical_failure_count >= 2:
            quality_level = "poor"
        elif success_rate >= 0.85 and not failed_agents:
            quality_level = "good"
        else:
            quality_level = "warn"

        warnings: List[str] = []
        if failed_agents:
            warnings.append(f"Failed agents: {', '.join(sorted(failed_agents))}.")
        if critical_failure_count >= 2:
            warnings.append("Multiple critical agents failed; confidence should be reduced.")
        if fallback_source_agents:
            labels = [f"{item['agent']}({item['source']})" for item in fallback_source_agents]
            warnings.append(f"Fallback data sources used: {', '.join(labels)}.")
        if news_freshness_hours is not None and news_freshness_hours > 24:
            warnings.append(f"News freshness is stale ({news_freshness_hours:.1f}h old).")
        elif news_data and news_freshness_hours is None:
            warnings.append("News freshness is unavailable due to missing publish timestamps.")

        # Track Tavily usage
        tavily_status = {
            "enabled": self.config.get("TAVILY_ENABLED", False),
            "news_enabled": self.config.get("TAVILY_NEWS_ENABLED", False),
            "context_enabled": self.config.get("TAVILY_CONTEXT_ENABLED", False),
            "agents_using": tavily_enabled_agents,
        }

        return {
            "agent_success_rate": round(success_rate, 4),
            "failed_agents": sorted(failed_agents),
            "fallback_source_agents": fallback_source_agents,
            "news_freshness_hours": news_freshness_hours,
            "quality_level": quality_level,
            "warnings": warnings,
            "tavily": tavily_status,
        }

    def _build_diagnostics(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Build combined disagreement and data-quality diagnostics."""
        disagreement = self._build_disagreement_diagnostics(agent_results)
        data_quality = self._build_data_quality_diagnostics(agent_results)
        return {
            "disagreement": disagreement,
            "data_quality": data_quality,
        }

    def _build_diagnostics_summary(self, diagnostics: Dict[str, Any]) -> str:
        """Create one-line diagnostics summary for compact displays."""
        disagreement = diagnostics.get("disagreement") or {}
        data_quality = diagnostics.get("data_quality") or {}

        bullish_count = int(disagreement.get("bullish_count", 0))
        bearish_count = int(disagreement.get("bearish_count", 0))
        if disagreement.get("is_conflicted"):
            conflict_text = f"Signals are conflicted ({bullish_count} bullish vs {bearish_count} bearish)."
        else:
            conflict_text = "Signals are broadly aligned."

        success_rate = self._safe_float(data_quality.get("agent_success_rate")) or 0.0
        quality_level = str(data_quality.get("quality_level", "warn")).lower()
        quality_text = f"Data quality: {quality_level} ({success_rate:.0%} agent success)."

        return f"{conflict_text} {quality_text}"

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

        if changes:
            summary = "; ".join(change["label"] for change in changes)
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
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if inspect.iscoroutinefunction(self.progress_callback):
                    await self.progress_callback(update)
                else:
                    self.progress_callback(update)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")

