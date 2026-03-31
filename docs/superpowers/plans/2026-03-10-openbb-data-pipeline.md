# OpenBB Data Pipeline Migration - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-agent Alpha Vantage + yfinance data-fetching code with a centralized `OpenBBDataProvider` service backed by OpenBB Platform SDK.

**Architecture:** New `src/data_provider.py` wraps all OpenBB calls with `asyncio.to_thread()`, TTL caching, and error handling. Agents delegate `fetch_data()` to this service. `analyze()` methods unchanged.

**Tech Stack:** OpenBB Platform v4.7+, openbb-technical, FMP (primary equities), FRED (macro), yfinance (fallback)

**Spec:** `docs/superpowers/specs/2026-03-10-openbb-data-pipeline-design.md`

---

## Chunk 1: Foundation — Config, Dependencies, and Data Provider

### Task 1: Add OpenBB Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add openbb packages to requirements.txt**

Add after the `tavily-python` line:

```
openbb>=4.7.0,<5.0
openbb-technical>=4.7.0,<5.0
```

- [ ] **Step 2: Install dependencies**

Run: `source venv/bin/activate && pip install openbb>=4.7.0,<5.0 openbb-technical>=4.7.0,<5.0`
Expected: Successful installation (openbb pulls in many transitive deps)

- [ ] **Step 3: Verify import works**

Run: `source venv/bin/activate && python -c "from openbb import obb; print('OpenBB OK')"`
Expected: `OpenBB OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openbb and openbb-technical dependencies"
```

---

### Task 2: Add OpenBB Config Variables

**Files:**
- Modify: `src/config.py:14-15` (API keys section), `src/config.py:138-140` (AV rate limit section)
- Modify: `.env.example`

- [ ] **Step 1: Add FMP and FRED API key config vars**

In `src/config.py`, after the `TAVILY_API_KEY` line (line 22), add:

```python
    # OpenBB Data Provider Keys
    FMP_API_KEY = os.getenv("FMP_API_KEY", "")
    FRED_API_KEY = os.getenv("FRED_API_KEY", "")

    # OpenBB Provider Preferences (override defaults)
    OPENBB_EQUITY_PROVIDER = os.getenv("OPENBB_EQUITY_PROVIDER", "fmp").split("#")[0].strip()
    OPENBB_MACRO_PROVIDER = os.getenv("OPENBB_MACRO_PROVIDER", "fred").split("#")[0].strip()
    OPENBB_OPTIONS_PROVIDER = os.getenv("OPENBB_OPTIONS_PROVIDER", "yfinance").split("#")[0].strip()
    OPENBB_NEWS_PROVIDER = os.getenv("OPENBB_NEWS_PROVIDER", "fmp").split("#")[0].strip()
```

- [ ] **Step 2: Update validate_config() optional key warnings**

In `src/config.py` `validate_config()` method, after the `TAVILY_API_KEY` check (~line 186), add:

```python
        if not cls.FMP_API_KEY:
            optional_keys.append("FMP_API_KEY")
        if not cls.FRED_API_KEY:
            optional_keys.append("FRED_API_KEY")
```

- [ ] **Step 3: Update .env.example with new variables**

Add to `.env.example`:

```bash
# OpenBB Data Provider Keys
FMP_API_KEY=               # Financial Modeling Prep (free: 250 req/day) - primary equity data
FRED_API_KEY=              # Federal Reserve Economic Data (free: 120 req/min) - macro data

# OpenBB Provider Preferences (optional overrides)
# OPENBB_EQUITY_PROVIDER=fmp
# OPENBB_MACRO_PROVIDER=fred
# OPENBB_OPTIONS_PROVIDER=yfinance
# OPENBB_NEWS_PROVIDER=fmp
```

- [ ] **Step 4: Commit**

```bash
git add src/config.py .env.example
git commit -m "feat: add OpenBB provider config variables (FMP, FRED)"
```

---

### Task 3: Create OpenBBDataProvider — Core Infrastructure

**Files:**
- Create: `src/data_provider.py`
- Create: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing test for data provider initialization**

Create `tests/test_data_provider.py`:

```python
"""Tests for OpenBBDataProvider."""

import pytest
import time
from unittest.mock import patch, MagicMock


class TestOpenBBDataProviderInit:
    """Test data provider initialization."""

    def test_init_sets_credentials(self):
        """Provider sets FMP and FRED credentials on OpenBB."""
        config = {"FMP_API_KEY": "test_fmp_key", "FRED_API_KEY": "test_fred_key"}

        with patch("src.data_provider.obb") as mock_obb:
            mock_obb.user.credentials = MagicMock()
            from src.data_provider import OpenBBDataProvider
            provider = OpenBBDataProvider(config)
            assert mock_obb.user.credentials.fmp_api_key == "test_fmp_key"
            assert mock_obb.user.credentials.fred_api_key == "test_fred_key"

    def test_init_without_keys_still_works(self):
        """Provider initializes even without API keys (yfinance fallback)."""
        config = {"FMP_API_KEY": "", "FRED_API_KEY": ""}

        with patch("src.data_provider.obb") as mock_obb:
            mock_obb.user.credentials = MagicMock()
            from src.data_provider import OpenBBDataProvider
            provider = OpenBBDataProvider(config)
            assert provider is not None


class TestTTLCache:
    """Test the TTL cache behavior."""

    def test_cache_stores_and_retrieves(self):
        """Cache returns stored value within TTL."""
        config = {"FMP_API_KEY": "", "FRED_API_KEY": ""}

        with patch("src.data_provider.obb") as mock_obb:
            mock_obb.user.credentials = MagicMock()
            from src.data_provider import OpenBBDataProvider
            provider = OpenBBDataProvider(config)
            provider._cache_put("test_key", {"data": "value"}, ttl=300)
            result = provider._cache_get("test_key")
            assert result == {"data": "value"}

    def test_cache_returns_none_for_expired(self):
        """Cache returns None for expired entries."""
        config = {"FMP_API_KEY": "", "FRED_API_KEY": ""}

        with patch("src.data_provider.obb") as mock_obb:
            mock_obb.user.credentials = MagicMock()
            from src.data_provider import OpenBBDataProvider
            provider = OpenBBDataProvider(config)
            provider._cache_put("test_key", {"data": "value"}, ttl=0)
            # TTL=0 means already expired
            result = provider._cache_get("test_key")
            assert result is None

    def test_cache_miss(self):
        """Cache returns None for unknown keys."""
        config = {"FMP_API_KEY": "", "FRED_API_KEY": ""}

        with patch("src.data_provider.obb") as mock_obb:
            mock_obb.user.credentials = MagicMock()
            from src.data_provider import OpenBBDataProvider
            provider = OpenBBDataProvider(config)
            result = provider._cache_get("nonexistent")
            assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.data_provider'`

