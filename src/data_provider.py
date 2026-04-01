"""OpenBB Data Provider — centralized data layer for all market research agents."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


class OpenBBDataProvider:
    """Unified data service backed by the OpenBB Platform SDK (v4.7+).

    Wraps synchronous OpenBB calls in ``asyncio.to_thread()`` so agents can
    ``await`` them without blocking the event loop.  Results are held in a
    simple TTL cache keyed by ``(method_name, ticker, extra_params)``.

    Provider stack (configured via ``Config``):
        - Equities: FMP > yfinance
        - Macro: FRED
        - Options: CBOE > yfinance
        - News: FMP > Benzinga
        - Technical: local compute via ``openbb-technical``
    """

    # TTL values in seconds
    TTL_QUOTE = 300            # 5 minutes
    TTL_PRICE_HISTORY = 300    # 5 minutes
    TTL_FUNDAMENTALS = 86400   # 24 hours
    TTL_TECHNICAL = 300        # 5 minutes
    TTL_MACRO = 86400          # 24 hours
    TTL_OPTIONS = 900          # 15 minutes
    TTL_NEWS = 3600            # 1 hour
    TTL_TRANSCRIPT = 86400     # 24 hours
    TTL_ESTIMATES = 86400      # 24 hours
    TTL_OWNERSHIP = 86400      # 24 hours

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (result, expiry_ts)
        self._obb = None  # lazy-initialized

    # ------------------------------------------------------------------
    # Lazy init — import openbb only when first needed
    # ------------------------------------------------------------------

    def _ensure_obb(self):
        """Import and configure the OpenBB SDK on first use."""
        if self._obb is not None:
            return
        try:
            # Workaround for OpenBB SDK bug (GH #7113): the auto-generated
            # wrapper modules import OBBject_* types from provider_interface,
            # but those types are only created dynamically when
            # ProviderInterface() is instantiated.  We inject them into the
            # module namespace before the wrapper is loaded.
            import sys
            from openbb_core.app.provider_interface import ProviderInterface
            pi = ProviderInterface()
            pi_mod = sys.modules["openbb_core.app.provider_interface"]
            for name, annotation in pi.return_annotations.items():
                setattr(pi_mod, f"OBBject_{name}", annotation)

            from openbb import obb
            self._obb = obb

            fmp_key = self._config.get("FMP_API_KEY", "")
            fred_key = self._config.get("FRED_API_KEY", "")

            if fmp_key:
                obb.user.credentials.fmp_api_key = fmp_key
            if fred_key:
                obb.user.credentials.fred_api_key = fred_key

            logger.info("OpenBB SDK initialized (FMP=%s, FRED=%s)",
                        "yes" if fmp_key else "no",
                        "yes" if fred_key else "no")
        except ImportError:
            logger.warning("openbb package not installed — data provider will return None for all calls")
            self._obb = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, method: str, ticker: str = "", **kwargs) -> str:
        extra = "|".join(f"{k}={v}" for k, v in sorted(kwargs.items())) if kwargs else ""
        return f"{method}:{ticker}:{extra}"

    def _cache_get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        result, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            return None
        return result

    def _cache_put(self, key: str, value: Any, ttl: float):
        self._cache[key] = (value, time.time() + ttl)

    # ------------------------------------------------------------------
    # Public async methods
    # ------------------------------------------------------------------

    async def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch latest quote for *ticker*."""
        ck = self._cache_key("quote", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_quote, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_QUOTE)
        return result

    async def get_price_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch OHLCV price history for *ticker*."""
        ck = self._cache_key("price_history", ticker, period=period)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_price_history, ticker, period)
        if result is not None:
            self._cache_put(ck, result, self.TTL_PRICE_HISTORY)
        return result

    async def get_company_overview(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch company profile and key metrics for *ticker*."""
        ck = self._cache_key("company_overview", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_company_overview, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch financial statements (balance sheet, income, cash flow)."""
        ck = self._cache_key("financials", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_financials, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_earnings(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch earnings history for *ticker*."""
        ck = self._cache_key("earnings", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_earnings, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_technical_indicators(
        self, ticker: str, price_data: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Compute technical indicators locally from price data."""
        ck = self._cache_key("technical", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        if price_data is None:
            price_data = await self.get_price_history(ticker, period="1y")

        if price_data is None or price_data.empty:
            return None

        result = await asyncio.to_thread(self._sync_get_technical_indicators, price_data)
        if result is not None:
            self._cache_put(ck, result, self.TTL_TECHNICAL)
        return result

    async def get_macro_indicators(self) -> Optional[Dict[str, Any]]:
        """Fetch US macro indicators from FRED (ticker-independent, cached 24h)."""
        ck = self._cache_key("macro")
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        fred_key = self._config.get("FRED_API_KEY", "")
        if not fred_key:
            logger.info("No FRED_API_KEY — macro indicators unavailable")
            return None

        result = await asyncio.to_thread(self._sync_get_macro_indicators)
        if result is not None:
            self._cache_put(ck, result, self.TTL_MACRO)
        return result

    async def get_options_chain(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch options chain for *ticker*."""
        ck = self._cache_key("options", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_options_chain, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_OPTIONS)
        return result

    async def get_news(self, ticker: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Fetch company news for *ticker*."""
        ck = self._cache_key("news", ticker, limit=limit)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await asyncio.to_thread(self._sync_get_news, ticker, limit)
        if result is not None:
            self._cache_put(ck, result, self.TTL_NEWS)
        return result

    async def get_earnings_transcript(self, ticker: str, quarter: int = 0, year: int = 0) -> Optional[Dict[str, Any]]:
        """Fetch earnings call transcript for *ticker* from FMP.

        Args:
            ticker: Stock ticker symbol.
            quarter: Fiscal quarter (1-4). If 0, fetches the most recent available.
            year: Fiscal year. If 0, fetches the most recent available.

        Returns:
            Dict with transcript content and metadata, or None.
        """
        ck = self._cache_key("transcript", ticker, quarter=quarter, year=year)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        result = await self._async_get_earnings_transcript(ticker, quarter, year)
        if result is not None:
            self._cache_put(ck, result, self.TTL_TRANSCRIPT)
        return result

    async def get_earnings_transcripts(self, ticker: str, num_quarters: int = 2) -> List[Dict[str, Any]]:
        """Fetch the N most recent earnings call transcripts for *ticker*.

        Args:
            ticker: Stock ticker symbol.
            num_quarters: Number of most recent transcripts to fetch (default 2).

        Returns:
            List of transcript dicts (most recent first), or empty list.
        """
        ck = self._cache_key("transcripts_multi", ticker, num_quarters=num_quarters)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached

        fmp_key = self._config.get("FMP_API_KEY", "")
        if not fmp_key:
            return []

        try:
            # Fetch transcript date list
            list_url = f"https://financialmodelingprep.com/stable/earning-call-transcript-dates?symbol={ticker}&apikey={fmp_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(list_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return []
                    entries = await resp.json(content_type=None)

            if not entries or not isinstance(entries, list):
                return []

            # Fetch each transcript
            transcripts = []
            for entry in entries[:num_quarters]:
                q = entry.get("quarter") or entry.get("period", 0)
                y = entry.get("year") or entry.get("fiscalYear", 0)
                if q == 0 or y == 0:
                    continue
                transcript = await self._async_get_earnings_transcript(ticker, q, y)
                if transcript:
                    transcripts.append(transcript)

            if transcripts:
                self._cache_put(ck, transcripts, self.TTL_TRANSCRIPT)
            return transcripts

        except Exception as e:
            logger.warning("FMP multi-quarter transcript fetch failed for %s: %s", ticker, e)
            return []

    async def _async_get_earnings_transcript(
        self, ticker: str, quarter: int = 0, year: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Fetch earnings call transcript directly from FMP REST API (async)."""
        fmp_key = self._config.get("FMP_API_KEY", "")
        if not fmp_key:
            logger.info("No FMP_API_KEY — earnings transcripts unavailable")
            return None

        try:
            # If quarter/year not specified, fetch the transcript list first to get most recent
            if quarter == 0 or year == 0:
                list_url = f"https://financialmodelingprep.com/stable/earning-call-transcript-dates?symbol={ticker}&apikey={fmp_key}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(list_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            logger.warning("FMP transcript list returned status %s for %s", resp.status, ticker)
                            return None
                        entries = await resp.json(content_type=None)

                if not entries or not isinstance(entries, list):
                    logger.info("No earnings transcripts available for %s", ticker)
                    return None

                # Pick the most recent entry (stable API uses "fiscalYear" instead of "year")
                latest = entries[0]
                quarter = latest.get("quarter") or latest.get("period", 0)
                year = latest.get("year") or latest.get("fiscalYear", 0)

                if quarter == 0 or year == 0:
                    logger.warning("FMP transcript list missing quarter/year for %s", ticker)
                    return None

            # Fetch the actual transcript (stable API)
            url = (
                f"https://financialmodelingprep.com/stable/earning-call-transcript"
                f"?symbol={ticker}&quarter={quarter}&year={year}&apikey={fmp_key}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 402:
                        logger.info("FMP transcript endpoint requires paid plan (402) for %s", ticker)
                        return None
                    if resp.status != 200:
                        logger.warning("FMP transcript fetch returned status %s for %s", resp.status, ticker)
                        return None
                    data = await resp.json(content_type=None)

            if not data:
                return None

            # FMP returns a list with one entry
            transcript_entry = data[0] if isinstance(data, list) else data
            content = transcript_entry.get("content", "")

            if not content:
                return None

            # Smart truncation: keep intro + Q&A section (most valuable part)
            max_chars = 16000
            if len(content) > max_chars:
                intro = content[:4000]
                # Find Q&A section start in the latter 2/3 of the transcript
                qa_start = -1
                for marker in ("Question-and-Answer", "Q&A Session", "Operator\n"):
                    idx = content.find(marker, len(content) // 3)
                    if idx != -1:
                        qa_start = idx
                        break
                if qa_start == -1:
                    # No marker found — take the last 10K chars as likely Q&A
                    qa_start = max(len(content) - 10000, 4000)
                qa_section = content[qa_start:qa_start + 10000]
                content = intro + "\n\n[... prepared remarks truncated ...]\n\n" + qa_section

            return {
                "quarter": quarter,
                "year": year,
                "date": transcript_entry.get("date", ""),
                "content": content,
                "symbol": ticker,
                "data_source": "fmp",
            }

        except Exception as e:
            logger.warning("FMP earnings transcript fetch failed for %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # FMP Ultimate endpoints (analyst, ownership, ratios, segments)
    # ------------------------------------------------------------------

    async def get_analyst_estimates(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch analyst consensus estimates (price targets) for *ticker*."""
        ck = self._cache_key("analyst_estimates", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_analyst_estimates, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_ESTIMATES)
        return result

    async def get_price_targets(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch individual analyst price targets for *ticker*."""
        ck = self._cache_key("price_targets", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_price_targets, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_ESTIMATES)
        return result

    async def get_ratios_ttm(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive TTM financial ratios for *ticker*."""
        ck = self._cache_key("ratios_ttm", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_ratios_ttm, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_insider_trading(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch insider trading activity for *ticker*."""
        ck = self._cache_key("insider_trading", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_insider_trading, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_OWNERSHIP)
        return result

    async def get_share_statistics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch share float and outstanding shares for *ticker*."""
        ck = self._cache_key("share_stats", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_share_statistics, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_OWNERSHIP)
        return result

    async def get_management(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch key executives for *ticker*."""
        ck = self._cache_key("management", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_management, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_revenue_segments(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch product and geographic revenue segmentation for *ticker*."""
        ck = self._cache_key("revenue_segments", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_revenue_segments, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_peers(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch stock peers for *ticker*."""
        ck = self._cache_key("peers", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(self._sync_get_peers, ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_financial_growth(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch financial growth rates for *ticker* (direct FMP stable API)."""
        ck = self._cache_key("financial_growth", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await self._async_get_financial_growth(ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    async def get_dcf_valuation(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch DCF valuation for *ticker* (direct FMP stable API)."""
        ck = self._cache_key("dcf", ticker)
        cached = self._cache_get(ck)
        if cached is not None:
            return cached
        result = await self._async_get_dcf_valuation(ticker)
        if result is not None:
            self._cache_put(ck, result, self.TTL_FUNDAMENTALS)
        return result

    # ------------------------------------------------------------------
    # Direct FMP stable REST API methods (async, no OpenBB wrapper)
    # ------------------------------------------------------------------

    async def _async_get_financial_growth(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch financial growth rates from FMP /stable/financial-growth."""
        fmp_key = self._config.get("FMP_API_KEY", "")
        if not fmp_key:
            return None
        try:
            url = f"https://financialmodelingprep.com/stable/financial-growth?symbol={ticker}&limit=4&apikey={fmp_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("FMP financial-growth returned %s for %s", resp.status, ticker)
                        return None
                    data = await resp.json(content_type=None)
            if not data or not isinstance(data, list):
                return None
            latest = data[0]
            return {
                "revenue_growth": latest.get("revenueGrowth"),
                "gross_profit_growth": latest.get("grossProfitGrowth"),
                "operating_income_growth": latest.get("operatingIncomeGrowth"),
                "net_income_growth": latest.get("netIncomeGrowth"),
                "eps_growth": latest.get("epsgrowth"),
                "eps_diluted_growth": latest.get("epsdilutedGrowth"),
                "operating_cf_growth": latest.get("operatingCashFlowGrowth"),
                "free_cf_growth": latest.get("freeCashFlowGrowth"),
                "rd_expense_growth": latest.get("rdexpenseGrowth"),
                "ten_y_revenue_growth_per_share": latest.get("tenYRevenueGrowthPerShare"),
                "five_y_revenue_growth_per_share": latest.get("fiveYRevenueGrowthPerShare"),
                "three_y_revenue_growth_per_share": latest.get("threeYRevenueGrowthPerShare"),
                "ten_y_net_income_growth_per_share": latest.get("tenYNetIncomeGrowthPerShare"),
                "five_y_net_income_growth_per_share": latest.get("fiveYNetIncomeGrowthPerShare"),
                "fiscal_year": latest.get("fiscalYear"),
                "period": latest.get("period"),
                "data_source": "fmp",
            }
        except Exception as e:
            logger.warning("FMP financial-growth fetch failed for %s: %s", ticker, e)
            return None

    async def _async_get_dcf_valuation(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch DCF valuation from FMP /stable/discounted-cash-flow."""
        fmp_key = self._config.get("FMP_API_KEY", "")
        if not fmp_key:
            return None
        try:
            url = f"https://financialmodelingprep.com/stable/discounted-cash-flow?symbol={ticker}&apikey={fmp_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("FMP DCF returned %s for %s", resp.status, ticker)
                        return None
                    data = await resp.json(content_type=None)
            if not data:
                return None
            entry = data[0] if isinstance(data, list) else data
            return {
                "dcf": entry.get("dcf"),
                "stock_price": entry.get("Stock Price"),
                "date": entry.get("date"),
                "data_source": "fmp",
            }
        except Exception as e:
            logger.warning("FMP DCF fetch failed for %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # Synchronous implementations (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _sync_get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.price.quote(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            data = result.results
            # Handle list result (some providers return list)
            row = data[0] if isinstance(data, list) else data
            df = result.to_df() if hasattr(result, "to_df") else None
            if df is not None and not df.empty:
                row_dict = df.iloc[0].to_dict()
            else:
                row_dict = row.__dict__ if hasattr(row, "__dict__") else {}

            return {
                "current_price": row_dict.get("last_price") or row_dict.get("close") or row_dict.get("price"),
                "open": row_dict.get("open"),
                "high": row_dict.get("high"),
                "low": row_dict.get("low"),
                "volume": row_dict.get("volume"),
                "change_pct": row_dict.get("change_percent"),
                "previous_close": row_dict.get("prev_close") or row_dict.get("previous_close"),
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB quote fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_price_history(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            # Map period string to start_date
            import datetime as _dt
            period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
            days = period_days.get(period, 365)
            start = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime("%Y-%m-%d")

            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.price.historical(
                symbol=ticker, start_date=start, provider=provider
            )
            if result is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            # Normalize column names to match existing agent expectations
            col_map = {}
            for col in df.columns:
                lower = col.lower()
                if lower == "open":
                    col_map[col] = "Open"
                elif lower == "high":
                    col_map[col] = "High"
                elif lower == "low":
                    col_map[col] = "Low"
                elif lower == "close":
                    col_map[col] = "Close"
                elif lower == "volume":
                    col_map[col] = "Volume"
            df = df.rename(columns=col_map)
            # Ensure index is DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                if "date" in [c.lower() for c in df.columns]:
                    date_col = [c for c in df.columns if c.lower() == "date"][0]
                    df[date_col] = pd.to_datetime(df[date_col])
                    df = df.set_index(date_col)
                else:
                    df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            return df
        except Exception as e:
            logger.warning("OpenBB price history fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_company_overview(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            profile_result = self._obb.equity.profile(symbol=ticker, provider=provider)

            overview = {}
            if profile_result and profile_result.results:
                df = profile_result.to_df()
                if df is not None and not df.empty:
                    row = df.iloc[0].to_dict()
                    overview = {
                        "longName": row.get("name") or row.get("company_name", ""),
                        "sector": row.get("sector", ""),
                        "industry": row.get("industry", ""),
                        "marketCap": row.get("market_cap") or row.get("mkt_cap"),
                        "description": row.get("description", ""),
                        "country": row.get("country", ""),
                        "exchange": row.get("exchange", ""),
                    }

            # Try to get key metrics
            try:
                metrics_result = self._obb.equity.fundamental.metrics(
                    symbol=ticker, provider=provider
                )
                if metrics_result and metrics_result.results:
                    mdf = metrics_result.to_df()
                    if mdf is not None and not mdf.empty:
                        mrow = mdf.iloc[0].to_dict()
                        overview.update({
                            "PE": mrow.get("pe_ratio") or mrow.get("pe_ratio_ttm"),
                            "forwardPE": mrow.get("forward_pe"),
                            "PB": mrow.get("pb_ratio") or mrow.get("price_to_book"),
                            "dividendYield": mrow.get("dividend_yield"),
                            "ROE": mrow.get("roe") or mrow.get("return_on_equity"),
                            "profitMargin": mrow.get("net_profit_margin") or mrow.get("profit_margin"),
                            "operatingMargin": mrow.get("operating_margin"),
                            "debtToEquity": mrow.get("debt_to_equity"),
                        })
            except Exception as e:
                logger.debug("Metrics fetch failed for %s: %s", ticker, e)

            overview["data_source"] = "openbb"
            return overview if overview.get("longName") else None
        except Exception as e:
            logger.warning("OpenBB company overview fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            financials = {}

            # Balance sheet
            try:
                bs = self._obb.equity.fundamental.balance(symbol=ticker, provider=provider)
                if bs and bs.results:
                    financials["balance_sheet"] = bs.to_df().to_dict("records")
            except Exception:
                financials["balance_sheet"] = []

            # Income statement
            try:
                inc = self._obb.equity.fundamental.income(symbol=ticker, provider=provider)
                if inc and inc.results:
                    financials["income_statement"] = inc.to_df().to_dict("records")
            except Exception:
                financials["income_statement"] = []

            # Cash flow
            try:
                cf = self._obb.equity.fundamental.cash(symbol=ticker, provider=provider)
                if cf and cf.results:
                    financials["cash_flow"] = cf.to_df().to_dict("records")
            except Exception:
                financials["cash_flow"] = []

            financials["data_source"] = "openbb"
            return financials
        except Exception as e:
            logger.warning("OpenBB financials fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_earnings(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.fundamental.historical_eps(
                symbol=ticker, provider=provider
            )
            if result is None or result.results is None:
                return None

            df = result.to_df()
            if df is None or df.empty:
                return None

            records = df.to_dict("records")
            latest = records[0] if records else {}

            return {
                "eps_history": records[:8],  # Last 8 quarters
                "latest_eps": latest.get("actual_eps") or latest.get("eps_actual"),
                "announcement_date": str(latest.get("date", "")),
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB earnings fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_technical_indicators(self, price_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Compute technical indicators locally using pandas (no openbb-technical dependency)."""
        try:
            if price_data is None or price_data.empty or len(price_data) < 26:
                return None

            close = price_data["Close"]

            # RSI (14-period)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_series = 100 - (100 / (1 + rs))
            rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

            # MACD (12, 26, 9)
            exp12 = close.ewm(span=12, adjust=False).mean()
            exp26 = close.ewm(span=26, adjust=False).mean()
            macd_line = exp12 - exp26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            macd_val = float(macd_line.iloc[-1])
            signal_val = float(signal_line.iloc[-1])
            hist_val = float(histogram.iloc[-1])
            if hist_val > 0 and macd_val > signal_val:
                macd_interp = "bullish"
            elif hist_val < 0 and macd_val < signal_val:
                macd_interp = "bearish"
            else:
                macd_interp = "neutral"

            # Bollinger Bands (20, 2)
            sma20 = close.rolling(window=20).mean()
            std20 = close.rolling(window=20).std()
            upper_band = float((sma20 + 2 * std20).iloc[-1])
            middle_band = float(sma20.iloc[-1])
            lower_band = float((sma20 - 2 * std20).iloc[-1])

            # SMAs
            sma_10 = float(close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else None
            sma_20 = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None
            sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

            return {
                "rsi": rsi_val,
                "macd": {
                    "macd_line": macd_val,
                    "signal_line": signal_val,
                    "histogram": hist_val,
                    "interpretation": macd_interp,
                },
                "bbands": {
                    "upper_band": upper_band,
                    "middle_band": middle_band,
                    "lower_band": lower_band,
                },
                "sma_10": sma_10,
                "sma_20": sma_20,
                "sma_50": sma_50,
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("Technical indicator computation failed: %s", e)
            return None

    def _sync_get_macro_indicators(self) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            series_ids = {
                "fed_funds": "FEDFUNDS",
                "treasury_10y": "DGS10",
                "treasury_2y": "DGS2",
                "unemployment": "UNRATE",
                "cpi": "CPIAUCSL",
                "gdp": "GDP",
                "inflation": "T10YIE",  # 10-Year Breakeven Inflation Rate
            }

            macro_data = {}
            for name, series_id in series_ids.items():
                try:
                    result = self._obb.economy.fred_series(
                        symbol=series_id, provider="fred"
                    )
                    if result and result.results:
                        df = result.to_df()
                        if df is not None and not df.empty:
                            # Get last few data points
                            recent = df.tail(6)
                            entries = []
                            for idx, row in recent.iterrows():
                                date_str = str(idx) if isinstance(idx, str) else idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                                val = row.get("value") if "value" in row else row.iloc[0]
                                if val is not None and not pd.isna(val):
                                    entries.append({"date": date_str, "value": float(val)})
                            # Reverse so most recent is first (matching AV format)
                            entries.reverse()
                            macro_data[name] = entries if entries else None
                        else:
                            macro_data[name] = None
                    else:
                        macro_data[name] = None
                except Exception as e:
                    logger.debug("FRED series %s fetch failed: %s", series_id, e)
                    macro_data[name] = None

            macro_data["data_source"] = "openbb"
            return macro_data
        except Exception as e:
            logger.warning("OpenBB macro indicators fetch failed: %s", e)
            return None

    def _sync_get_options_chain(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_OPTIONS_PROVIDER", "yfinance")
            result = self._obb.derivatives.options.chains(
                symbol=ticker, provider=provider
            )
            if result is None or result.results is None:
                return None

            df = result.to_df()
            if df is None or df.empty:
                return None

            # Normalize to match the contract format agents expect
            contracts = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                contracts.append({
                    "contractID": row_dict.get("contract_symbol", ""),
                    "symbol": ticker,
                    "expiration": str(row_dict.get("expiration", "")),
                    "strike": str(row_dict.get("strike", 0)),
                    "type": row_dict.get("option_type", "").lower(),
                    "last": str(row_dict.get("last_price", 0)),
                    "mark": str(row_dict.get("mark", 0)),
                    "bid": str(row_dict.get("bid", 0)),
                    "ask": str(row_dict.get("ask", 0)),
                    "volume": str(int(row_dict.get("volume", 0) or 0)),
                    "open_interest": str(int(row_dict.get("open_interest", 0) or 0)),
                    "impliedVolatility": str(row_dict.get("implied_volatility", 0) or 0),
                })

            expirations = sorted(set(c["expiration"] for c in contracts))
            calls = [c for c in contracts if c["type"] == "call"]
            puts = [c for c in contracts if c["type"] == "put"]

            total_call_vol = sum(int(float(c.get("volume", 0))) for c in calls)
            total_put_vol = sum(int(float(c.get("volume", 0))) for c in puts)
            pc_ratio = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None

            return {
                "contracts": contracts,
                "expirations": expirations,
                "put_call_ratio": pc_ratio,
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB options chain fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_news(self, ticker: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_NEWS_PROVIDER", "fmp")
            result = self._obb.news.company(
                symbol=ticker, limit=limit, provider=provider
            )
            if result is None or result.results is None:
                return None

            df = result.to_df()
            if df is None or df.empty:
                return None

            articles = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                pub_date = row_dict.get("date") or row_dict.get("published_at")
                if hasattr(pub_date, "isoformat"):
                    pub_date = pub_date.isoformat()

                articles.append({
                    "title": row_dict.get("title", ""),
                    "source": row_dict.get("source", "") or row_dict.get("site", ""),
                    "url": row_dict.get("url", "") or row_dict.get("link", ""),
                    "published_at": str(pub_date) if pub_date else "",
                    "description": row_dict.get("text", "") or row_dict.get("description", ""),
                    "content": row_dict.get("text", "") or row_dict.get("content", ""),
                    "relevance_score": 0.8,  # OpenBB news is pre-filtered by ticker
                    "data_source": "openbb",
                })

            return articles
        except Exception as e:
            logger.warning("OpenBB news fetch failed for %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # FMP Ultimate sync implementations
    # ------------------------------------------------------------------

    def _sync_get_analyst_estimates(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.estimates.consensus(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            row = df.iloc[0].to_dict()
            return {
                "target_high": row.get("target_high"),
                "target_low": row.get("target_low"),
                "target_consensus": row.get("target_consensus"),
                "target_median": row.get("target_median"),
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB analyst estimates fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_price_targets(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.estimates.price_target(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            targets = []
            for _, row in df.head(20).iterrows():
                row_dict = row.to_dict()
                pub_date = row_dict.get("published_date")
                if hasattr(pub_date, "isoformat"):
                    pub_date = pub_date.isoformat()
                targets.append({
                    "analyst_name": row_dict.get("analyst_name", ""),
                    "analyst_firm": row_dict.get("analyst_firm", ""),
                    "price_target": row_dict.get("price_target"),
                    "adj_price_target": row_dict.get("adj_price_target"),
                    "price_when_posted": row_dict.get("price_when_posted"),
                    "published_date": str(pub_date) if pub_date else "",
                    "news_title": row_dict.get("news_title", ""),
                })
            return targets
        except Exception as e:
            logger.warning("OpenBB price targets fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_ratios_ttm(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.fundamental.ratios(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            row = df.iloc[0].to_dict()
            return {
                "gross_profit_margin": row.get("gross_profit_margin"),
                "operating_profit_margin": row.get("operating_profit_margin"),
                "net_profit_margin": row.get("net_profit_margin"),
                "ebitda_margin": row.get("ebitda_margin"),
                "current_ratio": row.get("current_ratio"),
                "quick_ratio": row.get("quick_ratio"),
                "cash_ratio": row.get("cash_ratio"),
                "debt_to_equity": row.get("debt_to_equity"),
                "debt_to_assets": row.get("debt_to_assets"),
                "interest_coverage": row.get("interest_coverage_ratio"),
                "price_to_earnings": row.get("price_to_earnings"),
                "price_to_book": row.get("price_to_book"),
                "price_to_sales": row.get("price_to_sales"),
                "price_to_free_cash_flow": row.get("price_to_free_cash_flow"),
                "price_earnings_to_growth": row.get("price_to_earnings_growth"),
                "forward_pe_to_growth": row.get("forward_price_to_earnings_growth"),
                "dividend_yield": row.get("dividend_yield"),
                "payout_ratio": row.get("dividend_payout_ratio"),
                "inventory_turnover": row.get("inventory_turnover"),
                "receivables_turnover": row.get("receivables_turnover"),
                "asset_turnover": row.get("asset_turnover"),
                "free_cash_flow_per_share": row.get("free_cash_flow_per_share"),
                "operating_cash_flow_per_share": row.get("operating_cash_flow_per_share"),
                "revenue_per_share": row.get("revenue_per_share"),
                "net_income_per_share": row.get("net_income_per_share"),
                "enterprise_value_multiple": row.get("enterprise_value_multiple"),
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB ratios TTM fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_insider_trading(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.ownership.insider_trading(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            trades = []
            for _, row in df.head(50).iterrows():
                row_dict = row.to_dict()
                tx_date = row_dict.get("transaction_date") or row_dict.get("filing_date")
                if hasattr(tx_date, "isoformat"):
                    tx_date = tx_date.isoformat()
                trades.append({
                    "owner_name": row_dict.get("owner_name", ""),
                    "owner_title": row_dict.get("owner_title", ""),
                    "transaction_type": row_dict.get("transaction_type", ""),
                    "shares": row_dict.get("securities_transacted"),
                    "price": row_dict.get("price"),
                    "value": row_dict.get("value"),
                    "date": str(tx_date) if tx_date else "",
                })
            return trades
        except Exception as e:
            logger.warning("OpenBB insider trading fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_share_statistics(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.ownership.share_statistics(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            row = df.iloc[0].to_dict()
            return {
                "free_float": row.get("free_float"),
                "float_shares": row.get("float_shares"),
                "outstanding_shares": row.get("outstanding_shares"),
                "data_source": "openbb",
            }
        except Exception as e:
            logger.warning("OpenBB share statistics fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_management(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.fundamental.management(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            executives = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                executives.append({
                    "name": row_dict.get("name", ""),
                    "title": row_dict.get("title", ""),
                    "pay": row_dict.get("pay"),
                    "gender": row_dict.get("gender", ""),
                    "year_born": row_dict.get("year_born"),
                })
            return executives
        except Exception as e:
            logger.warning("OpenBB management fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_revenue_segments(self, ticker: str) -> Optional[Dict[str, Any]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            segments = {"data_source": "openbb"}

            # Product segments
            try:
                result = self._obb.equity.fundamental.revenue_per_segment(
                    symbol=ticker, provider=provider
                )
                if result and result.results:
                    df = result.to_df()
                    if df is not None and not df.empty:
                        # Get most recent fiscal year
                        latest_year = df["fiscal_year"].max()
                        latest = df[df["fiscal_year"] == latest_year]
                        product = {}
                        for _, row in latest.iterrows():
                            line = row.get("business_line", "Unknown")
                            rev = row.get("revenue")
                            if line and rev is not None:
                                product[line] = rev
                        segments["product"] = product
            except Exception as e:
                logger.debug("Revenue per segment failed for %s: %s", ticker, e)

            # Geographic segments
            try:
                result = self._obb.equity.fundamental.revenue_per_geography(
                    symbol=ticker, provider=provider
                )
                if result and result.results:
                    df = result.to_df()
                    if df is not None and not df.empty:
                        latest_year = df["fiscal_year"].max()
                        latest = df[df["fiscal_year"] == latest_year]
                        geo = {}
                        for _, row in latest.iterrows():
                            region = row.get("region", "Unknown")
                            rev = row.get("revenue")
                            if region and rev is not None:
                                geo[region] = rev
                        segments["geography"] = geo
            except Exception as e:
                logger.debug("Revenue per geography failed for %s: %s", ticker, e)

            return segments if ("product" in segments or "geography" in segments) else None
        except Exception as e:
            logger.warning("OpenBB revenue segments fetch failed for %s: %s", ticker, e)
            return None

    def _sync_get_peers(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        self._ensure_obb()
        if self._obb is None:
            return None
        try:
            provider = self._config.get("OPENBB_EQUITY_PROVIDER", "fmp")
            result = self._obb.equity.compare.peers(symbol=ticker, provider=provider)
            if result is None or result.results is None:
                return None
            df = result.to_df()
            if df is None or df.empty:
                return None
            peers = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                peers.append({
                    "symbol": row_dict.get("symbol", ""),
                    "name": row_dict.get("name", ""),
                    "market_cap": row_dict.get("market_cap"),
                })
            return peers
        except Exception as e:
            logger.warning("OpenBB peers fetch failed for %s: %s", ticker, e)
            return None
