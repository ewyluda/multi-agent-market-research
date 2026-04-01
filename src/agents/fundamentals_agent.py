"""Fundamentals agent for analyzing company financial data."""

import asyncio
import re
import aiohttp
import json
import anthropic
from openai import OpenAI
import yfinance as yf
from typing import Dict, Any, Optional, List
from .base_agent import BaseAgent
from ..tavily_client import get_tavily_client


class FundamentalsAgent(BaseAgent):
    """Agent for fetching and analyzing fundamental company data.

    Data source priority:
        1. OpenBB Platform (company overview, financials, earnings via self._data_provider)
        2. yfinance + SEC EDGAR (fallback)
    """

    # SEC EDGAR XBRL tag variants for key financial metrics
    REVENUE_TAGS = [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
    ]
    EPS_TAGS = [
        "EarningsPerShareDiluted",
        "EarningsPerShareBasic",
    ]
    NET_INCOME_TAGS = [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ]
    GROSS_PROFIT_TAGS = [
        "GrossProfit",
    ]

    # ──────────────────────────────────────────────
    # Tavily Context Integration (Phase 2)
    # ──────────────────────────────────────────────

    async def _fetch_tavily_context(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch recent company developments via Tavily AI Search.
        
        Provides context between earnings reports including:
        - Product launches and announcements
        - Management changes
        - Regulatory developments
        - Competitive positioning
        
        Args:
            company_name: Full company name
            
        Returns:
            Dict with categorized context data
        """
        if not self.config.get("TAVILY_ENABLED", True):
            return None
        
        if not self.config.get("TAVILY_CONTEXT_ENABLED", True):
            return None
        
        tavily = get_tavily_client(self.config)
        if not tavily.is_available:
            return None
        
        try:
            self.logger.info(f"Fetching Tavily context for {self.ticker}")
            
            context = await tavily.search_company_context(
                company_name=company_name,
                ticker=self.ticker,
                context_types=["earnings", "products", "leadership", "risks", "guidance"]
            )
            
            if context.get("success"):
                self.logger.info(f"Tavily context retrieved for {self.ticker}")
                return context.get("context_data", {})
            else:
                self.logger.warning(f"Tavily context failed: {context.get('error')}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Tavily context fetch failed for {self.ticker}: {e}")
            return None

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch fundamental data. Tries OpenBB data provider first, falls back to yfinance + SEC EDGAR.
        Also fetches Tavily context for recent developments (Phase 2).

        Returns:
            Dictionary with company info, financials, earnings data, SEC filings, and Tavily context
        """
        result = {"ticker": self.ticker, "source": "unknown"}

        # ── Try OpenBB data provider first ──
        data_provider = getattr(self, "_data_provider", None)
        if data_provider is not None:
            self.logger.info(f"Fetching {self.ticker} fundamentals from OpenBB data provider (primary)")

            # Fetch all OpenBB endpoints concurrently (including FMP Ultimate endpoints)
            (obb_overview, obb_financials, obb_earnings, obb_transcripts,
             obb_estimates, obb_ratios, obb_growth, obb_segments,
             obb_insider, obb_share_stats, obb_peers, obb_dcf) = await asyncio.gather(
                data_provider.get_company_overview(self.ticker),
                data_provider.get_financials(self.ticker),
                data_provider.get_earnings(self.ticker),
                data_provider.get_earnings_transcripts(self.ticker, num_quarters=2),
                data_provider.get_analyst_estimates(self.ticker),
                data_provider.get_ratios_ttm(self.ticker),
                data_provider.get_financial_growth(self.ticker),
                data_provider.get_revenue_segments(self.ticker),
                data_provider.get_insider_trading(self.ticker),
                data_provider.get_share_statistics(self.ticker),
                data_provider.get_peers(self.ticker),
                data_provider.get_dcf_valuation(self.ticker),
                return_exceptions=True,
            )

            # Handle exceptions from gather
            fetch_names = [
                ("overview", "obb_overview"), ("financials", "obb_financials"),
                ("earnings", "obb_earnings"), ("transcripts", "obb_transcripts"),
                ("estimates", "obb_estimates"), ("ratios", "obb_ratios"),
                ("growth", "obb_growth"), ("segments", "obb_segments"),
                ("insider", "obb_insider"), ("share_stats", "obb_share_stats"),
                ("peers", "obb_peers"), ("dcf", "obb_dcf"),
            ]
            all_results = [obb_overview, obb_financials, obb_earnings, obb_transcripts,
                           obb_estimates, obb_ratios, obb_growth, obb_segments,
                           obb_insider, obb_share_stats, obb_peers, obb_dcf]
            for (name, _), val in zip(fetch_names, all_results):
                if isinstance(val, Exception):
                    self.logger.warning(f"OpenBB {name} fetch raised: {val}")

            obb_overview = None if isinstance(obb_overview, Exception) else obb_overview
            obb_financials = None if isinstance(obb_financials, Exception) else obb_financials
            obb_earnings = None if isinstance(obb_earnings, Exception) else obb_earnings
            obb_transcripts = [] if isinstance(obb_transcripts, Exception) else (obb_transcripts or [])
            # Backward compat: extract first transcript
            obb_transcript = obb_transcripts[0] if obb_transcripts else None
            obb_estimates = None if isinstance(obb_estimates, Exception) else obb_estimates
            obb_ratios = None if isinstance(obb_ratios, Exception) else obb_ratios
            obb_growth = None if isinstance(obb_growth, Exception) else obb_growth
            obb_segments = None if isinstance(obb_segments, Exception) else obb_segments
            obb_insider = None if isinstance(obb_insider, Exception) else obb_insider
            obb_share_stats = None if isinstance(obb_share_stats, Exception) else obb_share_stats
            obb_peers = None if isinstance(obb_peers, Exception) else obb_peers
            obb_dcf = None if isinstance(obb_dcf, Exception) else obb_dcf

            # We need at least the overview to use OpenBB as primary
            if obb_overview:
                self.logger.info(f"OpenBB fundamentals retrieved for {self.ticker}")

                result["source"] = "openbb"

                # Map OpenBB keys to yfinance-compatible format expected by analyze()
                # Use ratios TTM as primary source for valuation metrics, fall back to overview
                r = obb_ratios or {}
                g = obb_growth or {}
                e = obb_estimates or {}

                info = {
                    "longName": obb_overview.get("longName", ""),
                    "sector": obb_overview.get("sector", ""),
                    "industry": obb_overview.get("industry", ""),
                    "marketCap": obb_overview.get("marketCap"),
                    "enterpriseValue": obb_overview.get("enterpriseValue"),
                    "trailingPE": r.get("price_to_earnings") or obb_overview.get("PE"),
                    "forwardPE": obb_overview.get("forwardPE"),
                    "pegRatio": r.get("price_earnings_to_growth") or obb_overview.get("pegRatio"),
                    "priceToBook": r.get("price_to_book") or obb_overview.get("PB"),
                    "priceToSalesTrailing12Months": r.get("price_to_sales") or obb_overview.get("priceToSalesTrailing12Months"),
                    "profitMargins": r.get("net_profit_margin") or obb_overview.get("profitMargin"),
                    "operatingMargins": r.get("operating_profit_margin") or obb_overview.get("operatingMargin"),
                    "returnOnAssets": obb_overview.get("returnOnAssets"),
                    "returnOnEquity": obb_overview.get("ROE") or obb_overview.get("returnOnEquity"),
                    "dividendYield": r.get("dividend_yield") or obb_overview.get("dividendYield"),
                    "dividendRate": obb_overview.get("dividendRate"),
                    "payoutRatio": r.get("payout_ratio") or obb_overview.get("payoutRatio"),
                    "revenueGrowth": g.get("revenue_growth") or obb_overview.get("revenueGrowth"),
                    "earningsGrowth": g.get("eps_growth") or obb_overview.get("earningsGrowth"),
                    "trailingEps": obb_overview.get("trailingEps"),
                    "forwardEps": obb_overview.get("forwardEps"),
                    # Analyst consensus targets (FMP Ultimate)
                    "targetHighPrice": e.get("target_high") or obb_overview.get("targetHighPrice"),
                    "targetLowPrice": e.get("target_low") or obb_overview.get("targetLowPrice"),
                    "targetMeanPrice": e.get("target_consensus") or obb_overview.get("targetMeanPrice"),
                    "targetMedianPrice": e.get("target_median") or obb_overview.get("targetMedianPrice"),
                    "recommendationKey": obb_overview.get("recommendationKey"),
                    "numberOfAnalystOpinions": obb_overview.get("numberOfAnalystOpinions"),
                    "beta": obb_overview.get("beta"),
                    "debtToEquity": r.get("debt_to_equity") or obb_overview.get("debtToEquity"),
                    # Ratios TTM fills these gaps
                    "currentRatio": r.get("current_ratio"),
                    "quickRatio": r.get("quick_ratio"),
                    "freeCashflow": None,
                    "operatingCashflow": None,
                    # Additional ratios from FMP Ultimate
                    "priceToFreeCashFlow": r.get("price_to_free_cash_flow"),
                    "enterpriseValueMultiple": r.get("enterprise_value_multiple"),
                    "grossMargins": r.get("gross_profit_margin"),
                    "ebitdaMargin": r.get("ebitda_margin"),
                    "freeCashFlowPerShare": r.get("free_cash_flow_per_share"),
                    "revenuePerShare": r.get("revenue_per_share"),
                }

                # Merge financial ratios from financials data if available
                if obb_financials:
                    # Fallback: compute current ratio from balance sheet if ratios TTM didn't provide it
                    if info["currentRatio"] is None:
                        balance_records = obb_financials.get("balance_sheet", [])
                        if balance_records:
                            latest_bs = balance_records[0]
                            total_current_assets = latest_bs.get("total_current_assets")
                            total_current_liabilities = latest_bs.get("total_current_liabilities")
                            if total_current_assets and total_current_liabilities and total_current_liabilities != 0:
                                info["currentRatio"] = total_current_assets / total_current_liabilities

                    # Extract cash flow metrics from latest records (TTM from last 4 quarters)
                    cf_records = obb_financials.get("cash_flow", [])
                    if cf_records:
                        operating_cf_ttm = 0
                        capex_ttm = 0
                        quarters_counted = 0
                        for cf in cf_records[:4]:
                            ocf = cf.get("operating_cash_flow") or cf.get("net_cash_from_operating_activities")
                            capex = cf.get("capital_expenditure") or cf.get("capital_expenditures")
                            if ocf is not None:
                                try:
                                    operating_cf_ttm += float(ocf)
                                    quarters_counted += 1
                                except (ValueError, TypeError):
                                    pass
                            if capex is not None:
                                try:
                                    capex_ttm += float(capex)
                                except (ValueError, TypeError):
                                    pass
                        if quarters_counted > 0:
                            info["operatingCashflow"] = operating_cf_ttm
                            info["freeCashflow"] = operating_cf_ttm - abs(capex_ttm)

                result["info"] = info

                # Build earnings data compatible with existing analyze() method
                result["earnings_dates"] = []
                result["earnings_dates_df"] = None
                result["quarterly_earnings"] = []

                if obb_earnings:
                    eps_history = obb_earnings.get("eps_history", [])
                    if eps_history:
                        import pandas as pd
                        earnings_records = []
                        for record in eps_history:
                            reported = record.get("actual_eps") or record.get("eps_actual")
                            estimated = record.get("estimated_eps") or record.get("eps_estimated")
                            earnings_records.append({
                                "Reported EPS": reported,
                                "EPS Estimate": estimated,
                            })
                        if earnings_records:
                            result["earnings_dates_df"] = pd.DataFrame(earnings_records)
                            result["earnings_dates"] = earnings_records

                        # Build quarterly_earnings-compatible records
                        for record in eps_history:
                            reported = record.get("actual_eps") or record.get("eps_actual")
                            revenue = record.get("revenue") or record.get("revenue_actual")
                            fiscal_date = record.get("date") or record.get("fiscal_date_ending", "")
                            result["quarterly_earnings"].append({
                                "Earnings": reported,
                                "Revenue": revenue,
                                "fiscalDateEnding": str(fiscal_date),
                            })

                # Store income statement records for revenue trend analysis
                if obb_financials:
                    income_records = obb_financials.get("income_statement", [])
                    if income_records:
                        # Map to the format analyze() expects for av_income_statement
                        parsed_income = []
                        for record in income_records[:8]:
                            parsed_income.append({
                                "fiscalDateEnding": str(record.get("date") or record.get("period_ending", "")),
                                "totalRevenue": record.get("revenue") or record.get("total_revenue"),
                                "grossProfit": record.get("gross_profit"),
                                "operatingIncome": record.get("operating_income"),
                                "netIncome": record.get("net_income"),
                                "ebitda": record.get("ebitda"),
                            })
                        result["av_income_statement"] = parsed_income if parsed_income else None
                    else:
                        result["av_income_statement"] = None
                else:
                    result["av_income_statement"] = None

                # Skip SEC EDGAR when OpenBB provides data
                result["sec_data"] = None

                # Store earnings call transcripts (multi-quarter)
                if obb_transcript:
                    result["earnings_transcript"] = obb_transcript  # backward compat
                    self.logger.info(f"Earnings transcript retrieved for {self.ticker} (Q{obb_transcript.get('quarter')} {obb_transcript.get('year')})")
                if len(obb_transcripts) > 1:
                    result["prev_quarter_transcript"] = obb_transcripts[1]
                    self.logger.info(f"Previous quarter transcript also retrieved for {self.ticker}")

                # ── FMP Ultimate enrichment data ──

                # Revenue segmentation (product + geographic)
                if obb_segments:
                    result["revenue_segments"] = obb_segments

                # Financial growth rates
                if obb_growth:
                    result["financial_growth"] = obb_growth

                # DCF valuation
                if obb_dcf:
                    result["dcf_valuation"] = obb_dcf

                # Insider trading summary (most recent 10)
                if obb_insider:
                    result["insider_trading"] = obb_insider[:10]

                # Share float statistics
                if obb_share_stats:
                    result["share_statistics"] = obb_share_stats

                # Peer companies
                if obb_peers:
                    result["peers"] = obb_peers

                # Fetch Tavily context asynchronously (don't block)
                company_name = info.get("longName", "")
                tavily_task = asyncio.create_task(self._fetch_tavily_context(company_name))
                tavily_context = await tavily_task
                if tavily_context:
                    result["tavily_context"] = tavily_context

                return result
            else:
                self.logger.info(f"OpenBB overview incomplete for {self.ticker}, falling back to yfinance + SEC EDGAR")

        # ── Fallback to yfinance + SEC EDGAR ──
        self.logger.info(f"Fetching {self.ticker} fundamentals from yfinance + SEC EDGAR (fallback)")
        result["source"] = "yfinance"

        ticker_obj = yf.Ticker(self.ticker)

        # Fetch each yfinance data source independently with retries
        info = await self._retry_fetch(
            lambda: ticker_obj.info, label=f"{self.ticker} info"
        )
        result["info"] = info or {}

        earnings_dates_raw = await self._retry_fetch(
            lambda: ticker_obj.earnings_dates, label=f"{self.ticker} earnings_dates"
        )
        if earnings_dates_raw is not None and not earnings_dates_raw.empty:
            result["earnings_dates"] = earnings_dates_raw.head(10).to_dict('records')
            result["earnings_dates_df"] = earnings_dates_raw.head(10)
        else:
            result["earnings_dates"] = []
            result["earnings_dates_df"] = None

        quarterly_earnings_raw = await self._retry_fetch(
            lambda: ticker_obj.quarterly_earnings, label=f"{self.ticker} quarterly_earnings"
        )
        if quarterly_earnings_raw is not None and not quarterly_earnings_raw.empty:
            result["quarterly_earnings"] = quarterly_earnings_raw.head(8).to_dict('records')
        else:
            result["quarterly_earnings"] = []

        # Fetch SEC EDGAR data (async, separate from yfinance)
        try:
            sec_data = await self._fetch_sec_data(self.ticker)
            result["sec_data"] = sec_data
        except Exception as e:
            self.logger.warning(f"SEC EDGAR fetch failed for {self.ticker}: {e}")
            result["sec_data"] = None

        # Fetch Tavily context
        company_name = (info or {}).get("longName", "")
        if company_name:
            tavily_context = await self._fetch_tavily_context(company_name)
            if tavily_context:
                result["tavily_context"] = tavily_context

        # Only raise if we got absolutely nothing useful
        if (not result["info"]
            and not result["earnings_dates"]
            and not result["quarterly_earnings"]
            and result["sec_data"] is None):
            raise Exception(f"Failed to fetch any fundamentals data for {self.ticker}")

        return result

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze fundamental data and extract key metrics.

        Args:
            raw_data: Raw data from yfinance and SEC EDGAR

        Returns:
            Analyzed fundamental metrics
        """
        info = raw_data.get("info", {})
        earnings_dates = raw_data.get("earnings_dates", [])
        earnings_dates_df = raw_data.get("earnings_dates_df")
        quarterly_earnings = raw_data.get("quarterly_earnings", [])
        sec_data = raw_data.get("sec_data")

        # Extract key fundamental metrics
        analysis = {
            "company_name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),

            # Valuation metrics
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),

            # Profitability metrics
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "return_on_assets": info.get("returnOnAssets"),
            "return_on_equity": info.get("returnOnEquity"),

            # Dividend metrics
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),

            # Growth metrics
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),

            # Earnings data
            "earnings_per_share": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),

            # Analyst recommendations
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "recommendation": info.get("recommendationKey"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),

            # Recent earnings (with real beat/miss calculation)
            "recent_earnings": self._analyze_earnings(quarterly_earnings, earnings_dates_df),

            # Company health
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "quick_ratio": info.get("quickRatio"),

            # Cash flow
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
        }

        # Parse and add SEC EDGAR data if available
        if sec_data:
            sec_financials = self._parse_sec_financials(sec_data)
            analysis["sec_financials"] = sec_financials

            # Add EPS and revenue trend analysis from SEC data
            eps_history = sec_financials.get("eps_history", [])
            revenue_history = sec_financials.get("revenue_history", [])

            if eps_history:
                analysis["eps_trend"] = self._analyze_eps_trend(eps_history)
            if revenue_history:
                analysis["revenue_trend"] = self._analyze_revenue_trend(revenue_history)

        # Parse income statement for revenue trends (when OpenBB or AV is primary)
        av_income = raw_data.get("av_income_statement")
        if av_income and not analysis.get("revenue_trend"):
            revenue_history = []
            for report in av_income:
                rev = report.get("totalRevenue")
                if rev is not None:
                    revenue_history.append({
                        "val": rev,
                        "end": report.get("fiscalDateEnding", ""),
                        "form": "AV",
                    })
            if len(revenue_history) >= 2:
                analysis["revenue_trend"] = self._analyze_revenue_trend(revenue_history)

        # Add earnings call transcript with structured extraction
        earnings_transcript = raw_data.get("earnings_transcript")
        if earnings_transcript:
            analysis["earnings_transcript"] = {
                "quarter": earnings_transcript.get("quarter"),
                "year": earnings_transcript.get("year"),
                "date": earnings_transcript.get("date", ""),
                "content": earnings_transcript.get("content", ""),
            }
            # Extract structured metrics from transcript
            analysis["transcript_metrics"] = self._extract_transcript_metrics(
                earnings_transcript.get("content", "")
            )

        # Previous quarter transcript metrics
        prev_transcript = raw_data.get("prev_quarter_transcript")
        if prev_transcript:
            analysis["prev_quarter_transcript_metrics"] = self._extract_transcript_metrics(
                prev_transcript.get("content", "")
            )
            analysis["prev_quarter_transcript"] = {
                "quarter": prev_transcript.get("quarter"),
                "year": prev_transcript.get("year"),
                "date": prev_transcript.get("date", ""),
            }

        # Add Tavily context (recent developments between earnings)
        tavily_context = raw_data.get("tavily_context")
        if tavily_context:
            analysis["tavily_context"] = self._parse_tavily_context(tavily_context)

        # ── FMP Ultimate enrichment ──

        # Revenue segmentation
        if raw_data.get("revenue_segments"):
            analysis["revenue_segments"] = raw_data["revenue_segments"]

        # Financial growth rates
        if raw_data.get("financial_growth"):
            analysis["financial_growth"] = raw_data["financial_growth"]

        # DCF valuation
        if raw_data.get("dcf_valuation"):
            analysis["dcf_valuation"] = raw_data["dcf_valuation"]

        # Insider trading activity
        if raw_data.get("insider_trading"):
            analysis["insider_trading"] = raw_data["insider_trading"]

        # Share statistics
        if raw_data.get("share_statistics"):
            analysis["share_statistics"] = raw_data["share_statistics"]

        # Peer companies
        if raw_data.get("peers"):
            analysis["peers"] = raw_data["peers"]

        # Additional valuation/margin fields from ratios
        analysis["price_to_free_cash_flow"] = info.get("priceToFreeCashFlow")
        analysis["enterprise_value_multiple"] = info.get("enterpriseValueMultiple")
        analysis["gross_margins"] = info.get("grossMargins")
        analysis["ebitda_margin"] = info.get("ebitdaMargin")

        # Track data source
        analysis["data_source"] = raw_data.get("source", "unknown")

        # Calculate health score
        analysis["health_score"] = self._calculate_health_score(analysis)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        # Run LLM-powered equity research analysis
        equity_research = await self._run_equity_research_llm(analysis)
        if equity_research:
            # ── Guardrails: cross-check LLM claims against input metrics ──
            from ..llm_guardrails import validate_equity_research
            equity_research, er_warnings = validate_equity_research(equity_research, analysis)
            if er_warnings:
                analysis["equity_research_warnings"] = er_warnings
                for w in er_warnings:
                    self.logger.warning(f"Equity research guardrail: {w}")

            analysis["equity_research_report"] = equity_research
            llm_summary = equity_research.get("executive_summary", "")
            if llm_summary:
                analysis["llm_summary"] = llm_summary
        else:
            analysis["equity_research_report"] = None
            analysis["llm_summary"] = None

        return analysis

    def _analyze_earnings(self, quarterly_earnings: list, earnings_dates_df=None) -> Dict[str, Any]:
        """
        Analyze recent earnings performance using actual reported vs estimated EPS.

        Args:
            quarterly_earnings: List of quarterly earnings data
            earnings_dates_df: DataFrame with Reported EPS and EPS Estimate columns

        Returns:
            Earnings analysis with real beat/miss counts
        """
        beats = 0
        misses = 0
        meets = 0
        total = 0

        # Try to use earnings_dates_df for beat/miss calculation (has Reported EPS and EPS Estimate)
        if earnings_dates_df is not None and not earnings_dates_df.empty:
            try:
                for _, row in earnings_dates_df.iterrows():
                    reported = row.get("Reported EPS")
                    estimated = row.get("EPS Estimate")

                    # Skip rows where either value is missing/NaN
                    if reported is None or estimated is None:
                        continue
                    try:
                        reported = float(reported)
                        estimated = float(estimated)
                    except (ValueError, TypeError):
                        continue

                    # Skip NaN values
                    if reported != reported or estimated != estimated:
                        continue

                    total += 1
                    if reported > estimated:
                        beats += 1
                    elif reported < estimated:
                        misses += 1
                    else:
                        meets += 1
            except Exception as e:
                self.logger.warning(f"Error parsing earnings_dates for beat/miss: {e}")

        # Determine earnings trend from quarterly data
        trend = "unknown"
        if quarterly_earnings and len(quarterly_earnings) >= 2:
            try:
                # Check if earnings are improving or declining
                recent_earnings = []
                for q in quarterly_earnings[:4]:
                    # quarterly_earnings records may have 'Earnings' or 'Revenue' keys
                    earnings_val = q.get("Earnings") or q.get("earnings")
                    if earnings_val is not None:
                        try:
                            recent_earnings.append(float(earnings_val))
                        except (ValueError, TypeError):
                            pass

                if len(recent_earnings) >= 2:
                    if recent_earnings[0] > recent_earnings[1]:
                        trend = "improving"
                    elif recent_earnings[0] < recent_earnings[1]:
                        trend = "declining"
                    else:
                        trend = "stable"
            except Exception as e:
                self.logger.warning(f"Error analyzing earnings trend: {e}")

        beat_rate = (beats / total * 100) if total > 0 else 0.0

        return {
            "beats": beats,
            "misses": misses,
            "meets": meets,
            "total": total,
            "beat_rate": beat_rate,
            "recent_quarters": quarterly_earnings[:4] if quarterly_earnings else [],
            "trend": trend
        }

    # ──────────────────────────────────────────────
    # SEC EDGAR Integration
    # ──────────────────────────────────────────────

    async def _get_cik_for_ticker(self, ticker: str) -> Optional[str]:
        """
        Convert ticker symbol to SEC CIK number.

        Args:
            ticker: Stock ticker symbol

        Returns:
            10-digit zero-padded CIK string, or None if not found
        """
        url = "https://www.sec.gov/files/company_tickers.json"
        user_agent = self.config.get("SEC_EDGAR_USER_AGENT", "MarketResearch/1.0 (research@example.com)")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": user_agent}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        self.logger.warning(f"SEC ticker mapping returned status {resp.status}")
                        return None
                    data = await resp.json(content_type=None)

            # data is a dict with numeric keys, each value has ticker, cik_str, title
            ticker_upper = ticker.upper()
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker_upper:
                    cik = str(entry["cik_str"])
                    return cik.zfill(10)  # Zero-pad to 10 digits

            self.logger.warning(f"Ticker {ticker} not found in SEC mapping")
            return None

        except Exception as e:
            self.logger.warning(f"Failed to get CIK for {ticker}: {e}")
            return None

    async def _fetch_sec_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company facts from SEC EDGAR XBRL API.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Company facts dictionary or None
        """
        cik = await self._get_cik_for_ticker(ticker)
        if not cik:
            return None

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        user_agent = self.config.get("SEC_EDGAR_USER_AGENT", "MarketResearch/1.0 (research@example.com)")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": user_agent}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        self.logger.warning(f"SEC EDGAR company facts returned status {resp.status}")
                        return None
                    data = await resp.json(content_type=None)
                    return data

        except Exception as e:
            self.logger.warning(f"Failed to fetch SEC data for {ticker} (CIK {cik}): {e}")
            return None

    def _parse_sec_financials(self, company_facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key financial metrics from SEC EDGAR XBRL company facts.

        Args:
            company_facts: Raw company facts from SEC EDGAR

        Returns:
            Parsed financial metrics with history
        """
        facts = company_facts.get("facts", {})
        us_gaap = facts.get("us-gaap", {})

        result = {
            "eps_history": [],
            "revenue_history": [],
            "net_income_history": [],
            "gross_profit_history": [],
        }

        # Extract each metric using tag variants
        result["eps_history"] = self._extract_metric(us_gaap, self.EPS_TAGS, quarterly_only=True)
        result["revenue_history"] = self._extract_metric(us_gaap, self.REVENUE_TAGS, quarterly_only=True)
        result["net_income_history"] = self._extract_metric(us_gaap, self.NET_INCOME_TAGS, quarterly_only=True)
        result["gross_profit_history"] = self._extract_metric(us_gaap, self.GROSS_PROFIT_TAGS, quarterly_only=True)

        # Add latest values for easy access
        if result["eps_history"]:
            result["latest_eps"] = result["eps_history"][0]["val"]
        if result["revenue_history"]:
            result["latest_revenue"] = result["revenue_history"][0]["val"]
        if result["net_income_history"]:
            result["latest_net_income"] = result["net_income_history"][0]["val"]

        return result

    def _extract_metric(self, us_gaap: Dict, tag_variants: List[str], quarterly_only: bool = True, limit: int = 8) -> List[Dict]:
        """
        Extract a financial metric from XBRL data, trying multiple tag variants.
        Picks the tag variant with the most recent data point.

        Args:
            us_gaap: The us-gaap section of company facts
            tag_variants: List of XBRL tag names to try
            quarterly_only: If True, filter for 10-Q filings only
            limit: Max number of data points to return

        Returns:
            List of dicts with 'val', 'end', 'form' keys, sorted newest first
        """
        best_result = []
        best_newest_date = ""

        for tag in tag_variants:
            tag_data = us_gaap.get(tag)
            if not tag_data:
                continue

            units = tag_data.get("units", {})
            # EPS uses USD/shares, revenue uses USD
            values = units.get("USD/shares") or units.get("USD") or []
            if not values:
                continue

            # Filter for 10-Q (quarterly) or 10-K (annual) filings
            filtered = []
            for v in values:
                form = v.get("form", "")
                if quarterly_only and form not in ("10-Q", "10-K"):
                    continue
                filtered.append({
                    "val": v.get("val"),
                    "end": v.get("end", ""),
                    "form": form,
                    "filed": v.get("filed", ""),
                })

            if not filtered:
                continue

            # Sort by end date descending (most recent first)
            filtered.sort(key=lambda x: x["end"], reverse=True)

            # Deduplicate by end date (keep first occurrence = most recent filing)
            seen_dates = set()
            deduped = []
            for item in filtered:
                if item["end"] not in seen_dates:
                    seen_dates.add(item["end"])
                    deduped.append(item)

            # Pick the tag with the most recent data
            if deduped and deduped[0]["end"] > best_newest_date:
                best_newest_date = deduped[0]["end"]
                best_result = deduped[:limit]

        return best_result

    def _analyze_eps_trend(self, eps_history: List[Dict]) -> Dict[str, Any]:
        """
        Analyze EPS trend from SEC EDGAR data.

        Args:
            eps_history: List of EPS data points (newest first)

        Returns:
            EPS trend analysis
        """
        if not eps_history or len(eps_history) < 2:
            return {"trend": "insufficient_data"}

        latest = eps_history[0]["val"]
        previous = eps_history[1]["val"]

        # QoQ change
        qoq_change = None
        qoq_pct = None
        if latest is not None and previous is not None and previous != 0:
            qoq_change = latest - previous
            qoq_pct = (qoq_change / abs(previous)) * 100

        # YoY change (compare to 4 quarters ago if available)
        yoy_change = None
        yoy_pct = None
        if len(eps_history) >= 5:
            year_ago = eps_history[4]["val"]
            if latest is not None and year_ago is not None and year_ago != 0:
                yoy_change = latest - year_ago
                yoy_pct = (yoy_change / abs(year_ago)) * 100

        # Determine trend direction
        trend = "stable"
        if qoq_pct is not None:
            if qoq_pct > 5:
                trend = "improving"
            elif qoq_pct < -5:
                trend = "declining"

        return {
            "trend": trend,
            "latest_eps": latest,
            "previous_eps": previous,
            "qoq_change": round(qoq_change, 4) if qoq_change is not None else None,
            "qoq_pct": round(qoq_pct, 2) if qoq_pct is not None else None,
            "yoy_change": round(yoy_change, 4) if yoy_change is not None else None,
            "yoy_pct": round(yoy_pct, 2) if yoy_pct is not None else None,
            "latest_date": eps_history[0].get("end"),
            "data_points": len(eps_history),
        }

    def _analyze_revenue_trend(self, revenue_history: List[Dict]) -> Dict[str, Any]:
        """
        Analyze revenue trend from SEC EDGAR data.

        Args:
            revenue_history: List of revenue data points (newest first)

        Returns:
            Revenue trend analysis
        """
        if not revenue_history or len(revenue_history) < 2:
            return {"trend": "insufficient_data"}

        latest = revenue_history[0]["val"]
        previous = revenue_history[1]["val"]

        # QoQ change
        qoq_change = None
        qoq_pct = None
        if latest is not None and previous is not None and previous != 0:
            qoq_change = latest - previous
            qoq_pct = (qoq_change / abs(previous)) * 100

        # YoY change
        yoy_change = None
        yoy_pct = None
        if len(revenue_history) >= 5:
            year_ago = revenue_history[4]["val"]
            if latest is not None and year_ago is not None and year_ago != 0:
                yoy_change = latest - year_ago
                yoy_pct = (yoy_change / abs(year_ago)) * 100

        # Determine trend direction
        trend = "stable"
        if qoq_pct is not None:
            if qoq_pct > 3:
                trend = "growing"
            elif qoq_pct < -3:
                trend = "declining"

        return {
            "trend": trend,
            "latest_revenue": latest,
            "previous_revenue": previous,
            "qoq_change": round(qoq_change, 2) if qoq_change is not None else None,
            "qoq_pct": round(qoq_pct, 2) if qoq_pct is not None else None,
            "yoy_change": round(yoy_change, 2) if yoy_change is not None else None,
            "yoy_pct": round(yoy_pct, 2) if yoy_pct is not None else None,
            "latest_date": revenue_history[0].get("end"),
            "data_points": len(revenue_history),
        }

    @staticmethod
    def _extract_transcript_metrics(content: str) -> Dict[str, Any]:
        """Extract structured guidance metrics from earnings call transcript text.

        Uses regex patterns to find revenue guidance, EPS guidance, growth targets,
        and capex outlook. These serve as factual anchors for LLM analysis.

        Returns:
            Dict with extracted metrics (empty sub-dicts if not found).
        """
        metrics: Dict[str, Any] = {}
        if not content:
            return metrics

        text = content.lower()

        # Revenue guidance: "revenue of $X billion", "$X to $Y billion in revenue"
        # Pattern 1: "revenue ... $X billion" (non-greedy to capture first dollar amount)
        rev_match = re.search(
            r'(?:revenue|sales).{0,30}?\$(\d+(?:\.\d+)?)\s*(billion|million|b|m)'
            r'(?:\s*(?:to|[-–])\s*\$(\d+(?:\.\d+)?)\s*(billion|million|b|m))?',
            text, re.IGNORECASE,
        )
        # Pattern 2: "$X billion ... revenue" (dollar amount before the word revenue)
        if not rev_match:
            rev_match = re.search(
                r'\$(\d+(?:\.\d+)?)\s*(billion|million|b|m)'
                r'(?:\s*(?:to|[-–])\s*\$(\d+(?:\.\d+)?)\s*(billion|million|b|m))?'
                r'.{0,40}?(?:revenue|sales)',
                text, re.IGNORECASE,
            )
        if rev_match:
            low = float(rev_match.group(1))
            unit = rev_match.group(2).lower()
            if unit in ("b", "billion"):
                unit = "billion"
            else:
                unit = "million"
            guidance = {"low": low, "unit": unit}
            if rev_match.group(3):
                guidance["high"] = float(rev_match.group(3))
            metrics["revenue_guidance"] = guidance

        # EPS guidance: "EPS of $X.XX", "earnings per share of $X.XX to $Y.YY"
        eps_pattern = re.compile(
            r'(?:eps|earnings per share)\s*(?:of|at|around|approximately|to be)?\s*'
            r'\$(\d+\.\d+)(?:\s*(?:to|[-–])\s*\$(\d+\.\d+))?',
            re.IGNORECASE,
        )
        eps_match = eps_pattern.search(text)
        if eps_match:
            guidance = {"low": float(eps_match.group(1))}
            if eps_match.group(2):
                guidance["high"] = float(eps_match.group(2))
            metrics["eps_guidance"] = guidance

        # Growth targets: "X% growth", "grew X%", "expect X% to Y% growth"
        growth_pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*%?\s*(?:to\s*(\d+(?:\.\d+)?)\s*%?\s*)?'
            r'(?:growth|grew|increase|year.over.year)',
            re.IGNORECASE,
        )
        growth_matches = growth_pattern.findall(text)
        if growth_matches:
            targets = []
            for match in growth_matches[:5]:  # cap at 5
                val = float(match[0])
                if 0.5 <= val <= 100:  # filter noise (very small or >100% unlikely guidance)
                    entry = {"value": val}
                    if match[1]:
                        entry["high"] = float(match[1])
                    targets.append(entry)
            if targets:
                metrics["growth_targets"] = targets

        # Capex outlook: "capital expenditure of $X billion", "capex of $X million"
        capex_pattern = re.compile(
            r'(?:capital expenditure|capex|cap\s*ex)\s*(?:of|at|around|approximately)?\s*'
            r'\$(\d+(?:\.\d+)?)\s*(billion|million|b|m)',
            re.IGNORECASE,
        )
        capex_match = capex_pattern.search(text)
        if capex_match:
            val = float(capex_match.group(1))
            unit = capex_match.group(2).lower()
            metrics["capex"] = {"value": val, "unit": "billion" if unit in ("b", "billion") else "million"}

        return metrics

    def _parse_tavily_context(self, tavily_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Tavily context into structured format for analysis.

        Args:
            tavily_context: Raw context data from Tavily
            
        Returns:
            Structured context with highlights
        """
        parsed = {
            "has_context": False,
            "earnings_highlights": [],
            "product_news": [],
            "leadership_changes": [],
            "risk_factors": [],
            "guidance_updates": [],
            "ai_summaries": {}
        }
        
        if not tavily_context:
            return parsed
        
        parsed["has_context"] = True
        
        # Parse each context type
        for ctx_type, data in tavily_context.items():
            if not isinstance(data, dict) or not data.get("success"):
                continue
            
            items = data.get("items", [])
            ai_summary = data.get("ai_summary")
            
            if ctx_type == "earnings" and items:
                parsed["earnings_highlights"] = [
                    {"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("url")}
                    for i in items[:3]
                ]
                if ai_summary:
                    parsed["ai_summaries"]["earnings"] = ai_summary
                    
            elif ctx_type == "products" and items:
                parsed["product_news"] = [
                    {"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("url")}
                    for i in items[:3]
                ]
                if ai_summary:
                    parsed["ai_summaries"]["products"] = ai_summary
                    
            elif ctx_type == "leadership" and items:
                parsed["leadership_changes"] = [
                    {"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("url")}
                    for i in items[:3]
                ]
                if ai_summary:
                    parsed["ai_summaries"]["leadership"] = ai_summary
                    
            elif ctx_type == "risks" and items:
                parsed["risk_factors"] = [
                    {"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("url")}
                    for i in items[:3]
                ]
                if ai_summary:
                    parsed["ai_summaries"]["risks"] = ai_summary
                    
            elif ctx_type == "guidance" and items:
                parsed["guidance_updates"] = [
                    {"title": i.get("title"), "snippet": i.get("snippet"), "url": i.get("url")}
                    for i in items[:3]
                ]
                if ai_summary:
                    parsed["ai_summaries"]["guidance"] = ai_summary
        
        return parsed

    # ──────────────────────────────────────────────
    # Health Score & Summary
    # ──────────────────────────────────────────────

    def _calculate_health_score(self, analysis: Dict[str, Any]) -> float:
        """
        Calculate overall company health score (0-100).

        Args:
            analysis: Fundamental analysis data

        Returns:
            Health score
        """
        score = 50.0  # Start neutral

        # Adjust based on P/E ratio
        pe = analysis.get("pe_ratio")
        if pe:
            if 10 < pe < 25:
                score += 10
            elif pe > 50:
                score -= 10

        # Adjust based on profit margins
        margins = analysis.get("profit_margins")
        if margins:
            if margins > 0.20:
                score += 15
            elif margins > 0.10:
                score += 10
            elif margins < 0:
                score -= 20

        # Adjust based on debt to equity
        debt_to_equity = analysis.get("debt_to_equity")
        if debt_to_equity:
            if debt_to_equity < 0.5:
                score += 10
            elif debt_to_equity > 2.0:
                score -= 10

        # Adjust based on dividend yield
        div_yield = analysis.get("dividend_yield")
        if div_yield and div_yield > 0.02:
            score += 5

        # Adjust based on ROE
        roe = analysis.get("return_on_equity")
        if roe:
            if roe > 0.15:
                score += 10
            elif roe < 0:
                score -= 15

        # Adjust based on earnings beat rate (from real data)
        recent_earnings = analysis.get("recent_earnings", {})
        beat_rate = recent_earnings.get("beat_rate", 0)
        if beat_rate >= 75:
            score += 10
        elif beat_rate >= 50:
            score += 5
        elif recent_earnings.get("total", 0) > 0 and beat_rate < 25:
            score -= 10

        # Cap score between 0 and 100
        return max(0, min(100, score))

    def _generate_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generate textual summary of fundamentals.

        Args:
            analysis: Fundamental analysis data

        Returns:
            Summary string
        """
        company = analysis.get("company_name", self.ticker)
        sector = analysis.get("sector", "Unknown")
        pe = analysis.get("pe_ratio", "N/A")
        margins = analysis.get("profit_margins")
        margins_pct = f"{margins * 100:.1f}%" if margins else "N/A"
        health = analysis.get("health_score", 0)

        summary = f"{company} operates in the {sector} sector. "
        summary += f"P/E ratio: {pe if pe != 'N/A' else 'N/A'}, "
        summary += f"Profit margins: {margins_pct}. "
        summary += f"Overall health score: {health:.0f}/100."

        # Add earnings beat rate if available
        recent_earnings = analysis.get("recent_earnings", {})
        if recent_earnings.get("total", 0) > 0:
            summary += f" Earnings beat rate: {recent_earnings['beat_rate']:.0f}% ({recent_earnings['beats']}/{recent_earnings['total']})."

        # Add SEC EPS trend if available
        eps_trend = analysis.get("eps_trend", {})
        if eps_trend.get("trend") and eps_trend["trend"] != "insufficient_data":
            summary += f" EPS trend: {eps_trend['trend']}."

        return summary

    # ──────────────────────────────────────────────
    # LLM-Powered Equity Research Analysis
    # ──────────────────────────────────────────────

    def _build_llm_context(self, analysis: Dict[str, Any]) -> str:
        """
        Build a formatted context string from computed fundamentals
        metrics for the LLM prompt.

        Args:
            analysis: The computed fundamentals analysis dict

        Returns:
            Formatted string with all available metrics
        """
        sections = []

        def _fmt(val):
            return "N/A" if val is None else str(val)

        def _fmt_money(val):
            return "N/A" if val is None else f"${val:,.0f}"

        def _fmt_pct(val, decimals=1):
            return "N/A" if val is None else f"{val * 100:.{decimals}f}%"

        def _fmt_pct_value(val, decimals=2):
            return "N/A" if val is None else f"{val:.{decimals}f}%"

        # Company overview
        sections.append(f"Company: {analysis.get('company_name', 'N/A')}")
        sections.append(f"Ticker: {self.ticker}")
        sections.append(f"Sector: {analysis.get('sector', 'N/A')}")
        sections.append(f"Industry: {analysis.get('industry', 'N/A')}")
        mc = analysis.get('market_cap')
        sections.append(f"Market Cap: {_fmt_money(mc)}")

        # Valuation
        sections.append("\n--- VALUATION ---")
        sections.append(f"P/E Ratio (TTM): {_fmt(analysis.get('pe_ratio'))}")
        sections.append(f"Forward P/E: {_fmt(analysis.get('forward_pe'))}")
        sections.append(f"PEG Ratio: {_fmt(analysis.get('peg_ratio'))}")
        sections.append(f"Price/Book: {_fmt(analysis.get('price_to_book'))}")
        sections.append(f"Price/Sales: {_fmt(analysis.get('price_to_sales'))}")
        ev = analysis.get('enterprise_value')
        sections.append(f"Enterprise Value: {_fmt_money(ev)}")

        # Profitability
        sections.append("\n--- PROFITABILITY ---")
        pm = analysis.get('profit_margins')
        sections.append(f"Profit Margins: {_fmt_pct(pm, 1)}")
        om = analysis.get('operating_margins')
        sections.append(f"Operating Margins: {_fmt_pct(om, 1)}")
        roa = analysis.get('return_on_assets')
        sections.append(f"ROA: {_fmt_pct(roa, 1)}")
        roe = analysis.get('return_on_equity')
        sections.append(f"ROE: {_fmt_pct(roe, 1)}")

        # Cash Flow
        sections.append("\n--- CASH FLOW ---")
        fcf = analysis.get('free_cash_flow')
        sections.append(f"Free Cash Flow: {_fmt_money(fcf)}")
        ocf = analysis.get('operating_cash_flow')
        sections.append(f"Operating Cash Flow: {_fmt_money(ocf)}")

        # Balance Sheet Health
        sections.append("\n--- BALANCE SHEET ---")
        sections.append(f"Current Ratio: {_fmt(analysis.get('current_ratio'))}")
        sections.append(f"Debt/Equity: {_fmt(analysis.get('debt_to_equity'))}")
        sections.append(f"Quick Ratio: {_fmt(analysis.get('quick_ratio'))}")

        # Growth
        sections.append("\n--- GROWTH ---")
        rg = analysis.get('revenue_growth')
        sections.append(f"Revenue Growth: {_fmt_pct(rg, 1)}")
        eg = analysis.get('earnings_growth')
        sections.append(f"Earnings Growth: {_fmt_pct(eg, 1)}")

        # Earnings
        sections.append("\n--- EARNINGS ---")
        sections.append(f"EPS (TTM): {_fmt(analysis.get('earnings_per_share'))}")
        sections.append(f"Forward EPS: {_fmt(analysis.get('forward_eps'))}")
        re_data = analysis.get('recent_earnings', {})
        beat_rate = re_data.get('beat_rate')
        sections.append(f"Earnings Beat Rate: {_fmt_pct_value(beat_rate, 0)} ({re_data.get('beats', 0)}/{re_data.get('total', 0)} quarters)")
        sections.append(f"Earnings Trend: {_fmt(re_data.get('trend'))}")

        # SEC EDGAR trends
        eps_trend = analysis.get('eps_trend', {})
        if eps_trend and eps_trend.get('trend') != 'insufficient_data':
            sections.append("\n--- SEC EDGAR EPS TREND ---")
            sections.append(f"EPS Trend Direction: {_fmt(eps_trend.get('trend'))}")
            sections.append(f"Latest EPS: {_fmt(eps_trend.get('latest_eps'))}")
            sections.append(f"QoQ Change: {_fmt_pct_value(eps_trend.get('qoq_pct'), 2)}")
            sections.append(f"YoY Change: {_fmt_pct_value(eps_trend.get('yoy_pct'), 2)}")

        rev_trend = analysis.get('revenue_trend', {})
        if rev_trend and rev_trend.get('trend') != 'insufficient_data':
            sections.append("\n--- SEC EDGAR REVENUE TREND ---")
            sections.append(f"Revenue Trend Direction: {_fmt(rev_trend.get('trend'))}")
            latest_rev = rev_trend.get('latest_revenue')
            sections.append(f"Latest Revenue: {_fmt_money(latest_rev)}")
            sections.append(f"QoQ Change: {_fmt_pct_value(rev_trend.get('qoq_pct'), 2)}")
            sections.append(f"YoY Change: {_fmt_pct_value(rev_trend.get('yoy_pct'), 2)}")

        # Analyst targets
        sections.append("\n--- ANALYST CONSENSUS ---")
        sections.append(f"Recommendation: {_fmt(analysis.get('recommendation'))}")
        sections.append(f"Target High: {_fmt(analysis.get('target_high_price'))}")
        sections.append(f"Target Mean: {_fmt(analysis.get('target_mean_price'))}")
        sections.append(f"Target Low: {_fmt(analysis.get('target_low_price'))}")
        sections.append(f"Analyst Count: {_fmt(analysis.get('number_of_analyst_opinions'))}")

        # Dividends
        dy = analysis.get('dividend_yield')
        if dy is not None:
            sections.append("\n--- DIVIDENDS ---")
            sections.append(f"Dividend Yield: {_fmt_pct(dy, 2)}")
            sections.append(f"Dividend Rate: {_fmt(analysis.get('dividend_rate'))}")
            pr = analysis.get('payout_ratio')
            sections.append(f"Payout Ratio: {_fmt_pct(pr, 1)}")

        # Revenue segment correlation (cross-reference with growth)
        rev_segments = analysis.get('revenue_segments')
        rev_growth = analysis.get('revenue_growth')
        if rev_segments:
            sections.append("\n--- REVENUE SEGMENT CORRELATION ---")
            product = rev_segments.get('product', {})
            if product:
                total = sum(v for v in product.values() if isinstance(v, (int, float)))
                sections.append("Product Segments (% of total):")
                for seg_name, seg_rev in sorted(product.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
                    if isinstance(seg_rev, (int, float)) and total > 0:
                        pct = seg_rev / total * 100
                        sections.append(f"  {seg_name}: ${seg_rev/1e9:.1f}B ({pct:.1f}%)")
            geo = rev_segments.get('geography', {})
            if geo:
                total = sum(v for v in geo.values() if isinstance(v, (int, float)))
                sections.append("Geographic Segments (% of total):")
                for reg_name, reg_rev in sorted(geo.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
                    if isinstance(reg_rev, (int, float)) and total > 0:
                        pct = reg_rev / total * 100
                        sections.append(f"  {reg_name}: ${reg_rev/1e9:.1f}B ({pct:.1f}%)")
            if rev_growth:
                sections.append(f"Overall Revenue Growth: {rev_growth}")

        # Structured transcript metrics (extracted before LLM call)
        t_metrics = analysis.get('transcript_metrics', {})
        if t_metrics:
            sections.append("\n--- STRUCTURED TRANSCRIPT METRICS (Regex-Extracted) ---")
            if t_metrics.get('revenue_guidance'):
                g = t_metrics['revenue_guidance']
                high_str = f" to ${g['high']} {g['unit']}" if g.get('high') else ""
                sections.append(f"Revenue Guidance: ${g['low']}{high_str} {g['unit']}")
            if t_metrics.get('eps_guidance'):
                g = t_metrics['eps_guidance']
                high_str = f" to ${g['high']}" if g.get('high') else ""
                sections.append(f"EPS Guidance: ${g['low']}{high_str}")
            if t_metrics.get('growth_targets'):
                targets = [f"{t['value']}%" for t in t_metrics['growth_targets'][:3]]
                sections.append(f"Growth Targets Mentioned: {', '.join(targets)}")
            if t_metrics.get('capex'):
                c = t_metrics['capex']
                sections.append(f"Capex Outlook: ${c['value']} {c['unit']}")

        # Previous quarter comparison
        prev_metrics = analysis.get('prev_quarter_transcript_metrics', {})
        prev_info = analysis.get('prev_quarter_transcript', {})
        if prev_metrics and prev_info:
            sections.append(f"\n--- PREVIOUS QUARTER METRICS (Q{prev_info.get('quarter')} {prev_info.get('year')}) ---")
            if prev_metrics.get('revenue_guidance'):
                g = prev_metrics['revenue_guidance']
                high_str = f" to ${g['high']} {g['unit']}" if g.get('high') else ""
                sections.append(f"Prior Revenue Guidance: ${g['low']}{high_str} {g['unit']}")
            if prev_metrics.get('eps_guidance'):
                g = prev_metrics['eps_guidance']
                high_str = f" to ${g['high']}" if g.get('high') else ""
                sections.append(f"Prior EPS Guidance: ${g['low']}{high_str}")

        # Earnings call transcript
        transcript = analysis.get('earnings_transcript')
        if transcript and transcript.get('content'):
            sections.append(f"\n--- EARNINGS CALL TRANSCRIPT (Q{transcript.get('quarter')} {transcript.get('year')}) ---")
            sections.append(f"Date: {transcript.get('date', 'N/A')}")
            sections.append(transcript['content'])

        # Health score
        sections.append(f"\n--- COMPUTED HEALTH SCORE ---")
        sections.append(f"Health Score: {_fmt(analysis.get('health_score'))}/100")

        return "\n".join(sections)

    def _build_research_prompt(self, context: str) -> str:
        """
        Build the equity research analyst prompt with fundamentals context.

        Args:
            context: Formatted fundamentals data string

        Returns:
            Complete prompt string
        """
        return f"""Role: Act as a Senior Equity Research Analyst at a top-tier investment firm. Your goal is to provide a strictly objective, unbiased, and deep-dive analysis of {self.ticker}.

Here is the current fundamental data for {self.ticker}:

{context}

Task: Conduct a comprehensive due diligence review using the data above. Avoid generic summaries; focus on actionable insights, data discrepancies, and investment nuance.
  * Executive Summary: A 3-sentence hook describing the company's core business model and current market sentiment.
  * The Bull Case (The "Long" Thesis):
    * What are the top 3 specific catalysts for growth in the next 12-24 months?
    * What is the company's "Moat" (competitive advantage)?
  * The Bear Case (The "Short" Thesis):
    * What is the single biggest existential risk to the company right now?
    * What specific metrics (e.g., margin compression, high churn, debt load) are concerning?
  * Financial Health Check:
    * Analyze their Free Cash Flow (FCF) and Profitability trends.
    * Comment on their Valuation (P/E, PEG, P/S) relative to historical averages and direct competitors.
  * The "Uncomfortable Questions": List 2 critical questions a skeptical investor would ask the CEO on an earnings call that haven't been adequately answered yet.

Constraints:
  * Prioritize recent earnings data, earnings call transcript commentary, and macro-economic factors.
  * If an earnings call transcript is provided, extract key management commentary on guidance, strategic priorities, and risk factors.
  * Maintain a professional, skeptical, and balanced tone.
  * Base your analysis strictly on the data provided. Do not fabricate numbers.

Respond ONLY in the following JSON format:
{{
  "executive_summary": "<3-sentence hook describing core business model and current market sentiment>",
  "bull_case": {{
    "catalysts": [
      {{"catalyst": "<specific catalyst 1>", "reasoning": "<why this matters in next 12-24 months>"}},
      {{"catalyst": "<specific catalyst 2>", "reasoning": "<why this matters>"}},
      {{"catalyst": "<specific catalyst 3>", "reasoning": "<why this matters>"}}
    ],
    "moat": "<description of the company's competitive advantage>"
  }},
  "bear_case": {{
    "existential_risk": "<single biggest existential risk right now>",
    "concerning_metrics": [
      {{"metric": "<specific metric name>", "concern": "<why this is concerning>"}},
      {{"metric": "<specific metric name>", "concern": "<why this is concerning>"}}
    ]
  }},
  "financial_health_check": {{
    "fcf_analysis": "<analysis of Free Cash Flow and profitability trends>",
    "valuation_analysis": "<P/E, PEG, P/S analysis relative to historical averages and competitors>"
  }},
  "uncomfortable_questions": [
    "<critical question 1 a skeptical investor would ask the CEO>",
    "<critical question 2>"
  ],
  "overall_assessment": "<1-sentence bottom-line assessment>",
  "confidence": <float from 0.0 to 1.0>
}}"""

    async def _run_equity_research_llm(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Run LLM-powered deep equity research analysis on the computed fundamentals.

        Args:
            analysis: The computed fundamentals analysis dict (with all metrics)

        Returns:
            Parsed equity research report dict, or None if LLM call fails
        """
        # Check if LLM analysis is enabled
        if not self.config.get("FUNDAMENTALS_LLM_ENABLED", True):
            self.logger.info("Fundamentals LLM analysis disabled by config")
            return None

        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        api_key = llm_config.get("api_key")

        if not api_key:
            self.logger.warning("No LLM API key available, skipping equity research analysis")
            return None

        context = self._build_llm_context(analysis)
        prompt = self._build_research_prompt(context)

        try:
            if provider == "anthropic":
                response_text = await self._call_anthropic_llm(prompt, llm_config)
            elif provider in ("xai", "openai"):
                response_text = await self._call_openai_compatible_llm(prompt, llm_config)
            else:
                self.logger.warning(f"Unsupported LLM provider '{provider}' for equity research")
                return None

            # Parse JSON from response (same pattern as sentiment_agent.py)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("Could not find JSON in LLM equity research response")

            result = json.loads(json_str)

            # Validate expected top-level keys
            expected_keys = ["executive_summary", "bull_case", "bear_case",
                             "financial_health_check", "uncomfortable_questions"]
            missing = [k for k in expected_keys if k not in result]
            if missing:
                self.logger.warning(f"LLM equity research response missing keys: {missing}")

            self.logger.info(f"LLM equity research analysis completed for {self.ticker}")
            return result

        except Exception as e:
            self.logger.error(f"LLM equity research analysis failed: {e}", exc_info=True)
            return None

    async def _call_anthropic_llm(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        """
        Make Anthropic API call and return response text.

        Args:
            prompt: The prompt to send
            llm_config: LLM configuration dict

        Returns:
            Response text string
        """
        client = anthropic.Anthropic(api_key=llm_config.get("api_key"))
        def _call_anthropic():
            return client.messages.create(
                model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.3),
                messages=[{"role": "user", "content": prompt}]
            )

        message = await asyncio.to_thread(_call_anthropic)
        return message.content[0].text

    async def _call_openai_compatible_llm(self, prompt: str, llm_config: Dict[str, Any]) -> str:
        """
        Make OpenAI-compatible API call (xAI/Grok, OpenAI, etc).

        Args:
            prompt: The prompt to send
            llm_config: LLM configuration dict

        Returns:
            Response text string
        """
        client = OpenAI(
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url")
        )
        def _call_openai():
            return client.chat.completions.create(
                model=llm_config.get("model", "grok-4-1-fast-reasoning"),
                max_tokens=llm_config.get("max_tokens", 4096),
                temperature=llm_config.get("temperature", 0.3),
                messages=[{"role": "user", "content": prompt}]
            )

        response = await asyncio.to_thread(_call_openai)
        return response.choices[0].message.content