- [ ] **Step 3: Write minimal data provider with init and cache**

Create `src/data_provider.py`:

```python
"""Centralized data access layer backed by OpenBB Platform."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    from openbb import obb
except ImportError:
    obb = None  # Allow tests/imports to work without openbb installed

logger = logging.getLogger(__name__)

# TTL constants (seconds)
TTL_QUOTE = 300          # 5 minutes
TTL_PRICE_HISTORY = 300  # 5 minutes
TTL_FUNDAMENTALS = 86400 # 24 hours
TTL_MACRO = 86400        # 24 hours
TTL_OPTIONS = 900        # 15 minutes
TTL_NEWS = 3600          # 1 hour


class OpenBBDataProvider:
    """Centralized data provider wrapping OpenBB Platform SDK.

    All methods are async — synchronous OpenBB calls are wrapped in
    asyncio.to_thread() to avoid blocking the event loop.

    Provider priority: FMP (equities) > yfinance (fallback), FRED (macro).
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._cache: Dict[str, tuple] = {}  # key → (value, expiry_timestamp)

        if obb is not None:
            fmp_key = config.get("FMP_API_KEY", "")
            fred_key = config.get("FRED_API_KEY", "")
            if fmp_key:
                obb.user.credentials.fmp_api_key = fmp_key
            if fred_key:
                obb.user.credentials.fred_api_key = fred_key

        self._equity_provider = config.get("OPENBB_EQUITY_PROVIDER", "fmp")
        self._macro_provider = config.get("OPENBB_MACRO_PROVIDER", "fred")
        self._options_provider = config.get("OPENBB_OPTIONS_PROVIDER", "yfinance")
        self._news_provider = config.get("OPENBB_NEWS_PROVIDER", "fmp")

    # ── Cache helpers ───────────────────────────────────────

    def _cache_get(self, key: str) -> Optional[Any]:
        """Get a value from the TTL cache, or None if missing/expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            return None
        return value

    def _cache_put(self, key: str, value: Any, ttl: int) -> None:
        """Store a value in the TTL cache."""
        self._cache[key] = (value, time.time() + ttl)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_data_provider.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add OpenBBDataProvider core with TTL cache"
```

---

### Task 4: Data Provider — get_quote() and get_price_history()

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing tests for get_quote and get_price_history**

Add to `tests/test_data_provider.py`:

```python
import asyncio


@pytest.fixture
def mock_obb():
    """Create a data provider with mocked OpenBB."""
    with patch("src.data_provider.obb") as mock:
        mock.user.credentials = MagicMock()
        config = {"FMP_API_KEY": "test", "FRED_API_KEY": "test"}
        from src.data_provider import OpenBBDataProvider
        provider = OpenBBDataProvider(config)
        yield provider, mock


class TestGetQuote:
    """Test get_quote method."""

    @pytest.mark.asyncio
    async def test_get_quote_returns_normalized_dict(self, mock_obb):
        provider, mock = mock_obb
        # Mock OBBject result
        mock_result = MagicMock()
        mock_result.results = [MagicMock(
            last_price=150.25,
            open=149.00,
            high=151.00,
            low=148.50,
            volume=1000000,
            change_percent=0.83,
            prev_close=149.01,
        )]
        mock.equity.price.quote.return_value = mock_result

        result = await provider.get_quote("AAPL")
        assert result is not None
        assert result["current_price"] == 150.25
        assert result["data_source"] == "openbb"

    @pytest.mark.asyncio
    async def test_get_quote_returns_none_on_failure(self, mock_obb):
        provider, mock = mock_obb
        mock.equity.price.quote.side_effect = Exception("API error")

        result = await provider.get_quote("AAPL")
        assert result is None


class TestGetPriceHistory:
    """Test get_price_history method."""

    @pytest.mark.asyncio
    async def test_get_price_history_returns_dataframe(self, mock_obb):
        provider, mock = mock_obb
        mock_result = MagicMock()
        mock_result.to_df.return_value = pd.DataFrame({
            "open": [149.0], "high": [151.0], "low": [148.0],
            "close": [150.0], "volume": [1000000],
        }, index=pd.to_datetime(["2025-01-01"]))
        mock.equity.price.historical.return_value = mock_result

        result = await provider.get_price_history("AAPL")
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "close" in result.columns or "Close" in result.columns

    @pytest.mark.asyncio
    async def test_get_price_history_uses_cache(self, mock_obb):
        provider, mock = mock_obb
        mock_result = MagicMock()
        df = pd.DataFrame({"close": [150.0]}, index=pd.to_datetime(["2025-01-01"]))
        mock_result.to_df.return_value = df
        mock.equity.price.historical.return_value = mock_result

        await provider.get_price_history("AAPL")
        await provider.get_price_history("AAPL")
        # Second call should hit cache, not OpenBB
        assert mock.equity.price.historical.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_provider.py::TestGetQuote -v`
Expected: FAIL with `AttributeError: 'OpenBBDataProvider' object has no attribute 'get_quote'`

- [ ] **Step 3: Implement get_quote and get_price_history**

Add to `src/data_provider.py`:

```python
    # ── Equity Price ────────────────────────────────────────

    async def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch current price quote for a ticker.

        Returns:
            Normalized dict with currentPrice, open, high, low, volume, etc.
            or None on failure.
        """
        cache_key = f"quote:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await asyncio.to_thread(
                obb.equity.price.quote, symbol=ticker, provider=self._equity_provider
            )
            if not result or not result.results:
                return None

            q = result.results[0]
            normalized = {
                "currentPrice": getattr(q, "last_price", None) or getattr(q, "price", None),
                "regularMarketPrice": getattr(q, "last_price", None) or getattr(q, "price", None),
                "previousClose": getattr(q, "prev_close", None) or getattr(q, "previous_close", None),
                "open": getattr(q, "open", None),
                "regularMarketOpen": getattr(q, "open", None),
                "dayHigh": getattr(q, "high", None),
                "dayLow": getattr(q, "low", None),
                "volume": getattr(q, "volume", None),
                "change_percent": getattr(q, "change_percent", None),
                "data_source": "openbb",
            }
            self._cache_put(cache_key, normalized, TTL_QUOTE)
            return normalized
        except Exception as e:
            logger.warning(f"get_quote({ticker}) failed: {e}")
            return None

    async def get_price_history(
        self, ticker: str, period: str = "1y"
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV price history for a ticker.

        Args:
            ticker: Stock symbol
            period: Lookback period (e.g. '1y', '6m', '3m')

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            indexed by date, or None on failure.
        """
        cache_key = f"price_history:{ticker}:{period}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # Map period string to start_date
        from datetime import datetime, timedelta
        period_days = {"1y": 365, "6m": 180, "3m": 90, "1m": 30}
        days = period_days.get(period, 365)
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = await asyncio.to_thread(
                obb.equity.price.historical,
                symbol=ticker,
                start_date=start_date,
                provider=self._equity_provider,
            )
            if result is None:
                return None

            df = result.to_df()
            if df is None or df.empty:
                return None

            # Normalize column names to match existing agent expectations (capitalized)
            col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            self._cache_put(cache_key, df, TTL_PRICE_HISTORY)
            return df
        except Exception as e:
            logger.warning(f"get_price_history({ticker}, {period}) failed: {e}")
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_provider.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add get_quote() and get_price_history() to data provider"
```

