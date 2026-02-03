"""Fundamentals agent for analyzing company financial data."""

import yfinance as yf
from typing import Dict, Any
from .base_agent import BaseAgent


class FundamentalsAgent(BaseAgent):
    """Agent for fetching and analyzing fundamental company data."""

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch fundamental data using yfinance.

        Returns:
            Dictionary with company info, financials, and earnings data
        """
        ticker_obj = yf.Ticker(self.ticker)

        try:
            # Get company info
            info = ticker_obj.info

            # Get earnings data
            earnings = ticker_obj.earnings_dates
            if earnings is not None and not earnings.empty:
                earnings_data = earnings.head(10).to_dict('records')
            else:
                earnings_data = []

            # Get quarterly earnings
            quarterly_earnings = ticker_obj.quarterly_earnings
            if quarterly_earnings is not None and not quarterly_earnings.empty:
                quarterly_data = quarterly_earnings.head(8).to_dict('records')
            else:
                quarterly_data = []

            return {
                "info": info,
                "earnings_dates": earnings_data,
                "quarterly_earnings": quarterly_data,
                "ticker": self.ticker
            }

        except Exception as e:
            self.logger.error(f"Error fetching fundamentals for {self.ticker}: {e}")
            raise

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze fundamental data and extract key metrics.

        Args:
            raw_data: Raw data from yfinance

        Returns:
            Analyzed fundamental metrics
        """
        info = raw_data.get("info", {})
        earnings_dates = raw_data.get("earnings_dates", [])
        quarterly_earnings = raw_data.get("quarterly_earnings", [])

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

            # Recent earnings
            "recent_earnings": self._analyze_earnings(quarterly_earnings),

            # Company health
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "quick_ratio": info.get("quickRatio"),

            # Cash flow
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
        }

        # Calculate health score
        analysis["health_score"] = self._calculate_health_score(analysis)

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def _analyze_earnings(self, quarterly_earnings: list) -> Dict[str, Any]:
        """
        Analyze recent earnings performance.

        Args:
            quarterly_earnings: List of quarterly earnings data

        Returns:
            Earnings analysis
        """
        if not quarterly_earnings or len(quarterly_earnings) == 0:
            return {
                "beats": 0,
                "misses": 0,
                "total": 0,
                "beat_rate": 0.0,
                "trend": "unknown"
            }

        # Count beats and misses (simplified - would need actual vs expected data)
        # For now, just return structure
        return {
            "beats": 0,
            "misses": 0,
            "total": len(quarterly_earnings),
            "beat_rate": 0.0,
            "recent_quarters": quarterly_earnings[:4],
            "trend": "stable"
        }

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

        return summary
