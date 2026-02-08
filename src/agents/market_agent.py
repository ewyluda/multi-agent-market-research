"""Market agent for analyzing price data and market trends."""

import asyncio
import random
import aiohttp
import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .base_agent import BaseAgent


class MarketAgent(BaseAgent):
    """Agent for fetching and analyzing market price data.

    Data source priority:
        1. Alpha Vantage API (GLOBAL_QUOTE + TIME_SERIES_DAILY)
        2. yfinance (fallback)
    """

    AV_BASE_URL = "https://www.alphavantage.co/query"

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

    # ──────────────────────────────────────────────
    # Alpha Vantage Data Fetching
    # ──────────────────────────────────────────────

    async def _av_request(self, params: Dict[str, str]) -> Optional[Dict]:
        """
        Make a request to Alpha Vantage API.

        Args:
            params: Query parameters (function, symbol, etc.)

        Returns:
            JSON response dict, or None on failure
        """
        api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            return None

        params["apikey"] = api_key
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.AV_BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        self.logger.warning(f"Alpha Vantage returned status {resp.status}")
                        return None
                    data = await resp.json(content_type=None)
                    # Check for API error messages
                    if "Error Message" in data or "Note" in data:
                        msg = data.get("Error Message") or data.get("Note", "")
                        self.logger.warning(f"Alpha Vantage API error: {msg}")
                        return None
                    if "Information" in data and "rate limit" in data.get("Information", "").lower():
                        self.logger.warning(f"Alpha Vantage rate limited: {data['Information']}")
                        return None
                    return data
        except Exception as e:
            self.logger.warning(f"Alpha Vantage request failed: {e}")
            return None

    async def _fetch_av_quote(self) -> Optional[Dict[str, Any]]:
        """
        Fetch latest quote from Alpha Vantage GLOBAL_QUOTE.

        Returns:
            Dict with current price data, or None
        """
        data = await self._av_request({
            "function": "GLOBAL_QUOTE",
            "symbol": self.ticker,
            "datatype": "json"
        })
        if not data or "Global Quote" not in data:
            return None

        quote = data["Global Quote"]
        if not quote:
            return None

        try:
            return {
                "current_price": float(quote.get("05. price", 0)),
                "open": float(quote.get("02. open", 0)),
                "day_high": float(quote.get("03. high", 0)),
                "day_low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "previous_close": float(quote.get("08. previous close", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%"),
            }
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse Alpha Vantage quote: {e}")
            return None

    async def _fetch_av_daily(self, outputsize: str = "compact") -> Optional[pd.DataFrame]:
        """
        Fetch daily time series from Alpha Vantage TIME_SERIES_DAILY.

        Args:
            outputsize: "compact" (100 data points) or "full" (20+ years)

        Returns:
            DataFrame with OHLCV data, or None
        """
        data = await self._av_request({
            "function": "TIME_SERIES_DAILY",
            "symbol": self.ticker,
            "outputsize": outputsize,
            "datatype": "json"
        })
        if not data:
            return None

        ts_key = "Time Series (Daily)"
        if ts_key not in data:
            return None

        time_series = data[ts_key]
        if not time_series:
            return None

        try:
            rows = []
            for date_str, values in time_series.items():
                rows.append({
                    "Date": pd.Timestamp(date_str),
                    "Open": float(values.get("1. open", 0)),
                    "High": float(values.get("2. high", 0)),
                    "Low": float(values.get("3. low", 0)),
                    "Close": float(values.get("4. close", 0)),
                    "Volume": int(values.get("5. volume", 0)),
                })

            df = pd.DataFrame(rows)
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            self.logger.warning(f"Failed to parse Alpha Vantage daily data: {e}")
            return None

    # ──────────────────────────────────────────────
    # Data Fetching (AV first, yfinance fallback)
    # ──────────────────────────────────────────────

    async def fetch_data(self) -> Dict[str, Any]:
        """
        Fetch market price data. Tries Alpha Vantage first, falls back to yfinance.

        Returns:
            Dictionary with price history and current market data
        """
        result = {"ticker": self.ticker, "source": "unknown"}

        # ── Try Alpha Vantage first ──
        av_api_key = self.config.get("ALPHA_VANTAGE_API_KEY", "")
        if av_api_key:
            self.logger.info(f"Fetching {self.ticker} market data from Alpha Vantage (primary)")

            # Fetch quote and daily data concurrently
            av_quote, av_daily_full = await asyncio.gather(
                self._fetch_av_quote(),
                self._fetch_av_daily(outputsize="full"),
                return_exceptions=True,
            )

            # Handle exceptions from gather
            if isinstance(av_quote, Exception):
                self.logger.warning(f"Alpha Vantage quote fetch raised: {av_quote}")
                av_quote = None
            if isinstance(av_daily_full, Exception):
                self.logger.warning(f"Alpha Vantage daily fetch raised: {av_daily_full}")
                av_daily_full = None

            if av_quote and av_daily_full is not None and not av_daily_full.empty:
                self.logger.info(f"Alpha Vantage returned {len(av_daily_full)} daily records for {self.ticker}")

                result["source"] = "alpha_vantage"
                result["info"] = {
                    "currentPrice": av_quote["current_price"],
                    "regularMarketPrice": av_quote["current_price"],
                    "previousClose": av_quote["previous_close"],
                    "open": av_quote["open"],
                    "regularMarketOpen": av_quote["open"],
                    "dayHigh": av_quote["day_high"],
                    "dayLow": av_quote["day_low"],
                    "volume": av_quote["volume"],
                }

                # Slice daily data into timeframes
                now = pd.Timestamp.now()
                result["history_1y"] = av_daily_full[av_daily_full.index >= now - pd.Timedelta(days=365)]
                result["history_3m"] = av_daily_full[av_daily_full.index >= now - pd.Timedelta(days=90)]
                result["history_1m"] = av_daily_full[av_daily_full.index >= now - pd.Timedelta(days=30)]

                return result
            else:
                self.logger.info(f"Alpha Vantage incomplete for {self.ticker}, falling back to yfinance")

        # ── Fallback to yfinance ──
        self.logger.info(f"Fetching {self.ticker} market data from yfinance (fallback)")
        result["source"] = "yfinance"

        ticker_obj = yf.Ticker(self.ticker)
        end_date = datetime.now()

        info = await self._retry_fetch(
            lambda: ticker_obj.info, label=f"{self.ticker} info"
        )
        result["info"] = info or {}

        result["history_1y"] = await self._retry_fetch(
            lambda: ticker_obj.history(start=end_date - timedelta(days=365), end=end_date),
            label=f"{self.ticker} history_1y"
        )

        result["history_3m"] = await self._retry_fetch(
            lambda: ticker_obj.history(start=end_date - timedelta(days=90), end=end_date),
            label=f"{self.ticker} history_3m"
        )

        result["history_1m"] = await self._retry_fetch(
            lambda: ticker_obj.history(start=end_date - timedelta(days=30), end=end_date),
            label=f"{self.ticker} history_1m"
        )

        # Only raise if we got absolutely nothing useful
        if (not result["info"]
            and result.get("history_1y") is None
            and result.get("history_3m") is None
            and result.get("history_1m") is None):
            raise Exception(f"Failed to fetch any market data for {self.ticker}")

        return result

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data for trends and patterns.

        Args:
            raw_data: Raw price data from Alpha Vantage or yfinance

        Returns:
            Market analysis with trends and patterns
        """
        info = raw_data.get("info", {})
        hist_1y = raw_data.get("history_1y")
        hist_3m = raw_data.get("history_3m")
        hist_1m = raw_data.get("history_1m")

        analysis = {
            # Current price data
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "day_high": info.get("dayHigh"),
            "day_low": info.get("dayLow"),
            "volume": info.get("volume"),
            "average_volume": info.get("averageVolume"),

            # Price ranges
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),

            # Market cap
            "market_cap": info.get("marketCap"),

            # Data source
            "data_source": raw_data.get("source", "unknown"),
        }

        # Calculate moving averages and trends
        if hist_1y is not None and not hist_1y.empty:
            analysis["ma_50"] = self._calculate_ma(hist_1y, 50)
            analysis["ma_200"] = self._calculate_ma(hist_1y, 200)

        if hist_3m is not None and not hist_3m.empty:
            analysis["ma_20"] = self._calculate_ma(hist_3m, 20)
            analysis["price_change_3m"] = self._calculate_price_change(hist_3m)
            analysis["volatility_3m"] = self._calculate_volatility(hist_3m)

        if hist_1m is not None and not hist_1m.empty:
            analysis["price_change_1m"] = self._calculate_price_change(hist_1m)
            analysis["volume_trend_1m"] = self._analyze_volume_trend(hist_1m)

        # Determine overall trend
        analysis["trend"] = self._determine_trend(analysis)

        # Calculate support and resistance levels
        if hist_3m is not None and not hist_3m.empty:
            support, resistance = self._calculate_support_resistance(hist_3m)
            analysis["support_level"] = support
            analysis["resistance_level"] = resistance

        # Generate summary
        analysis["summary"] = self._generate_summary(analysis)

        return analysis

    def _calculate_ma(self, df: pd.DataFrame, period: int) -> float:
        """Calculate moving average."""
        if df is None or len(df) < period:
            return None

        return df['Close'].tail(period).mean()

    def _calculate_price_change(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate price change over period."""
        if df is None or len(df) < 2:
            return {"change": 0, "change_pct": 0}

        first_price = df['Close'].iloc[0]
        last_price = df['Close'].iloc[-1]

        change = last_price - first_price
        change_pct = (change / first_price) * 100

        return {
            "change": float(change),
            "change_pct": float(change_pct),
            "start_price": float(first_price),
            "end_price": float(last_price)
        }

    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """Calculate price volatility (standard deviation of returns)."""
        if df is None or len(df) < 2:
            return 0.0

        returns = df['Close'].pct_change()
        return float(returns.std() * 100)  # Convert to percentage

    def _analyze_volume_trend(self, df: pd.DataFrame) -> str:
        """Analyze volume trend."""
        if df is None or len(df) < 10:
            return "unknown"

        recent_avg = df['Volume'].tail(5).mean()
        older_avg = df['Volume'].head(5).mean()

        if recent_avg > older_avg * 1.2:
            return "increasing"
        elif recent_avg < older_avg * 0.8:
            return "decreasing"
        else:
            return "stable"

    def _determine_trend(self, analysis: Dict[str, Any]) -> str:
        """Determine overall market trend."""
        current = analysis.get("current_price")
        ma_20 = analysis.get("ma_20")
        ma_50 = analysis.get("ma_50")
        ma_200 = analysis.get("ma_200")

        if not current:
            return "unknown"

        # Simple trend determination
        if ma_20 and ma_50 and ma_200:
            if current > ma_20 > ma_50 > ma_200:
                return "strong_uptrend"
            elif current < ma_20 < ma_50 < ma_200:
                return "strong_downtrend"
            elif current > ma_50:
                return "uptrend"
            elif current < ma_50:
                return "downtrend"

        # Fallback to 3-month performance
        change_3m = analysis.get("price_change_3m", {})
        pct_change = change_3m.get("change_pct", 0)

        if pct_change > 10:
            return "uptrend"
        elif pct_change < -10:
            return "downtrend"
        else:
            return "sideways"

    def _calculate_support_resistance(self, df: pd.DataFrame) -> tuple:
        """Calculate support and resistance levels."""
        if df is None or len(df) < 10:
            return None, None

        # Simple approach: use recent highs and lows
        high = df['High'].tail(30).max()
        low = df['Low'].tail(30).min()

        resistance = float(high)
        support = float(low)

        return support, resistance

    def _generate_summary(self, analysis: Dict[str, Any]) -> str:
        """Generate market summary."""
        current = analysis.get("current_price", "N/A")
        trend = analysis.get("trend", "unknown")
        change_1m = analysis.get("price_change_1m", {}).get("change_pct", 0)
        source = analysis.get("data_source", "unknown")

        summary = f"Current price: ${current:.2f}" if isinstance(current, (int, float)) else f"Current price: {current}. "
        summary += f"Trend: {trend.replace('_', ' ')}. "
        summary += f"1-month change: {change_1m:+.2f}%."
        summary += f" [Source: {source}]"

        return summary