---

### Task 5: Data Provider — get_company_overview(), get_financials(), get_earnings()

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing tests for fundamentals methods**

Add to `tests/test_data_provider.py`:

```python
class TestGetCompanyOverview:
    @pytest.mark.asyncio
    async def test_returns_normalized_dict(self, mock_obb):
        provider, mock = mock_obb
        # Mock profile
        profile_result = MagicMock()
        profile_result.results = [MagicMock(
            name="Apple Inc", sector="Technology", industry="Consumer Electronics",
            market_cap=3000000000000, beta=1.2,
        )]
        mock.equity.profile.return_value = profile_result
        # Mock metrics
        metrics_result = MagicMock()
        metrics_result.results = [MagicMock(
            pe_ratio=30.5, forward_pe=28.0, peg_ratio=2.1,
            price_to_book=45.0, price_to_sales=8.5,
            return_on_equity=1.5, return_on_assets=0.3,
            dividend_yield=0.005, eps_ttm=6.50,
        )]
        mock.equity.fundamental.metrics.return_value = metrics_result

        result = await provider.get_company_overview("AAPL")
        assert result is not None
        assert result["longName"] == "Apple Inc"
        assert result["sector"] == "Technology"
        assert result["data_source"] == "openbb"


class TestGetFinancials:
    @pytest.mark.asyncio
    async def test_returns_three_statements(self, mock_obb):
        provider, mock = mock_obb
        for attr in ["balance", "income", "cash"]:
            mock_result = MagicMock()
            mock_result.to_df.return_value = pd.DataFrame({"value": [100]})
            getattr(mock.equity.fundamental, attr).return_value = mock_result

        result = await provider.get_financials("AAPL")
        assert result is not None
        assert "balance_sheet" in result
        assert "income_statement" in result
        assert "cash_flow" in result


class TestGetEarnings:
    @pytest.mark.asyncio
    async def test_returns_earnings_history(self, mock_obb):
        provider, mock = mock_obb
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(actual_eps=6.50, estimated_eps=6.30, date="2025-01-30"),
        ]
        mock.equity.fundamental.historical_eps.return_value = mock_result

        result = await provider.get_earnings("AAPL")
        assert result is not None
        assert "eps_history" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_provider.py::TestGetCompanyOverview -v`
Expected: FAIL

- [ ] **Step 3: Implement fundamentals methods**

Add to `src/data_provider.py`:

```python
    # ── Fundamentals ────────────────────────────────────────

    async def get_company_overview(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch company profile and key metrics.

        Returns:
            Dict with keys matching existing agent expectations:
            longName, sector, industry, marketCap, trailingPE, forwardPE,
            pegRatio, priceToBook, returnOnEquity, dividendYield, etc.
        """
        cache_key = f"overview:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            profile_result, metrics_result = await asyncio.gather(
                asyncio.to_thread(
                    obb.equity.profile, symbol=ticker, provider=self._equity_provider
                ),
                asyncio.to_thread(
                    obb.equity.fundamental.metrics, symbol=ticker, provider=self._equity_provider
                ),
                return_exceptions=True,
            )

            normalized = {"data_source": "openbb"}

            if not isinstance(profile_result, Exception) and profile_result and profile_result.results:
                p = profile_result.results[0]
                normalized.update({
                    "longName": getattr(p, "name", None),
                    "sector": getattr(p, "sector", None),
                    "industry": getattr(p, "industry", None),
                    "marketCap": getattr(p, "market_cap", None) or getattr(p, "mkt_cap", None),
                    "beta": getattr(p, "beta", None),
                })

            if not isinstance(metrics_result, Exception) and metrics_result and metrics_result.results:
                m = metrics_result.results[0]
                normalized.update({
                    "trailingPE": getattr(m, "pe_ratio", None),
                    "forwardPE": getattr(m, "forward_pe", None),
                    "pegRatio": getattr(m, "peg_ratio", None),
                    "priceToBook": getattr(m, "price_to_book", None),
                    "priceToSalesTrailing12Months": getattr(m, "price_to_sales", None),
                    "returnOnEquity": getattr(m, "return_on_equity", None),
                    "returnOnAssets": getattr(m, "return_on_assets", None),
                    "dividendYield": getattr(m, "dividend_yield", None),
                    "trailingEps": getattr(m, "eps_ttm", None),
                })

            if len(normalized) <= 1:  # Only data_source
                return None

            self._cache_put(cache_key, normalized, TTL_FUNDAMENTALS)
            return normalized
        except Exception as e:
            logger.warning(f"get_company_overview({ticker}) failed: {e}")
            return None

    async def get_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch balance sheet, income statement, and cash flow.

        Returns:
            Dict with balance_sheet, income_statement, cash_flow DataFrames.
        """
        cache_key = f"financials:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            balance, income, cash = await asyncio.gather(
                asyncio.to_thread(
                    obb.equity.fundamental.balance, symbol=ticker, provider=self._equity_provider
                ),
                asyncio.to_thread(
                    obb.equity.fundamental.income, symbol=ticker, provider=self._equity_provider
                ),
                asyncio.to_thread(
                    obb.equity.fundamental.cash, symbol=ticker, provider=self._equity_provider
                ),
                return_exceptions=True,
            )

            result = {"data_source": "openbb"}

            for name, data in [("balance_sheet", balance), ("income_statement", income), ("cash_flow", cash)]:
                if isinstance(data, Exception) or data is None:
                    result[name] = None
                else:
                    try:
                        result[name] = data.to_df()
                    except Exception:
                        result[name] = None

            self._cache_put(cache_key, result, TTL_FUNDAMENTALS)
            return result
        except Exception as e:
            logger.warning(f"get_financials({ticker}) failed: {e}")
            return None

    async def get_earnings(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch historical EPS data.

        Returns:
            Dict with eps_history list and latest_eps.
        """
        cache_key = f"earnings:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await asyncio.to_thread(
                obb.equity.fundamental.historical_eps,
                symbol=ticker,
                provider=self._equity_provider,
            )
            if not result or not result.results:
                return None

            eps_history = []
            for item in result.results:
                eps_history.append({
                    "date": str(getattr(item, "date", "")),
                    "actual_eps": getattr(item, "actual_eps", None),
                    "estimated_eps": getattr(item, "estimated_eps", None),
                })

            normalized = {
                "eps_history": eps_history,
                "latest_eps": eps_history[0].get("actual_eps") if eps_history else None,
                "data_source": "openbb",
            }
            self._cache_put(cache_key, normalized, TTL_FUNDAMENTALS)
            return normalized
        except Exception as e:
            logger.warning(f"get_earnings({ticker}) failed: {e}")
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_provider.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add fundamentals methods to data provider"
```

