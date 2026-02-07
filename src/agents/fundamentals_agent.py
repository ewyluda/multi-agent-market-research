"""Fundamentals agent for analyzing company financial data."""

import asyncio
import random
import re
import aiohttp
import json
import anthropic
from openai import OpenAI
import yfinance as yf
from typing import Dict, Any, Optional, List
from .base_agent import BaseAgent


class FundamentalsAgent(BaseAgent):
    """Agent for fetching and analyzing fundamental company data."""

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

    async def _retry_fetch(self, func, max_retries: int = None, label: str = ""):
        """
        Retry a synchronous function with exponential backoff.

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

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch fundamental data using yfinance and SEC EDGAR with retry logic.
        Each data source is fetched independently for graceful degradation.

        Returns:
            Dictionary with company info, financials, earnings data, and SEC filings
        """
        ticker_obj = yf.Ticker(self.ticker)
        result = {"ticker": self.ticker}

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

        # Calculate health score
        analysis["health_score"] = self._calculate_health_score(analysis)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        # Run LLM-powered equity research analysis
        equity_research = await self._run_equity_research_llm(analysis)
        if equity_research:
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

        # Company overview
        sections.append(f"Company: {analysis.get('company_name', 'N/A')}")
        sections.append(f"Ticker: {self.ticker}")
        sections.append(f"Sector: {analysis.get('sector', 'N/A')}")
        sections.append(f"Industry: {analysis.get('industry', 'N/A')}")
        mc = analysis.get('market_cap')
        sections.append(f"Market Cap: {'${:,.0f}'.format(mc) if mc else 'N/A'}")

        # Valuation
        sections.append("\n--- VALUATION ---")
        sections.append(f"P/E Ratio (TTM): {analysis.get('pe_ratio', 'N/A')}")
        sections.append(f"Forward P/E: {analysis.get('forward_pe', 'N/A')}")
        sections.append(f"PEG Ratio: {analysis.get('peg_ratio', 'N/A')}")
        sections.append(f"Price/Book: {analysis.get('price_to_book', 'N/A')}")
        sections.append(f"Price/Sales: {analysis.get('price_to_sales', 'N/A')}")
        ev = analysis.get('enterprise_value')
        sections.append(f"Enterprise Value: {'${:,.0f}'.format(ev) if ev else 'N/A'}")

        # Profitability
        sections.append("\n--- PROFITABILITY ---")
        pm = analysis.get('profit_margins')
        sections.append(f"Profit Margins: {f'{pm*100:.1f}%' if pm else 'N/A'}")
        om = analysis.get('operating_margins')
        sections.append(f"Operating Margins: {f'{om*100:.1f}%' if om else 'N/A'}")
        roa = analysis.get('return_on_assets')
        sections.append(f"ROA: {f'{roa*100:.1f}%' if roa else 'N/A'}")
        roe = analysis.get('return_on_equity')
        sections.append(f"ROE: {f'{roe*100:.1f}%' if roe else 'N/A'}")

        # Cash Flow
        sections.append("\n--- CASH FLOW ---")
        fcf = analysis.get('free_cash_flow')
        sections.append(f"Free Cash Flow: {'${:,.0f}'.format(fcf) if fcf else 'N/A'}")
        ocf = analysis.get('operating_cash_flow')
        sections.append(f"Operating Cash Flow: {'${:,.0f}'.format(ocf) if ocf else 'N/A'}")

        # Balance Sheet Health
        sections.append("\n--- BALANCE SHEET ---")
        sections.append(f"Current Ratio: {analysis.get('current_ratio', 'N/A')}")
        sections.append(f"Debt/Equity: {analysis.get('debt_to_equity', 'N/A')}")
        sections.append(f"Quick Ratio: {analysis.get('quick_ratio', 'N/A')}")

        # Growth
        sections.append("\n--- GROWTH ---")
        rg = analysis.get('revenue_growth')
        sections.append(f"Revenue Growth: {f'{rg*100:.1f}%' if rg else 'N/A'}")
        eg = analysis.get('earnings_growth')
        sections.append(f"Earnings Growth: {f'{eg*100:.1f}%' if eg else 'N/A'}")

        # Earnings
        sections.append("\n--- EARNINGS ---")
        sections.append(f"EPS (TTM): {analysis.get('earnings_per_share', 'N/A')}")
        sections.append(f"Forward EPS: {analysis.get('forward_eps', 'N/A')}")
        re_data = analysis.get('recent_earnings', {})
        sections.append(f"Earnings Beat Rate: {re_data.get('beat_rate', 'N/A')}% ({re_data.get('beats', 0)}/{re_data.get('total', 0)} quarters)")
        sections.append(f"Earnings Trend: {re_data.get('trend', 'N/A')}")

        # SEC EDGAR trends
        eps_trend = analysis.get('eps_trend', {})
        if eps_trend and eps_trend.get('trend') != 'insufficient_data':
            sections.append("\n--- SEC EDGAR EPS TREND ---")
            sections.append(f"EPS Trend Direction: {eps_trend.get('trend', 'N/A')}")
            sections.append(f"Latest EPS: {eps_trend.get('latest_eps', 'N/A')}")
            sections.append(f"QoQ Change: {eps_trend.get('qoq_pct', 'N/A')}%")
            sections.append(f"YoY Change: {eps_trend.get('yoy_pct', 'N/A')}%")

        rev_trend = analysis.get('revenue_trend', {})
        if rev_trend and rev_trend.get('trend') != 'insufficient_data':
            sections.append("\n--- SEC EDGAR REVENUE TREND ---")
            sections.append(f"Revenue Trend Direction: {rev_trend.get('trend', 'N/A')}")
            latest_rev = rev_trend.get('latest_revenue')
            sections.append(f"Latest Revenue: {'${:,.0f}'.format(latest_rev) if latest_rev else 'N/A'}")
            sections.append(f"QoQ Change: {rev_trend.get('qoq_pct', 'N/A')}%")
            sections.append(f"YoY Change: {rev_trend.get('yoy_pct', 'N/A')}%")

        # Analyst targets
        sections.append("\n--- ANALYST CONSENSUS ---")
        sections.append(f"Recommendation: {analysis.get('recommendation', 'N/A')}")
        sections.append(f"Target High: {analysis.get('target_high_price', 'N/A')}")
        sections.append(f"Target Mean: {analysis.get('target_mean_price', 'N/A')}")
        sections.append(f"Target Low: {analysis.get('target_low_price', 'N/A')}")
        sections.append(f"Analyst Count: {analysis.get('number_of_analyst_opinions', 'N/A')}")

        # Dividends
        dy = analysis.get('dividend_yield')
        if dy:
            sections.append("\n--- DIVIDENDS ---")
            sections.append(f"Dividend Yield: {f'{dy*100:.2f}%' if dy else 'N/A'}")
            sections.append(f"Dividend Rate: {analysis.get('dividend_rate', 'N/A')}")
            pr = analysis.get('payout_ratio')
            sections.append(f"Payout Ratio: {f'{pr*100:.1f}%' if pr else 'N/A'}")

        # Health score
        sections.append(f"\n--- COMPUTED HEALTH SCORE ---")
        sections.append(f"Health Score: {analysis.get('health_score', 'N/A')}/100")

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
  * Prioritize recent earnings data and macro-economic factors.
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
        message = client.messages.create(
            model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
            max_tokens=llm_config.get("max_tokens", 4096),
            temperature=llm_config.get("temperature", 0.3),
            messages=[{"role": "user", "content": prompt}]
        )
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
        response = client.chat.completions.create(
            model=llm_config.get("model", "grok-4-1-fast-reasoning"),
            max_tokens=llm_config.get("max_tokens", 4096),
            temperature=llm_config.get("temperature", 0.3),
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
