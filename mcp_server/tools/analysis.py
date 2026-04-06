"""Layer 1: Analysis tools — processed, LLM-optimized research data."""

from typing import Optional


def register_tools(mcp, call_api):

    @mcp.tool()
    async def get_ticker_summary(ticker: str) -> str:
        """Get a quick summary of the latest analysis for a stock (~200 tokens).
        Returns recommendation, score, confidence, price targets, top risks/opportunities.
        For deeper analysis, use get_ticker_analysis instead.

        Args:
            ticker: Stock ticker symbol (e.g., AAPL, MSFT, NVDA)
        """
        return await call_api("GET", f"/api/agent/{ticker.upper()}/summary")

    @mcp.tool()
    async def get_ticker_analysis(ticker: str, detail: str = "standard", sections: Optional[str] = None) -> str:
        """Get detailed analysis with configurable depth and section filtering.
        Detail levels: "summary" (~200 tokens), "standard" (~1-2K), "full" (~3-6K).

        Args:
            ticker: Stock ticker symbol
            detail: Detail level — "summary", "standard", or "full"
            sections: Comma-separated agent types (e.g., "fundamentals,sentiment")
        """
        params = {"detail": detail}
        if sections:
            params["sections"] = sections
        return await call_api("GET", f"/api/agent/{ticker.upper()}/analysis", params=params)

    @mcp.tool()
    async def get_ticker_changes(ticker: str) -> str:
        """Get what changed between the two most recent analyses.
        Returns recommendation change, score/confidence/sentiment deltas.

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/{ticker.upper()}/changes")

    @mcp.tool()
    async def get_ticker_inflections(ticker: str, limit: int = 20) -> str:
        """Get recent inflection events (significant KPI changes) for a stock.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum events to return (default: 20)
        """
        return await call_api("GET", f"/api/agent/{ticker.upper()}/inflections", params={"limit": limit})

    @mcp.tool()
    async def get_council_results(ticker: str) -> str:
        """Get the latest investor council analysis (legendary investor personas).

        Args:
            ticker: Stock ticker symbol
        """
        return await call_api("GET", f"/api/agent/{ticker.upper()}/council")

    @mcp.tool()
    async def compare_tickers(tickers: str) -> str:
        """Side-by-side comparison of 2-5 stocks.

        Args:
            tickers: Comma-separated tickers (e.g., "AAPL,MSFT,GOOGL"), max 5
        """
        return await call_api("GET", "/api/agent/compare", params={"tickers": tickers})