---

### Task 6: Data Provider — get_technical_indicators()

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_data_provider.py`:

```python
class TestGetTechnicalIndicators:
    @pytest.mark.asyncio
    async def test_computes_indicators_from_price_data(self, mock_obb):
        provider, mock = mock_obb
        # Create realistic price DataFrame (200 days)
        import numpy as np
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        prices = 150 + np.cumsum(np.random.randn(200) * 2)
        df = pd.DataFrame({
            "Open": prices - 1, "High": prices + 2,
            "Low": prices - 2, "Close": prices, "Volume": [1000000] * 200,
        }, index=dates)

        # Mock obb.technical methods
        for method_name in ["rsi", "macd", "bbands", "sma"]:
            mock_tech = MagicMock()
            mock_tech.to_df.return_value = pd.DataFrame({"value": [50.0]})
            getattr(mock.technical, method_name).return_value = mock_tech

        result = await provider.get_technical_indicators("AAPL", price_data=df)
        assert result is not None
        assert "rsi" in result
        assert "macd" in result
        assert "bbands" in result
        assert "sma_10" in result or "sma" in str(result)

    @pytest.mark.asyncio
    async def test_returns_none_without_price_data(self, mock_obb):
        provider, mock = mock_obb
        result = await provider.get_technical_indicators("AAPL", price_data=None)
        assert result is None
