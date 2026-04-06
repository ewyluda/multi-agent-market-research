"""Layer 2: Action tools — trigger analyses, manage watchlists/alerts/portfolio."""

from typing import Optional


def register_tools(mcp, call_api):

    @mcp.tool()
    async def run_analysis(ticker: str, agents: Optional[str] = None) -> str:
        """Run a fresh analysis for a stock. Takes 15-45 seconds.

        Args:
            ticker: Stock ticker symbol
            agents: Optional comma-separated agent list (e.g., "news,fundamentals")
        """
        body = {}
        if agents:
            body["agents"] = agents
        return await call_api("POST", f"/api/agent/{ticker.upper()}/analyze", json_body=body or None, timeout=130)

    @mcp.tool()
    async def run_council(ticker: str, investors: Optional[str] = None) -> str:
        """Run investor council analysis. Requires existing analysis. Takes 30-90s.

        Args:
            ticker: Stock ticker symbol
            investors: Optional comma-separated investor names
        """
        params = {}
        if investors:
            params["investors"] = investors
        return await call_api("POST", f"/api/agent/{ticker.upper()}/council", params=params, timeout=130)

    @mcp.tool()
    async def list_watchlists() -> str:
        """List all watchlists with their tickers."""
        return await call_api("GET", "/api/agent/watchlists")

    @mcp.tool()
    async def create_watchlist(name: str) -> str:
        """Create a new watchlist.

        Args:
            name: Watchlist name (e.g., "Tech Stocks")
        """
        return await call_api("POST", "/api/agent/watchlists", json_body={"name": name})

    @mcp.tool()
    async def update_watchlist(watchlist_id: int, name: str) -> str:
        """Rename a watchlist.

        Args:
            watchlist_id: ID of the watchlist
            name: New name
        """
        return await call_api("PUT", f"/api/agent/watchlists/{watchlist_id}", json_body={"name": name})

    @mcp.tool()
    async def delete_watchlist(watchlist_id: int) -> str:
        """Delete a watchlist.

        Args:
            watchlist_id: ID to delete
        """
        return await call_api("DELETE", f"/api/agent/watchlists/{watchlist_id}")

    @mcp.tool()
    async def add_ticker_to_watchlist(watchlist_id: int, ticker: str) -> str:
        """Add a stock to a watchlist.

        Args:
            watchlist_id: Watchlist ID
            ticker: Stock ticker (e.g., AAPL)
        """
        return await call_api("POST", f"/api/agent/watchlists/{watchlist_id}/tickers", json_body={"ticker": ticker.upper()})

    @mcp.tool()
    async def remove_ticker_from_watchlist(watchlist_id: int, ticker: str) -> str:
        """Remove a stock from a watchlist.

        Args:
            watchlist_id: Watchlist ID
            ticker: Stock ticker to remove
        """
        return await call_api("DELETE", f"/api/agent/watchlists/{watchlist_id}/tickers/{ticker.upper()}")

    @mcp.tool()
    async def list_alerts(ticker: Optional[str] = None) -> str:
        """List active alert rules, optionally filtered by ticker.

        Args:
            ticker: Optional ticker filter
        """
        params = {}
        if ticker:
            params["ticker"] = ticker.upper()
        return await call_api("GET", "/api/agent/alerts", params=params)

    @mcp.tool()
    async def create_alert(ticker: str, rule_type: str, threshold: Optional[float] = None) -> str:
        """Create a new alert rule.

        Args:
            ticker: Stock ticker to monitor
            rule_type: Alert type (e.g., "price_change", "recommendation_change")
            threshold: Threshold value (e.g., 5.0 for 5% change)
        """
        body = {"ticker": ticker.upper(), "rule_type": rule_type}
        if threshold is not None:
            body["threshold"] = threshold
        return await call_api("POST", "/api/agent/alerts", json_body=body)

    @mcp.tool()
    async def delete_alert(rule_id: int) -> str:
        """Delete an alert rule.

        Args:
            rule_id: Alert rule ID to delete
        """
        return await call_api("DELETE", f"/api/agent/alerts/{rule_id}")

    @mcp.tool()
    async def get_portfolio() -> str:
        """Get portfolio holdings and snapshot."""
        return await call_api("GET", "/api/agent/portfolio")

    @mcp.tool()
    async def add_holding(ticker: str, shares: float, avg_cost: Optional[float] = None, market_value: Optional[float] = None, sector: Optional[str] = None) -> str:
        """Add a holding to the portfolio.

        Args:
            ticker: Stock ticker
            shares: Number of shares
            avg_cost: Average cost per share
            market_value: Current market value
            sector: Sector classification
        """
        body = {"ticker": ticker.upper(), "shares": shares}
        if avg_cost is not None:
            body["avg_cost"] = avg_cost
        if market_value is not None:
            body["market_value"] = market_value
        if sector:
            body["sector"] = sector
        return await call_api("POST", "/api/agent/portfolio", json_body=body)

    @mcp.tool()
    async def remove_holding(holding_id: int) -> str:
        """Remove a holding from the portfolio.

        Args:
            holding_id: Holding ID to remove
        """
        return await call_api("DELETE", f"/api/agent/portfolio/{holding_id}")
