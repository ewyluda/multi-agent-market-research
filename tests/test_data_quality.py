"""Data quality tests for all configured data provider endpoints.

Hits real APIs to verify data shape, field presence, freshness, and consistency.
Requires configured API keys (FMP, FRED, Tavily, etc.) — skips gracefully when missing.

Run:
    python -m pytest tests/test_data_quality.py -v
    python -m pytest tests/test_data_quality.py -v -k quote       # single endpoint
    python -m pytest tests/test_data_quality.py -v -k tavily      # tavily only
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import pytest

from src.config import Config
from src.data_provider import OpenBBDataProvider
from src.tavily_client import TavilyClient, TAVILY_AVAILABLE

logger = logging.getLogger(__name__)

# ─── Shared config & provider ───

TEST_TICKER = "AAPL"  # Highly liquid, all endpoints should have data


def _build_config() -> Dict[str, Any]:
    """Build a config dict from the real environment."""
    return {
        attr: getattr(Config, attr)
        for attr in dir(Config)
        if not attr.startswith("_") and not callable(getattr(Config, attr))
    }


@pytest.fixture(scope="module")
def config():
    return _build_config()


@pytest.fixture(scope="module")
def provider(config):
    return OpenBBDataProvider(config)


@pytest.fixture(scope="module")
def tavily(config):
    api_key = config.get("TAVILY_API_KEY", "")
    return TavilyClient(api_key)


# ─── Helper assertions ───


def assert_non_empty_string(val: Any, field: str):
    assert isinstance(val, str), f"{field} should be str, got {type(val).__name__}"
    assert len(val.strip()) > 0, f"{field} should not be empty"


def assert_positive_number(val: Any, field: str):
    assert val is not None, f"{field} should not be None"
    assert isinstance(val, (int, float)), f"{field} should be numeric, got {type(val).__name__}"
    assert val > 0, f"{field} should be > 0, got {val}"


def assert_date_recent(date_str: str, field: str, max_days: int = 365):
    """Assert a date string is parseable and within max_days of today."""
    assert date_str, f"{field} should not be empty"
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(date_str[:19], fmt)
            age = (datetime.now() - dt).days
            assert age <= max_days, f"{field} is {age} days old (max {max_days})"
            return
        except ValueError:
            continue
    # If none of the formats worked, just log — some dates have timezone suffixes
    logger.warning(f"Could not parse date format for {field}: {date_str}")


# ═══════════════════════════════════════════════
# OpenBB Data Provider Endpoints
# ═══════════════════════════════════════════════


@pytest.mark.slow
class TestQuoteEndpoint:
    """FMP quote via OpenBB — real-time price data."""

    @pytest.fixture(scope="class")
    def quote(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_quote(TEST_TICKER)
        )

    def test_returns_data(self, quote):
        assert quote is not None, "Quote returned None — FMP_API_KEY may be missing or invalid"

    def test_has_current_price(self, quote):
        if quote is None:
            pytest.skip("No quote data")
        assert_positive_number(quote.get("current_price"), "current_price")

    def test_has_volume(self, quote):
        if quote is None:
            pytest.skip("No quote data")
        vol = quote.get("volume")
        # Volume can be 0 on weekends/holidays — just check it exists and is numeric
        assert vol is not None, "volume should not be None"
        assert isinstance(vol, (int, float)), f"volume should be numeric, got {type(vol).__name__}"

    def test_has_change_pct(self, quote):
        if quote is None:
            pytest.skip("No quote data")
        pct = quote.get("change_pct")
        # Can be 0 or negative — just check it's numeric
        assert pct is not None, "change_pct should not be None"
        assert isinstance(pct, (int, float)), "change_pct should be numeric"

    def test_price_sanity(self, quote):
        """AAPL should be between $50 and $500 (sanity check)."""
        if quote is None:
            pytest.skip("No quote data")
        price = quote["current_price"]
        assert 50 < price < 500, f"AAPL price {price} outside sanity range $50-$500"

    def test_data_source_tagged(self, quote):
        if quote is None:
            pytest.skip("No quote data")
        assert quote.get("data_source") == "openbb"


@pytest.mark.slow
class TestPriceHistoryEndpoint:
    """FMP historical prices via OpenBB."""

    @pytest.fixture(scope="class")
    def history(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_price_history(TEST_TICKER, period="3m")
        )

    def test_returns_dataframe(self, history):
        assert history is not None, "Price history returned None"
        assert isinstance(history, pd.DataFrame), f"Expected DataFrame, got {type(history).__name__}"

    def test_has_ohlcv_columns(self, history):
        if history is None:
            pytest.skip("No history data")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in history.columns, f"Missing column: {col}"

    def test_sufficient_rows(self, history):
        """3 months of daily data should have at least 40 trading days."""
        if history is None:
            pytest.skip("No history data")
        assert len(history) >= 40, f"Only {len(history)} rows for 3m history (expected >=40)"

    def test_no_all_null_columns(self, history):
        if history is None:
            pytest.skip("No history data")
        for col in ["Open", "High", "Low", "Close"]:
            non_null = history[col].notna().sum()
            assert non_null > 0, f"Column {col} is entirely null"

    def test_prices_positive(self, history):
        if history is None:
            pytest.skip("No history data")
        assert (history["Close"].dropna() > 0).all(), "Found non-positive close prices"

    def test_dates_sorted(self, history):
        if history is None:
            pytest.skip("No history data")
        assert history.index.is_monotonic_increasing, "Price history dates not sorted ascending"

    def test_recent_data(self, history):
        """Most recent data point should be within 5 days (weekends/holidays)."""
        if history is None:
            pytest.skip("No history data")
        last_date = history.index[-1]
        if hasattr(last_date, "date"):
            last_date = last_date.date()
        days_old = (datetime.now().date() - pd.Timestamp(last_date).date()).days
        assert days_old <= 5, f"Most recent price is {days_old} days old"


@pytest.mark.slow
class TestCompanyOverviewEndpoint:
    """FMP company profile + metrics via OpenBB."""

    @pytest.fixture(scope="class")
    def overview(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_company_overview(TEST_TICKER)
        )

    def test_returns_data(self, overview):
        assert overview is not None, "Company overview returned None"

    def test_has_company_name(self, overview):
        if overview is None:
            pytest.skip("No overview data")
        name = overview.get("longName", "")
        assert "apple" in name.lower(), f"Expected 'Apple' in name, got: {name}"

    def test_has_sector(self, overview):
        if overview is None:
            pytest.skip("No overview data")
        assert_non_empty_string(overview.get("sector", ""), "sector")

    def test_has_market_cap(self, overview):
        if overview is None:
            pytest.skip("No overview data")
        mcap = overview.get("marketCap")
        if mcap is not None:
            assert mcap > 1e9, f"AAPL market cap {mcap} seems too low"

    def test_has_valuation_metrics(self, overview):
        if overview is None:
            pytest.skip("No overview data")
        # At least one valuation metric should be present
        metrics = ["PE", "forwardPE", "PB", "ROE", "profitMargin", "operatingMargin", "debtToEquity", "dividendYield"]
        present = [m for m in metrics if overview.get(m) is not None]
        assert len(present) >= 1, f"No valuation metrics present. Keys: {list(overview.keys())}"


@pytest.mark.slow
class TestFinancialsEndpoint:
    """FMP financial statements via OpenBB."""

    @pytest.fixture(scope="class")
    def financials(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_financials(TEST_TICKER)
        )

    def test_returns_data(self, financials):
        assert financials is not None, "Financials returned None"

    def test_has_balance_sheet(self, financials):
        if financials is None:
            pytest.skip("No financials data")
        bs = financials.get("balance_sheet", [])
        assert isinstance(bs, list), "balance_sheet should be a list"
        assert len(bs) > 0, "balance_sheet is empty"

    def test_has_income_statement(self, financials):
        if financials is None:
            pytest.skip("No financials data")
        inc = financials.get("income_statement", [])
        assert isinstance(inc, list), "income_statement should be a list"
        assert len(inc) > 0, "income_statement is empty"

    def test_has_cash_flow(self, financials):
        if financials is None:
            pytest.skip("No financials data")
        cf = financials.get("cash_flow", [])
        assert isinstance(cf, list), "cash_flow should be a list"
        assert len(cf) > 0, "cash_flow is empty"

    def test_income_has_revenue(self, financials):
        if financials is None:
            pytest.skip("No financials data")
        inc = financials.get("income_statement", [])
        if not inc:
            pytest.skip("No income statement data")
        row = inc[0]
        # FMP uses various field names for revenue
        revenue_fields = ["revenue", "total_revenue", "Revenue"]
        found = any(row.get(f) is not None for f in revenue_fields)
        assert found, f"No revenue field found in income statement. Keys: {list(row.keys())[:10]}"


@pytest.mark.slow
class TestEarningsEndpoint:
    """FMP earnings history via OpenBB."""

    @pytest.fixture(scope="class")
    def earnings(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_earnings(TEST_TICKER)
        )

    def test_returns_data(self, earnings):
        assert earnings is not None, "Earnings returned None — FMP Ultimate should have full access"

    def test_has_eps_history(self, earnings):
        if earnings is None:
            pytest.skip("No earnings data")
        history = earnings.get("eps_history", [])
        assert isinstance(history, list), "eps_history should be a list"
        assert len(history) >= 4, f"Expected >=4 quarters of EPS, got {len(history)}"

    def test_has_latest_eps(self, earnings):
        if earnings is None:
            pytest.skip("No earnings data")
        eps = earnings.get("latest_eps")
        assert eps is not None, "latest_eps should not be None"
        assert isinstance(eps, (int, float)), "latest_eps should be numeric"


@pytest.mark.slow
class TestEarningsTranscriptEndpoint:
    """FMP earnings transcript (direct REST API call)."""

    @pytest.fixture(scope="class")
    def transcript(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_earnings_transcript(TEST_TICKER)
        )

    def test_returns_data(self, transcript):
        assert transcript is not None, "Transcript returned None — FMP Ultimate should have full access"

    def test_has_content(self, transcript):
        if transcript is None:
            pytest.skip("No transcript data")
        content = transcript.get("content", "")
        assert len(content) > 100, f"Transcript content too short ({len(content)} chars)"

    def test_has_metadata(self, transcript):
        if transcript is None:
            pytest.skip("No transcript data")
        assert transcript.get("quarter") in (1, 2, 3, 4), "quarter should be 1-4"
        assert transcript.get("year", 0) >= 2020, "year should be >= 2020"
        assert transcript.get("symbol") == TEST_TICKER


@pytest.mark.slow
class TestTechnicalIndicatorsEndpoint:
    """Locally-computed technical indicators from price data."""

    @pytest.fixture(scope="class")
    def technicals(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_technical_indicators(TEST_TICKER)
        )

    def test_returns_data(self, technicals):
        assert technicals is not None, "Technical indicators returned None"

    def test_rsi_in_range(self, technicals):
        if technicals is None:
            pytest.skip("No technical data")
        rsi = technicals.get("rsi")
        assert rsi is not None, "RSI should not be None"
        assert 0 <= rsi <= 100, f"RSI {rsi} outside 0-100 range"

    def test_macd_structure(self, technicals):
        if technicals is None:
            pytest.skip("No technical data")
        macd = technicals.get("macd", {})
        assert "macd_line" in macd, "Missing macd_line"
        assert "signal_line" in macd, "Missing signal_line"
        assert "histogram" in macd, "Missing histogram"
        assert macd.get("interpretation") in ("bullish", "bearish", "neutral")

    def test_bollinger_bands(self, technicals):
        if technicals is None:
            pytest.skip("No technical data")
        bb = technicals.get("bbands", {})
        assert bb.get("upper_band") is not None, "Missing upper_band"
        assert bb.get("lower_band") is not None, "Missing lower_band"
        assert bb["upper_band"] > bb["lower_band"], "Upper band should be > lower band"

    def test_sma_values(self, technicals):
        if technicals is None:
            pytest.skip("No technical data")
        # At least SMA 20 and 50 should be present for 1y data
        sma20 = technicals.get("sma_20")
        sma50 = technicals.get("sma_50")
        assert sma20 is not None, "SMA 20 should not be None"
        assert sma50 is not None, "SMA 50 should not be None"
        assert sma20 > 0, "SMA 20 should be positive"


@pytest.mark.slow
class TestMacroIndicatorsEndpoint:
    """FRED macro indicators via OpenBB."""

    @pytest.fixture(scope="class")
    def macro(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_macro_indicators()
        )

    def test_returns_data(self, macro):
        if not Config.FRED_API_KEY:
            pytest.skip("No FRED_API_KEY configured")
        assert macro is not None, "Macro indicators returned None"

    def test_has_key_series(self, macro):
        if macro is None:
            pytest.skip("No macro data")
        expected = ["fed_funds", "treasury_10y", "unemployment", "cpi", "gdp"]
        present = [s for s in expected if macro.get(s) is not None]
        assert len(present) >= 3, f"Only {len(present)}/{len(expected)} macro series present: {present}"

    def test_series_have_recent_values(self, macro):
        if macro is None:
            pytest.skip("No macro data")
        for series_name in ["fed_funds", "treasury_10y"]:
            data = macro.get(series_name)
            if data is None:
                continue
            assert isinstance(data, list), f"{series_name} should be a list"
            assert len(data) >= 1, f"{series_name} is empty"
            latest = data[0]
            assert "date" in latest, f"{series_name} entry missing 'date'"
            assert "value" in latest, f"{series_name} entry missing 'value'"
            assert isinstance(latest["value"], (int, float)), f"{series_name} value should be numeric"

    def test_yield_curve(self, macro):
        """10Y and 2Y yields should both exist for yield curve analysis."""
        if macro is None:
            pytest.skip("No macro data")
        t10 = macro.get("treasury_10y")
        t2 = macro.get("treasury_2y")
        if t10 and t2:
            # Both should have recent data
            assert len(t10) >= 1 and len(t2) >= 1, "Need data in both yield series"


@pytest.mark.slow
class TestOptionsChainEndpoint:
    """Options chain via yfinance/OpenBB."""

    @pytest.fixture(scope="class")
    def options(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_options_chain(TEST_TICKER)
        )

    def test_returns_data(self, options):
        assert options is not None, "Options chain returned None"

    def test_has_contracts(self, options):
        if options is None:
            pytest.skip("No options data")
        contracts = options.get("contracts", [])
        assert isinstance(contracts, list), "contracts should be a list"
        assert len(contracts) > 10, f"Only {len(contracts)} option contracts (expected >10 for AAPL)"

    def test_has_expirations(self, options):
        if options is None:
            pytest.skip("No options data")
        exps = options.get("expirations", [])
        assert len(exps) >= 3, f"Only {len(exps)} expirations (expected >=3)"

    def test_put_call_ratio(self, options):
        if options is None:
            pytest.skip("No options data")
        pcr = options.get("put_call_ratio")
        if pcr is not None:
            assert 0 < pcr < 10, f"Put/call ratio {pcr} outside sanity range 0-10"

    def test_contract_structure(self, options):
        if options is None:
            pytest.skip("No options data")
        contracts = options.get("contracts", [])
        if not contracts:
            pytest.skip("No contracts")
        c = contracts[0]
        required = ["strike", "type", "expiration"]
        for field in required:
            assert field in c, f"Contract missing field: {field}"
        assert c["type"] in ("call", "put"), f"Unexpected option type: {c['type']}"


@pytest.mark.slow
class TestNewsEndpoint:
    """FMP company news via OpenBB."""

    @pytest.fixture(scope="class")
    def news(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_news(TEST_TICKER, limit=10)
        )

    def test_returns_data(self, news):
        assert news is not None, "News returned None — FMP Ultimate should have full access"

    def test_has_articles(self, news):
        if news is None:
            pytest.skip("No news data")
        assert isinstance(news, list), "News should be a list"
        assert len(news) >= 1, "No articles returned"

    def test_article_structure(self, news):
        if not news:
            pytest.skip("No news data")
        article = news[0]
        assert_non_empty_string(article.get("title", ""), "title")
        assert article.get("url") or article.get("link"), "Article missing URL"

    def test_articles_have_dates(self, news):
        """Check if articles have dates. FMP via OpenBB may not include dates."""
        if not news:
            pytest.skip("No news data")
        dated = [a for a in news if a.get("published_at")]
        # FMP news via OpenBB sometimes omits dates — log but don't fail
        if len(dated) < len(news) * 0.5:
            import logging
            logging.getLogger(__name__).warning(
                "FMP news: %d/%d articles missing dates (known FMP behavior)", len(news) - len(dated), len(news)
            )


# ═══════════════════════════════════════════════
# Tavily Search Endpoints
# ═══════════════════════════════════════════════


@pytest.mark.slow
class TestTavilyNewsSearch:
    """Tavily AI search — news articles (using official tavily-python)."""

    @pytest.fixture(scope="class")
    def results(self, tavily):
        if not tavily.is_available:
            pytest.skip("Tavily not available")
        return asyncio.get_event_loop().run_until_complete(
            tavily.search_news(f"${TEST_TICKER} stock news", max_results=5, days=7)
        )

    def test_search_succeeds(self, results):
        assert results.get("success") is True, f"Tavily search failed: {results.get('error')}"

    def test_has_articles(self, results):
        if not results.get("success"):
            pytest.skip("Search failed")
        articles = results.get("articles", [])
        assert len(articles) >= 1, "No Tavily articles returned"

    def test_article_quality(self, results):
        if not results.get("success"):
            pytest.skip("Search failed")
        articles = results.get("articles", [])
        if not articles:
            pytest.skip("No articles")
        a = articles[0]
        assert_non_empty_string(a.get("title", ""), "title")
        assert_non_empty_string(a.get("url", ""), "url")
        # Content or description should be present
        has_content = bool(a.get("content") or a.get("description"))
        assert has_content, "Article missing both content and description"

    def test_has_ai_summary(self, results):
        if not results.get("success"):
            pytest.skip("Search failed")
        summary = results.get("ai_summary")
        # AI summary is optional but should be present with include_answer=True
        if summary:
            assert len(summary) > 20, "AI summary seems too short"


@pytest.mark.slow
class TestTavilyCompanyContext:
    """Tavily company context search — multi-dimension."""

    @pytest.fixture(scope="class")
    def context(self, tavily):
        if not tavily.is_available:
            pytest.skip("Tavily not available")
        return asyncio.get_event_loop().run_until_complete(
            tavily.search_company_context("Apple", TEST_TICKER, ["earnings", "risks"])
        )

    def test_search_succeeds(self, context):
        assert context.get("success") is True, f"Context search failed: {context.get('error')}"

    def test_has_context_categories(self, context):
        if not context.get("success"):
            pytest.skip("Search failed")
        data = context.get("context_data", {})
        assert "earnings" in data, "Missing 'earnings' context"
        assert "risks" in data, "Missing 'risks' context"

    def test_context_has_items(self, context):
        if not context.get("success"):
            pytest.skip("Search failed")
        data = context.get("context_data", {})
        for category in ["earnings", "risks"]:
            cat_data = data.get(category, {})
            if cat_data.get("success"):
                items = cat_data.get("items", [])
                assert len(items) >= 1, f"{category} context has no items"


# ═══════════════════════════════════════════════
# FMP Ultimate Tier Endpoints
# ═══════════════════════════════════════════════


@pytest.mark.slow
class TestAnalystEstimatesEndpoint:
    """FMP analyst consensus estimates via OpenBB."""

    @pytest.fixture(scope="class")
    def estimates(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_analyst_estimates(TEST_TICKER)
        )

    def test_returns_data(self, estimates):
        assert estimates is not None, "Analyst estimates returned None"

    def test_has_targets(self, estimates):
        if estimates is None:
            pytest.skip("No estimates data")
        assert estimates.get("target_high") is not None, "Missing target_high"
        assert estimates.get("target_low") is not None, "Missing target_low"
        assert estimates.get("target_consensus") is not None, "Missing target_consensus"

    def test_target_sanity(self, estimates):
        if estimates is None:
            pytest.skip("No estimates data")
        high = estimates.get("target_high", 0)
        low = estimates.get("target_low", 0)
        assert high > low, f"target_high ({high}) should be > target_low ({low})"


@pytest.mark.slow
class TestRatiosTTMEndpoint:
    """FMP comprehensive TTM ratios via OpenBB."""

    @pytest.fixture(scope="class")
    def ratios(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_ratios_ttm(TEST_TICKER)
        )

    def test_returns_data(self, ratios):
        assert ratios is not None, "Ratios TTM returned None"

    def test_has_valuation_ratios(self, ratios):
        if ratios is None:
            pytest.skip("No ratios data")
        assert ratios.get("price_to_earnings") is not None, "Missing P/E"
        assert ratios.get("price_to_book") is not None, "Missing P/B"

    def test_has_profitability(self, ratios):
        if ratios is None:
            pytest.skip("No ratios data")
        assert ratios.get("gross_profit_margin") is not None, "Missing gross margin"
        assert ratios.get("net_profit_margin") is not None, "Missing net margin"

    def test_has_liquidity(self, ratios):
        if ratios is None:
            pytest.skip("No ratios data")
        cr = ratios.get("current_ratio")
        assert cr is not None, "Missing current_ratio"
        assert cr > 0, f"current_ratio should be positive, got {cr}"


@pytest.mark.slow
class TestManagementEndpoint:
    """FMP key executives via OpenBB."""

    @pytest.fixture(scope="class")
    def management(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_management(TEST_TICKER)
        )

    def test_returns_data(self, management):
        assert management is not None, "Management returned None"

    def test_has_executives(self, management):
        if management is None:
            pytest.skip("No management data")
        assert len(management) >= 3, f"Only {len(management)} executives (expected >=3)"

    def test_executive_structure(self, management):
        if not management:
            pytest.skip("No management data")
        exec = management[0]
        assert_non_empty_string(exec.get("name", ""), "name")
        assert_non_empty_string(exec.get("title", ""), "title")


@pytest.mark.slow
class TestInsiderTradingEndpoint:
    """FMP insider trading via OpenBB."""

    @pytest.fixture(scope="class")
    def insider(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_insider_trading(TEST_TICKER)
        )

    def test_returns_data(self, insider):
        assert insider is not None, "Insider trading returned None"

    def test_has_trades(self, insider):
        if insider is None:
            pytest.skip("No insider data")
        assert len(insider) >= 1, "No insider trades returned"

    def test_trade_structure(self, insider):
        if not insider:
            pytest.skip("No insider data")
        trade = insider[0]
        assert trade.get("owner_name"), "Missing owner_name"
        assert trade.get("date"), "Missing date"


@pytest.mark.slow
class TestShareStatisticsEndpoint:
    """FMP share float statistics via OpenBB."""

    @pytest.fixture(scope="class")
    def stats(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_share_statistics(TEST_TICKER)
        )

    def test_returns_data(self, stats):
        assert stats is not None, "Share statistics returned None"

    def test_has_shares(self, stats):
        if stats is None:
            pytest.skip("No stats data")
        assert stats.get("outstanding_shares") is not None, "Missing outstanding_shares"
        assert stats.get("float_shares") is not None, "Missing float_shares"


@pytest.mark.slow
class TestRevenueSegmentsEndpoint:
    """FMP product/geographic revenue segmentation via OpenBB."""

    @pytest.fixture(scope="class")
    def segments(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_revenue_segments(TEST_TICKER)
        )

    def test_returns_data(self, segments):
        assert segments is not None, "Revenue segments returned None"

    def test_has_product_segments(self, segments):
        if segments is None:
            pytest.skip("No segments data")
        product = segments.get("product", {})
        assert len(product) >= 2, f"Only {len(product)} product segments (expected >=2)"

    def test_has_geography_segments(self, segments):
        if segments is None:
            pytest.skip("No segments data")
        geo = segments.get("geography", {})
        assert len(geo) >= 2, f"Only {len(geo)} geographic segments (expected >=2)"


@pytest.mark.slow
class TestFinancialGrowthEndpoint:
    """FMP financial growth rates (direct REST)."""

    @pytest.fixture(scope="class")
    def growth(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_financial_growth(TEST_TICKER)
        )

    def test_returns_data(self, growth):
        assert growth is not None, "Financial growth returned None"

    def test_has_growth_rates(self, growth):
        if growth is None:
            pytest.skip("No growth data")
        assert growth.get("revenue_growth") is not None, "Missing revenue_growth"
        assert growth.get("eps_growth") is not None, "Missing eps_growth"


@pytest.mark.slow
class TestDCFValuationEndpoint:
    """FMP DCF valuation (direct REST)."""

    @pytest.fixture(scope="class")
    def dcf(self, provider):
        return asyncio.get_event_loop().run_until_complete(
            provider.get_dcf_valuation(TEST_TICKER)
        )

    def test_returns_data(self, dcf):
        assert dcf is not None, "DCF valuation returned None"

    def test_has_dcf_value(self, dcf):
        if dcf is None:
            pytest.skip("No DCF data")
        assert_positive_number(dcf.get("dcf"), "dcf")

    def test_has_stock_price(self, dcf):
        if dcf is None:
            pytest.skip("No DCF data")
        assert_positive_number(dcf.get("stock_price"), "stock_price")


# ═══════════════════════════════════════════════
# Cross-Endpoint Consistency Checks
# ═══════════════════════════════════════════════


@pytest.mark.slow
class TestCrossEndpointConsistency:
    """Verify data consistency across endpoints."""

    @pytest.fixture(scope="class")
    def all_data(self, provider):
        """Fetch quote and history together for comparison."""
        loop = asyncio.get_event_loop()
        quote = loop.run_until_complete(provider.get_quote(TEST_TICKER))
        history = loop.run_until_complete(provider.get_price_history(TEST_TICKER, period="1m"))
        return {"quote": quote, "history": history}

    def test_quote_price_near_last_close(self, all_data):
        """Quote price should be reasonably close to most recent historical close."""
        quote = all_data.get("quote")
        history = all_data.get("history")
        if quote is None or history is None or history.empty:
            pytest.skip("Missing quote or history data")

        quote_price = quote.get("current_price")
        last_close = float(history["Close"].iloc[-1])

        if quote_price is None or last_close == 0:
            pytest.skip("Missing price values")

        # Prices should be within 15% (accounts for after-hours, weekends)
        pct_diff = abs(quote_price - last_close) / last_close * 100
        assert pct_diff < 15, (
            f"Quote price ${quote_price:.2f} differs from last close "
            f"${last_close:.2f} by {pct_diff:.1f}%"
        )

    def test_all_endpoints_tagged(self, provider):
        """All data endpoints should include data_source tag."""
        loop = asyncio.get_event_loop()
        endpoints = {
            "quote": loop.run_until_complete(provider.get_quote(TEST_TICKER)),
            "overview": loop.run_until_complete(provider.get_company_overview(TEST_TICKER)),
            "financials": loop.run_until_complete(provider.get_financials(TEST_TICKER)),
            "earnings": loop.run_until_complete(provider.get_earnings(TEST_TICKER)),
        }
        for name, data in endpoints.items():
            if data is not None:
                assert "data_source" in data, f"{name} endpoint missing data_source tag"
