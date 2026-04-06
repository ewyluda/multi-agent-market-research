"""Layer 3: Raw data tools — direct access to FMP, FRED, EDGAR, and options data."""

from typing import Optional


def register_tools(mcp, call_api):

    @mcp.tool()
    async def get_stock_quote(ticker: str) -> str:
        """Get real-time stock quote — price, change, volume, market cap.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/quote")

    @mcp.tool()
    async def get_price_history(ticker: str, period: str = "3m") -> str:
        """Get historical OHLCV price data.

        Args:
            ticker: Stock ticker symbol
            period: "1m", "3m", "6m", "1y", or "2y" (default: "3m")
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/price-history", params={"period": period})

    @mcp.tool()
    async def get_company_profile(ticker: str) -> str:
        """Get company overview — sector, industry, description, employees.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/profile")

    @mcp.tool()
    async def get_financials(ticker: str) -> str:
        """Get financial statements — revenue, net income, EPS, ratios, cash flow.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/financials")

    @mcp.tool()
    async def get_earnings_history(ticker: str) -> str:
        """Get earnings history — EPS actual vs estimated, beat/miss record.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/earnings")

    @mcp.tool()
    async def get_earnings_transcript(ticker: str, year: int = 0, quarter: int = 0) -> str:
        """Get full earnings call transcript. WARNING: Large output (5K-15K tokens).

        Args:
            ticker: Stock ticker symbol
            year: Earnings year (default: most recent)
            quarter: Earnings quarter 1-4 (default: most recent)
        """
        params = {}
        if year:
            params["year"] = year
        if quarter:
            params["quarter"] = quarter
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/transcript", params=params, timeout=60)

    @mcp.tool()
    async def get_analyst_estimates(ticker: str) -> str:
        """Get consensus analyst estimates.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/analyst-estimates")

    @mcp.tool()
    async def get_price_targets(ticker: str) -> str:
        """Get analyst price targets.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/price-targets")

    @mcp.tool()
    async def get_insider_trading(ticker: str) -> str:
        """Get recent insider transactions.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/insider-trading")

    @mcp.tool()
    async def get_peers(ticker: str) -> str:
        """Get peer/comparable companies.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/peers")

    @mcp.tool()
    async def get_financial_ratios(ticker: str) -> str:
        """Get trailing twelve month financial ratios.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/ratios")

    @mcp.tool()
    async def get_revenue_segments(ticker: str) -> str:
        """Get revenue breakdown by segment and geography.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/revenue-segments")

    @mcp.tool()
    async def get_dcf_valuation(ticker: str) -> str:
        """Get DCF valuation model output.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/dcf")

    @mcp.tool()
    async def get_management(ticker: str) -> str:
        """Get executive team — names, titles.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/management")

    @mcp.tool()
    async def get_financial_growth(ticker: str) -> str:
        """Get financial growth metrics.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/growth")

    @mcp.tool()
    async def get_share_statistics(ticker: str) -> str:
        """Get share float and trading statistics.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/share-stats")

    @mcp.tool()
    async def get_technical_indicators(ticker: str) -> str:
        """Get technical indicators — RSI, MACD, Bollinger Bands, moving averages.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/technical")

    @mcp.tool()
    async def get_options_chain(ticker: str) -> str:
        """Get options chain — put/call ratios, implied volatility.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/options")

    @mcp.tool()
    async def get_news(ticker: str, limit: int = 10) -> str:
        """Get recent news articles for a stock.

        Args:
            ticker: Stock ticker symbol
            limit: Max articles (default: 10, max: 50)
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/news", params={"limit": limit})

    @mcp.tool()
    async def get_macro_indicators() -> str:
        """Get macroeconomic indicators — fed funds, CPI, GDP, yields, unemployment."""
        return await call_api("GET", "/api/agent/data/macro")

    @mcp.tool()
    async def get_sec_filings(ticker: str, filing_type: str = "10-K", limit: int = 3) -> str:
        """Get SEC filing metadata — dates, links, accession numbers.

        Args:
            ticker: Stock ticker symbol
            filing_type: "10-K" (annual) or "10-Q" (quarterly)
            limit: Max filings (default: 3)
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/sec-filings", params={"filing_type": filing_type, "limit": limit})

    @mcp.tool()
    async def get_sec_risk_factors(ticker: str, filing_url: str) -> str:
        """Extract Item 1A (Risk Factors) from an SEC filing. WARNING: Large output (2-10K tokens).
        Get filing URLs from get_sec_filings first. URL must be from sec.gov or FMP.

        Args:
            ticker: Stock ticker symbol
            filing_url: URL from get_sec_filings results (must be sec.gov or FMP)
        """
        return await call_api("GET", f"/api/agent/data/{ticker.upper()}/sec-section", params={"filing_url": filing_url}, timeout=60)