```

- [ ] **Step 2: Run to verify failure, then implement**

Add to `src/data_provider.py`:

```python
    # ── Technical Indicators (local compute) ────────────────

    async def get_technical_indicators(
        self, ticker: str, price_data: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Compute technical indicators from price history.

        Uses OpenBB's technical module for local computation (no API calls).
        If price_data is not provided, fetches it via get_price_history().

        Returns:
            Dict matching the av_indicators structure expected by TechnicalAgent:
            {rsi, macd: {macd_line, signal_line, histogram, interpretation},
             bbands: {upper_band, middle_band, lower_band},
             sma_10, sma_20, sma_50}
        """
        if price_data is None:
            price_data = await self.get_price_history(ticker, period="6m")
        if price_data is None or price_data.empty:
            return None

        # Ensure lowercase columns for OpenBB technical module
        df = price_data.copy()
        col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Need 'close' column for indicators
        close_col = "close" if "close" in df.columns else "Close"
        if close_col not in df.columns:
            return None

        config = self._config
        result = {"data_source": "openbb"}

        try:
            # RSI
            rsi_period = config.get("RSI_PERIOD", 14)
            rsi_result = await asyncio.to_thread(
                obb.technical.rsi, data=df, target="close", length=rsi_period
            )
            rsi_df = rsi_result.to_df() if rsi_result else None
            rsi_val = float(rsi_df.iloc[-1].iloc[-1]) if rsi_df is not None and not rsi_df.empty else None
            result["rsi"] = rsi_val

            # MACD
            macd_fast = config.get("MACD_FAST", 12)
            macd_slow = config.get("MACD_SLOW", 26)
            macd_signal = config.get("MACD_SIGNAL", 9)
            macd_result = await asyncio.to_thread(
                obb.technical.macd, data=df, target="close",
                fast=macd_fast, slow=macd_slow, signal=macd_signal
            )
            macd_df = macd_result.to_df() if macd_result else None
            if macd_df is not None and not macd_df.empty:
                last_row = macd_df.iloc[-1]
                macd_cols = macd_df.columns.tolist()
                # OpenBB MACD returns columns like MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
                macd_val = float(last_row.iloc[0]) if len(macd_cols) > 0 else 0
                signal_val = float(last_row.iloc[1]) if len(macd_cols) > 1 else 0
                hist_val = float(last_row.iloc[2]) if len(macd_cols) > 2 else 0

                if hist_val > 0 and macd_val > signal_val:
                    interpretation = "bullish"
                elif hist_val < 0 and macd_val < signal_val:
                    interpretation = "bearish"
                else:
                    interpretation = "neutral"

                result["macd"] = {
                    "macd_line": macd_val,
                    "signal_line": signal_val,
                    "histogram": hist_val,
                    "interpretation": interpretation,
                }
            else:
                result["macd"] = {"macd_line": 0, "signal_line": 0, "histogram": 0, "interpretation": "neutral"}

            # Bollinger Bands
            bb_period = config.get("BB_PERIOD", 20)
            bb_std = config.get("BB_STD", 2)
            bb_result = await asyncio.to_thread(
                obb.technical.bbands, data=df, target="close", length=bb_period, std=bb_std
            )
            bb_df = bb_result.to_df() if bb_result else None
            if bb_df is not None and not bb_df.empty:
                last_row = bb_df.iloc[-1]
                bb_cols = bb_df.columns.tolist()
                result["bbands"] = {
                    "upper_band": float(last_row.iloc[0]) if len(bb_cols) > 0 else None,
                    "middle_band": float(last_row.iloc[1]) if len(bb_cols) > 1 else None,
                    "lower_band": float(last_row.iloc[2]) if len(bb_cols) > 2 else None,
                }
            else:
                result["bbands"] = {"upper_band": None, "middle_band": None, "lower_band": None}

            # SMAs
            for period in [10, 20, 50]:
                sma_result = await asyncio.to_thread(
                    obb.technical.sma, data=df, target="close", length=period
                )
                sma_df = sma_result.to_df() if sma_result else None
                if sma_df is not None and not sma_df.empty:
                    result[f"sma_{period}"] = float(sma_df.iloc[-1].iloc[-1])
                else:
                    result[f"sma_{period}"] = None

            return result
        except Exception as e:
            logger.warning(f"get_technical_indicators({ticker}) failed: {e}")
            return None
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_provider.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add get_technical_indicators() to data provider"
```

---

### Task 7: Data Provider — get_macro_indicators()

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_data_provider.py`:

```python
class TestGetMacroIndicators:
    @pytest.mark.asyncio
    async def test_returns_all_indicators(self, mock_obb):
        provider, mock = mock_obb
        # Mock FRED series calls
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(date="2025-01-01", value=5.33),
            MagicMock(date="2024-12-01", value=5.33),
        ]
        mock.economy.fred_series.return_value = mock_result

        result = await provider.get_macro_indicators()
        assert result is not None
        assert "federal_funds_rate" in result
        assert "treasury_yield_10y" in result
        assert "cpi" in result

    @pytest.mark.asyncio
    async def test_returns_none_without_fred_key(self, mock_obb):
        provider, mock = mock_obb
        provider._config["FRED_API_KEY"] = ""
        result = await provider.get_macro_indicators()
        assert result is None
```

- [ ] **Step 2: Run to verify failure, then implement**

Add to `src/data_provider.py`:

```python
    # ── Macro Indicators (FRED) ─────────────────────────────

    async def get_macro_indicators(self) -> Optional[Dict[str, Any]]:
        """Fetch US macroeconomic indicators from FRED.

        Returns:
            Dict with series data matching MacroAgent's expected format:
            {federal_funds_rate, cpi, real_gdp, treasury_yield_10y,
             treasury_yield_2y, unemployment, inflation}
            Each value is a list of {date, value} dicts (most recent first),
            or None.
        """
        if not self._config.get("FRED_API_KEY"):
            return None

        cache_key = "macro:all"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # FRED series IDs
        series_map = {
            "federal_funds_rate": "FEDFUNDS",
            "cpi": "CPIAUCSL",
            "real_gdp": "GDPC1",
            "treasury_yield_10y": "DGS10",
            "treasury_yield_2y": "DGS2",
            "unemployment": "UNRATE",
            "inflation": "T10YIE",  # 10-Year Breakeven Inflation Rate
        }

        async def _fetch_series(name: str, series_id: str):
            try:
                result = await asyncio.to_thread(
                    obb.economy.fred_series,
                    symbol=series_id,
                    provider="fred",
                )
                if not result or not result.results:
                    return name, None

                entries = []
                for item in result.results[:6]:  # Last 6 data points
                    entries.append({
                        "date": str(getattr(item, "date", "")),
                        "value": float(getattr(item, "value", 0)),
                    })
                return name, entries if entries else None
            except Exception as e:
                logger.warning(f"FRED fetch {name} ({series_id}) failed: {e}")
                return name, None

        tasks = [_fetch_series(name, sid) for name, sid in series_map.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        macro_data = {"data_source": "openbb"}
        for res in results:
            if isinstance(res, Exception):
                continue
            name, data = res
            macro_data[name] = data

        fetched = sum(1 for k, v in macro_data.items() if k != "data_source" and v is not None)
        logger.info(f"Fetched {fetched}/{len(series_map)} macro indicators from FRED")

        self._cache_put(cache_key, macro_data, TTL_MACRO)
        return macro_data
```

- [ ] **Step 3: Run tests, verify pass, commit**

Run: `python -m pytest tests/test_data_provider.py -v`

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add get_macro_indicators() to data provider (FRED)"
```

---

### Task 8: Data Provider — get_options_chain() and get_news()

**Files:**
- Modify: `src/data_provider.py`
- Modify: `tests/test_data_provider.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_data_provider.py`:

```python
class TestGetOptionsChain:
    @pytest.mark.asyncio
    async def test_returns_contracts(self, mock_obb):
        provider, mock = mock_obb
        mock_result = MagicMock()
        mock_result.to_df.return_value = pd.DataFrame({
            "strike": [150.0, 155.0],
            "option_type": ["call", "put"],
            "volume": [100, 200],
            "open_interest": [1000, 2000],
            "implied_volatility": [0.25, 0.30],
        })
        mock.derivatives.options.chains.return_value = mock_result

        result = await provider.get_options_chain("AAPL")
        assert result is not None
        assert "contracts" in result
        assert len(result["contracts"]) == 2


class TestGetNews:
    @pytest.mark.asyncio
    async def test_returns_articles(self, mock_obb):
        provider, mock = mock_obb
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(
                title="Apple beats earnings",
                date="2025-01-30",
                text="Apple reported...",
                url="https://example.com/1",
                images=None,
            ),
        ]
        mock.news.company.return_value = mock_result

        result = await provider.get_news("AAPL")
        assert result is not None
        assert len(result) >= 1
        assert result[0]["title"] == "Apple beats earnings"
```

- [ ] **Step 2: Implement get_options_chain and get_news**

Add to `src/data_provider.py`:

```python
    # ── Options ─────────────────────────────────────────────

    async def get_options_chain(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch options chain data.

        Returns:
            Dict with contracts list matching OptionsAgent expected format.
        """
        cache_key = f"options:{ticker}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await asyncio.to_thread(
                obb.derivatives.options.chains,
                symbol=ticker,
                provider=self._options_provider,
            )
            if result is None:
                return None

            df = result.to_df()
            if df is None or df.empty:
                return None

            contracts = []
            for _, row in df.iterrows():
                contracts.append({
                    "strike": float(row.get("strike", 0)),
                    "type": str(row.get("option_type", row.get("contract_type", ""))).lower(),
                    "volume": int(row.get("volume", 0) or 0),
                    "open_interest": int(row.get("open_interest", 0) or 0),
                    "impliedVolatility": float(row.get("implied_volatility", 0) or 0),
                    "last": float(row.get("last_price", row.get("last_trade_price", 0)) or 0),
                    "bid": float(row.get("bid", 0) or 0),
                    "ask": float(row.get("ask", 0) or 0),
                    "expiration": str(row.get("expiration", "")),
                })

            normalized = {
                "contracts": contracts,
                "source": "openbb",
                "data_source": "openbb",
            }
            self._cache_put(cache_key, normalized, TTL_OPTIONS)
            return normalized
        except Exception as e:
            logger.warning(f"get_options_chain({ticker}) failed: {e}")
            return None

    # ── News ────────────────────────────────────────────────

    async def get_news(self, ticker: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Fetch company news articles.

        Returns:
            List of article dicts matching NewsAgent expected format.
        """
        cache_key = f"news:{ticker}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await asyncio.to_thread(
                obb.news.company,
                symbol=ticker,
                limit=limit,
                provider=self._news_provider,
            )
            if not result or not result.results:
                return None

            articles = []
            for item in result.results:
                articles.append({
                    "title": getattr(item, "title", ""),
                    "source": getattr(item, "source", "") or getattr(item, "publisher", ""),
                    "url": getattr(item, "url", ""),
                    "published_at": str(getattr(item, "date", "")),
                    "description": getattr(item, "text", "") or getattr(item, "content", ""),
                    "content": getattr(item, "text", "") or getattr(item, "content", ""),
                    "relevance_score": 0.5,  # Default; Tavily/agent will re-score
                    "data_source": "openbb",
                })

            self._cache_put(cache_key, articles, TTL_NEWS)
            return articles
        except Exception as e:
            logger.warning(f"get_news({ticker}) failed: {e}")
            return None
```

- [ ] **Step 3: Run tests, verify pass, commit**

Run: `python -m pytest tests/test_data_provider.py -v`

```bash
git add src/data_provider.py tests/test_data_provider.py
git commit -m "feat: add get_options_chain() and get_news() to data provider"
```

---

## Chunk 2: Wire Up Orchestrator and BaseAgent

### Task 9: Update BaseAgent — Remove AV, Add Data Provider

**Files:**
- Modify: `src/agents/base_agent.py`
- Modify: `tests/test_agents/test_base_agent.py`

- [ ] **Step 1: Remove AV-specific code from BaseAgent**

In `src/agents/base_agent.py`:

1. Remove `import aiohttp` (line 11) — will be re-added if needed for http_session
2. Remove `AV_BASE_URL` class attribute (line 17)
3. Remove `_av_request()` method (lines 90-160)
4. Remove `_do_av_request()` method (lines 162-189)
5. Add `_data_provider` attribute initialization in `__init__()`:

```python
        self._data_provider = None  # Injected by orchestrator
        self._http_session = None   # Lightweight session for non-OpenBB HTTP calls
```

Keep: `_retry_fetch()`, `_run_blocking()`, `execute()`, all get_* methods.

- [ ] **Step 2: Update base_agent tests**

In `tests/test_agents/test_base_agent.py`:
- Remove all tests that reference `_av_request`, `_do_av_request`, `AV_BASE_URL`
- Keep tests for `_retry_fetch`, `_run_blocking`, `execute`, `get_agent_type`
- Add a test verifying `_data_provider` attribute exists after init

- [ ] **Step 3: Run base_agent tests to verify they pass**

Run: `python -m pytest tests/test_agents/test_base_agent.py -v`
Expected: All remaining tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/base_agent.py tests/test_agents/test_base_agent.py
git commit -m "refactor: remove AV infrastructure from BaseAgent, add data_provider attribute"
```

---

### Task 10: Update Orchestrator — Inject Data Provider

**Files:**
- Modify: `src/orchestrator.py`

- [ ] **Step 1: Update orchestrator imports and constructor**

In `src/orchestrator.py`:

1. Replace imports (lines 23-24):
   ```python
   # Remove:
   from .av_rate_limiter import AVRateLimiter
   from .av_cache import AVCache
   # Add:
   from .data_provider import OpenBBDataProvider
   ```

2. Update `__init__()` constructor (lines 46-77):
   - Replace `rate_limiter` and `av_cache` params with `data_provider`:
   ```python
   def __init__(
       self,
       config: Optional[Dict[str, Any]] = None,
       db_manager: Optional[DatabaseManager] = None,
       progress_callback: Optional[Callable] = None,
       data_provider: Optional[OpenBBDataProvider] = None,
   ):
   ```
   - Replace rate_limiter/av_cache init with:
   ```python
       self._data_provider = data_provider or OpenBBDataProvider(self.config)
       self._shared_session: Optional[aiohttp.ClientSession] = None
   ```

3. Update `_inject_shared_resources()` (lines 139-143):
   ```python
   def _inject_shared_resources(self, agent):
       """Inject shared resources into an agent instance."""
       agent._data_provider = self._data_provider
       agent._http_session = self._shared_session
   ```

4. Keep `_create_shared_session()` and `_close_shared_session()` — still needed for Twitter/Tavily HTTP calls.

- [ ] **Step 2: Run orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: Some failures from constructor changes. Fix mock references in test file.

- [ ] **Step 3: Update orchestrator tests**

In `tests/test_orchestrator.py`, replace `rate_limiter=...` and `av_cache=...` constructor args with `data_provider=MagicMock()`.

- [ ] **Step 4: Run tests, verify pass, commit**

Run: `python -m pytest tests/test_orchestrator.py -v`

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "refactor: orchestrator injects data_provider instead of AV rate_limiter/cache"
```

---

### Task 11: Update api.py and scheduler.py

**Files:**
- Modify: `src/api.py`
- Modify: `src/scheduler.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_scheduler.py`

- [ ] **Step 1: Update api.py**

1. Remove imports (line 36-37):
   ```python
   # Remove:
   from .av_rate_limiter import AVRateLimiter
   from .av_cache import AVCache
   # Add:
   from .data_provider import OpenBBDataProvider
   ```

2. Replace module-level singleton instantiation (lines 89-93):
   ```python
   # Remove:
   av_rate_limiter = AVRateLimiter(...)
   av_cache = AVCache()
   # Add:
   data_provider = OpenBBDataProvider(Orchestrator({})._get_config_dict() if True else {})
   ```

   Better approach — lazy init in lifespan:
   ```python
   data_provider: Optional[OpenBBDataProvider] = None
   ```
   Then in `lifespan()`, initialize `data_provider = OpenBBDataProvider(config_dict)`.

3. At every `Orchestrator(...)` callsite, replace `rate_limiter=av_rate_limiter, av_cache=av_cache` with `data_provider=data_provider`.

- [ ] **Step 2: Update scheduler.py**

1. Remove imports (lines 13-14):
   ```python
   from .av_rate_limiter import AVRateLimiter
   from .av_cache import AVCache
   ```
   Add: `from .data_provider import OpenBBDataProvider`

2. Update constructor (lines 28-37):
   - Replace `rate_limiter: AVRateLimiter` and `av_cache: AVCache` params with `data_provider: OpenBBDataProvider`
   - Store as `self.data_provider = data_provider`

3. Update `_run_schedule_analysis()` (lines 446-450):
   - Replace `rate_limiter=self.rate_limiter, av_cache=self.av_cache` with `data_provider=self.data_provider`

- [ ] **Step 3: Update test files**

In `tests/test_api.py` and `tests/test_scheduler.py`:
- Replace AV mock references with `data_provider=MagicMock()`
- Remove any `AVRateLimiter`/`AVCache` fixture usage

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_api.py tests/test_scheduler.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/api.py src/scheduler.py tests/test_api.py tests/test_scheduler.py
git commit -m "refactor: api.py and scheduler.py use data_provider instead of AV infrastructure"
```

---

## Chunk 3: Migrate Agents (one by one)

### Task 12: Migrate MarketAgent

**Files:**
- Modify: `src/agents/market_agent.py`

- [ ] **Step 1: Rewrite fetch_data() to use data provider**

Replace the entire `fetch_data()` method and remove `_fetch_av_quote()` and `_fetch_av_daily()` methods. New `fetch_data()`:

```python
    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch market price data via OpenBB data provider."""
        result = {"ticker": self.ticker, "source": "unknown"}

        dp = self._data_provider
        if dp is None:
            raise Exception("No data provider available")

        # Fetch quote and history concurrently
        quote, history_full = await asyncio.gather(
            dp.get_quote(self.ticker),
            dp.get_price_history(self.ticker, period="1y"),
            return_exceptions=True,
        )
        if isinstance(quote, Exception):
            self.logger.warning(f"Quote fetch failed: {quote}")
            quote = None
        if isinstance(history_full, Exception):
            self.logger.warning(f"History fetch failed: {history_full}")
            history_full = None

        result["source"] = "openbb" if quote else "none"
        result["info"] = quote or {}

        # Slice history into timeframes
        if history_full is not None and not history_full.empty:
            now = pd.Timestamp.now()
            result["history_1y"] = history_full[history_full.index >= now - pd.Timedelta(days=365)]
            result["history_3m"] = history_full[history_full.index >= now - pd.Timedelta(days=90)]
            result["history_1m"] = history_full[history_full.index >= now - pd.Timedelta(days=30)]
        else:
            result["history_1y"] = None
            result["history_3m"] = None
            result["history_1m"] = None

        if not result["info"] and result["history_1y"] is None:
            raise Exception(f"Failed to fetch any market data for {self.ticker}")

        return result
```

Also remove `import yfinance as yf` and the `from datetime import datetime, timedelta` import (no longer needed).

- [ ] **Step 2: Run existing market agent tests**

Run: `python -m pytest tests/ -k "market" -v`
Expected: Tests may need mock updates. Fix any that reference `_av_request` or `_fetch_av_*`.

- [ ] **Step 3: Commit**

```bash
git add src/agents/market_agent.py
git commit -m "refactor: MarketAgent delegates to OpenBBDataProvider"
```

---

### Task 13: Migrate TechnicalAgent

**Files:**
- Modify: `src/agents/technical_agent.py`

- [ ] **Step 1: Rewrite fetch_data()**

Remove all `_fetch_av_*` methods (lines 24-235). Replace `fetch_data()`:

```python
    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch price data and compute technical indicators via data provider."""
        result = {"ticker": self.ticker, "source": "unknown"}

        dp = self._data_provider
        if dp is None:
            raise Exception("No data provider available")

        # Fetch price history (6 months for indicator computation)
        history = await dp.get_price_history(self.ticker, period="6m")

        if history is None or history.empty:
            raise Exception(f"No price data available for technical analysis of {self.ticker}")

        result["source"] = "openbb"
        result["history"] = history

        # Compute technical indicators locally via OpenBB
        indicators = await dp.get_technical_indicators(self.ticker, price_data=history)
        if indicators:
            result["av_indicators"] = indicators  # Populate av_indicators dict for analyze() branch

        return result
```

Remove `import yfinance as yf` and `import numpy as np` if no longer used.

- [ ] **Step 2: Run technical tests**

Run: `python -m pytest tests/ -k "technical" -v`

- [ ] **Step 3: Commit**

```bash
git add src/agents/technical_agent.py
git commit -m "refactor: TechnicalAgent uses data provider for price + local indicator compute"
```

---

### Task 14: Migrate MacroAgent

**Files:**
- Modify: `src/agents/macro_agent.py`

- [ ] **Step 1: Rewrite fetch_data()**

Remove all `_fetch_av_*` methods (lines 21-97). Replace `fetch_data()`:

```python
    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch macroeconomic data via data provider (FRED)."""
        dp = self._data_provider
        if dp is None:
            self.logger.info("No data provider available, skipping macro agent")
            return {"ticker": self.ticker, "source": "none", "data": {}}

        macro_data = await dp.get_macro_indicators()
        if macro_data is None:
            self.logger.info("No FRED API key or macro data unavailable")
            return {"ticker": self.ticker, "source": "none", "data": {}}

        self.logger.info("Fetched macroeconomic indicators via FRED")
        return {
            "ticker": self.ticker,
            "source": "fred",
            "federal_funds_rate": macro_data.get("federal_funds_rate"),
            "cpi": macro_data.get("cpi"),
            "real_gdp": macro_data.get("real_gdp"),
            "treasury_yield_10y": macro_data.get("treasury_yield_10y"),
            "treasury_yield_2y": macro_data.get("treasury_yield_2y"),
            "unemployment": macro_data.get("unemployment"),
            "inflation": macro_data.get("inflation"),
        }
```

Keep `_parse_av_series()` only if other code references it — otherwise remove.

- [ ] **Step 2: Update analyze() data_source**

In `analyze()` method (line 195), change `"data_source": "alpha_vantage"` to `"data_source": raw_data.get("source", "fred")`.

- [ ] **Step 3: Run macro tests, commit**

Run: `python -m pytest tests/ -k "macro" -v`

```bash
git add src/agents/macro_agent.py
git commit -m "refactor: MacroAgent uses FRED via data provider instead of AV"
```

---

### Task 15: Migrate FundamentalsAgent

**Files:**
- Modify: `src/agents/fundamentals_agent.py`

- [ ] **Step 1: Rewrite fetch_data() — AV part only**

Remove all `_fetch_av_*` methods. Replace the AV-first section of `fetch_data()` with data provider calls. **Keep** SEC EDGAR and Tavily context code.

New fetch_data() structure:
```python
    async def fetch_data(self) -> Dict[str, Any]:
        result = {"ticker": self.ticker, "source": "unknown"}
        dp = self._data_provider

        if dp:
            overview, financials, earnings = await asyncio.gather(
                dp.get_company_overview(self.ticker),
                dp.get_financials(self.ticker),
                dp.get_earnings(self.ticker),
                return_exceptions=True,
            )
            # Handle exceptions, normalize into result["info"], etc.
            # ... (merge overview dict into info, add earnings data)

            if overview and not isinstance(overview, Exception):
                result["source"] = "openbb"
                result["info"] = overview
                # Merge financials data if available
                # ...

        # Keep existing yfinance fallback if data_provider fails
        if result["source"] == "unknown":
            # ... existing yfinance + SEC EDGAR fallback code ...
            pass

        # Keep Tavily context fetch (unchanged)
        if self.config.get("TAVILY_CONTEXT_ENABLED", True):
            result["tavily_context"] = await self._fetch_tavily_context()

        return result
```

- [ ] **Step 2: Run fundamentals tests, commit**

```bash
git add src/agents/fundamentals_agent.py
git commit -m "refactor: FundamentalsAgent uses data provider (keeps SEC EDGAR + Tavily)"
```

---

### Task 16: Migrate OptionsAgent

**Files:**
- Modify: `src/agents/options_agent.py`

- [ ] **Step 1: Rewrite fetch_data()**

Remove `_fetch_av_realtime_options()` and `_fetch_av_historical_options()`. Replace fetch_data():

```python
    async def fetch_data(self) -> Dict[str, Any]:
        """Fetch options chain data via data provider."""
        dp = self._data_provider
        if dp is None:
            return {"ticker": self.ticker, "source": "none", "contracts": []}

        chain_data = await dp.get_options_chain(self.ticker)
        if chain_data and chain_data.get("contracts"):
            return {
                "ticker": self.ticker,
                "source": "openbb",
                "contracts": chain_data["contracts"],
            }

        self.logger.warning(f"No options data available for {self.ticker}")
        return {"ticker": self.ticker, "source": "none", "contracts": []}
```

- [ ] **Step 2: Update options agent tests**

In `tests/test_agents/test_options_agent.py`, replace AV mock patterns with data_provider mocks.

- [ ] **Step 3: Run tests, commit**

```bash
git add src/agents/options_agent.py tests/test_agents/test_options_agent.py
git commit -m "refactor: OptionsAgent uses data provider for options chain"
```

---

### Task 17: Migrate NewsAgent (Partial)

**Files:**
- Modify: `src/agents/news_agent.py`

- [ ] **Step 1: Replace AV NEWS_SENTIMENT and NewsAPI fallback with data provider**

In `fetch_data()`:
- Remove `_fetch_av_news()` method
- Remove `_fetch_from_newsapi()` method (or keep as last-resort fallback)
- Keep `_fetch_tavily_news()` as primary
- Keep `_fetch_twitter_posts()` as supplementary
- Replace AV/NewsAPI tier with `data_provider.get_news()`:

```python
    # In fetch_data(), after Tavily returns no articles:
    # Try OpenBB news (replaces AV NEWS_SENTIMENT)
    dp = self._data_provider
    if dp:
        obb_articles = await dp.get_news(self.ticker, limit=max_articles)
        if obb_articles:
            articles.extend(obb_articles)
            source = "openbb"

    # Only fall back to NewsAPI if both Tavily and OpenBB returned nothing
```

- [ ] **Step 2: Run news tests, commit**

```bash
git add src/agents/news_agent.py
git commit -m "refactor: NewsAgent uses data provider for news (keeps Tavily + Twitter)"
```

---

## Chunk 4: Cleanup and Final Verification

### Task 18: Delete AV Infrastructure Files

**Files:**
- Delete: `src/av_cache.py`
- Delete: `src/av_rate_limiter.py`
- Delete: `tests/test_av_cache.py`
- Delete: `tests/test_av_rate_limiter.py`

- [ ] **Step 1: Verify no remaining imports**

Run: `grep -r "av_cache\|av_rate_limiter\|AVCache\|AVRateLimiter" src/ tests/ --include="*.py"`
Expected: No matches (all references removed in previous tasks)

- [ ] **Step 2: Delete files**

```bash
git rm src/av_cache.py src/av_rate_limiter.py tests/test_av_cache.py tests/test_av_rate_limiter.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove AV cache and rate limiter (replaced by OpenBB data provider)"
```

---

### Task 19: Update Test Fixtures

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Replace AV fixtures with data provider fixtures**

1. Remove fixtures: `av_cache`, `av_rate_limiter`, `exhausted_rate_limiter`
2. Remove AV response fixtures: `av_global_quote_response`, `av_time_series_daily_response`, `av_news_sentiment_response`, `av_rsi_response`, `av_company_overview_response`, `av_macro_fed_funds_response`
3. Add data provider fixture:

```python
@pytest.fixture
def mock_data_provider():
    """Mock OpenBBDataProvider for agent tests."""
    from unittest.mock import AsyncMock, MagicMock
    provider = MagicMock()
    provider.get_quote = AsyncMock(return_value={
        "currentPrice": 150.0, "previousClose": 149.0,
        "open": 149.5, "dayHigh": 151.0, "dayLow": 148.5,
        "volume": 1000000, "data_source": "openbb",
    })
    provider.get_price_history = AsyncMock(return_value=pd.DataFrame({
        "Open": [149.0], "High": [151.0], "Low": [148.0],
        "Close": [150.0], "Volume": [1000000],
    }, index=pd.to_datetime(["2025-01-01"])))
    provider.get_company_overview = AsyncMock(return_value={
        "longName": "Apple Inc", "sector": "Technology",
        "data_source": "openbb",
    })
    provider.get_technical_indicators = AsyncMock(return_value={
        "rsi": 55.0, "macd": {"macd_line": 1.5, "signal_line": 1.0,
        "histogram": 0.5, "interpretation": "bullish"},
        "bbands": {"upper_band": 155.0, "middle_band": 150.0, "lower_band": 145.0},
        "sma_10": 150.0, "sma_20": 149.0, "sma_50": 148.0,
    })
    provider.get_macro_indicators = AsyncMock(return_value={
        "federal_funds_rate": [{"date": "2025-01-01", "value": 5.33}],
        "data_source": "openbb",
    })
    provider.get_options_chain = AsyncMock(return_value={
        "contracts": [], "data_source": "openbb",
    })
    provider.get_news = AsyncMock(return_value=[])
    return provider
```

4. Update `make_agent` factory:

```python
@pytest.fixture
def make_agent(test_config, mock_data_provider):
    def _make(agent_class, ticker="AAPL"):
        agent = agent_class(ticker, test_config)
        agent._data_provider = mock_data_provider
        agent._http_session = None
        return agent
    return _make
```

5. Remove `ALPHA_VANTAGE_API_KEY` from `test_config` fixture.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: Fix any remaining failures from AV references.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "refactor: replace AV test fixtures with data provider mocks"
```

---

### Task 20: Full Test Suite Verification

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run with coverage**

Run: `python -m pytest tests/ --cov=src --cov-report=term-missing`
Verify: `src/data_provider.py` has good coverage. No uncovered methods.

- [ ] **Step 3: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds (frontend unchanged)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete OpenBB data pipeline migration

Replace Alpha Vantage + yfinance data fetching with centralized
OpenBBDataProvider service. FMP as primary equity provider, FRED
for macro data, local technical indicator computation.

Key changes:
- New src/data_provider.py with TTL caching and async wrappers
- All 6 data agents delegate to data_provider
- Removed av_cache.py and av_rate_limiter.py
- ~22 AV calls/analysis reduced to 0 (FMP: ~9, FRED: ~7, local: 6)
- Tavily and Twitter integrations unchanged"
```

---

### Task 21: Update CLAUDE.md

- [ ] **Step 1: Update CLAUDE.md to reflect new architecture**

Key sections to update:
- Data Source Priority table: Replace AV references with FMP/FRED/OpenBB
- Agent Directory Structure descriptions
- Environment Setup: Replace `ALPHA_VANTAGE_API_KEY` with `FMP_API_KEY`, `FRED_API_KEY`
- Common Issues: Replace AV debugging section with OpenBB debugging
- Important Patterns: Update Orchestrator Pattern and Agent Base Class sections
- Performance Considerations: Update API call budget
- Quick Reference Commands: Update if needed

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for OpenBB data pipeline"
```
