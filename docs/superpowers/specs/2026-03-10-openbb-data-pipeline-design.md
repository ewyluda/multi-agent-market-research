# OpenBB Data Pipeline Migration Design

**Date:** 2026-03-10
**Status:** Approved
**Approach:** Data Layer Abstraction (Approach A)

## Goal

Replace the current per-agent Alpha Vantage + yfinance data-fetching code with a centralized `OpenBBDataProvider` service backed by the OpenBB Platform SDK (v4.7+). This achieves:

1. **Rate limit relief** — Drop from ~22 AV calls/analysis to 0 AV calls. Technical indicators computed locally, macro data from FRED.
2. **Unified data layer** — Single SDK replaces scattered AV/yfinance/SEC EDGAR plumbing across 6 agents.
3. **More data providers** — FMP (250 req/day free), FRED (120 req/min), CBOE, yfinance as no-key fallback.

## Decisions

- **Async strategy:** `asyncio.to_thread()` wrappers around synchronous OpenBB calls. Matches existing `_retry_fetch()` pattern. Agents still run in parallel via `asyncio.gather()`.
- **Provider stack:** FMP (primary equities), FRED (macro), CBOE + yfinance (options), FMP + Benzinga (news). yfinance as universal fallback.
- **Tavily + Twitter:** Kept as-is. Tavily is the primary news source with AI summaries; Twitter provides social sentiment. Neither is available in OpenBB.
- **License:** OpenBB Platform uses AGPLv3. Fine for internal/self-hosted use.

## Architecture

```
Orchestrator
  ├── creates OpenBBDataProvider (singleton)
  ├── injects into each agent
  └── runs agents in parallel via asyncio.gather()

Agent.fetch_data()
  └── calls data_provider.get_*() methods
      └── asyncio.to_thread(obb.some.endpoint(...))
          └── OpenBB SDK → FMP/FRED/yfinance/CBOE

Agent.analyze()
  └── unchanged — receives same normalized dict structure
```

## OpenBBDataProvider Service

**File:** `src/data_provider.py`

### Initialization

```python
class OpenBBDataProvider:
    def __init__(self, config: Config):
        from openbb import obb
        self._obb = obb
        # Set credentials from config/.env
        obb.user.credentials.fmp_api_key = config.FMP_API_KEY
        obb.user.credentials.fred_api_key = config.FRED_API_KEY
        # Initialize TTL cache
        self._cache = {}  # key: (method, ticker, params) → (result, timestamp)
```

### Methods

| Method | OpenBB Call | Provider | Returns |
|--------|-----------|----------|---------|
| `get_quote(ticker)` | `obb.equity.price.quote()` | FMP > yfinance | `{current_price, open, high, low, volume, change_pct, previous_close}` |
| `get_price_history(ticker, period)` | `obb.equity.price.historical()` | FMP > yfinance | `pd.DataFrame` (OHLCV) |
| `get_company_overview(ticker)` | `obb.equity.profile()` + `obb.equity.fundamental.metrics()` | FMP > yfinance | `{longName, sector, industry, marketCap, PE, margins, ROE, ...}` |
| `get_financials(ticker)` | `obb.equity.fundamental.balance/income/cash()` | FMP > yfinance | `{balance_sheet, income_statement, cash_flow}` |
| `get_earnings(ticker)` | `obb.equity.fundamental.historical_eps()` | FMP | `{eps_history, latest_eps, announcement_date}` |
| `get_technical_indicators(ticker, price_data?)` | `obb.technical.rsi/macd/bbands/sma()` | Local compute | `{rsi, macd, bbands, sma_10, sma_20, sma_50}` |
| `get_macro_indicators()` | `obb.economy.fred_series()` x7 | FRED | `{fed_funds, treasury_10y, treasury_2y, unemployment, cpi, gdp, inflation}` |
| `get_options_chain(ticker)` | `obb.derivatives.options.chains()` | CBOE > yfinance | `{calls, puts, expirations, put_call_ratio}` |
| `get_news(ticker, limit)` | `obb.news.company()` | FMP > Benzinga | `[{title, source, url, published_at, summary, sentiment}]` |

### Behaviors

- All methods are `async` — wrap OpenBB sync calls in `asyncio.to_thread()`
- Return `None` or empty defaults on failure (agents handle gracefully)
- Include `data_source` field in results for diagnostics tracking
- Price history fetched once and reused for technical indicators
- Macro data cached 24 hours globally (not per-ticker)
- Quote data cached 5 minutes, fundamentals cached 24 hours, news cached 1 hour

### Caching

Simple TTL dict in the data provider:

```python
_cache: dict[str, tuple[Any, float]]  # key → (result, expiry_timestamp)

TTLs:
  quote: 5 minutes
  price_history: 5 minutes
  fundamentals/overview/earnings: 24 hours
  technical: 5 minutes (derived from price_history cache)
  macro: 24 hours
  options: 15 minutes
  news: 1 hour
```

No request coalescing. When agents run in parallel, two agents may request the same data concurrently before either caches the result, causing duplicate OpenBB calls. This is acceptable because: (a) duplicate work is a thread-pool call, not a rate-limited API call with strict quotas, and (b) FMP's 250 req/day limit has ample headroom for occasional duplicates. The TTL cache prevents repeated calls on subsequent analyses.

## Agent Changes

### BaseAgent

**Remove:**
- `_av_request()`, `_do_av_request()` methods
- `_shared_session`, `_rate_limiter`, `_av_cache` attributes
- `AV_BASE_URL` constant

**Add:**
- `_data_provider: OpenBBDataProvider` attribute (injected by orchestrator)

**Keep:**
- `execute()` method (fetch_data → analyze → return)
- `_retry_fetch()` and `_run_blocking()` — general-purpose async wrappers for sync calls (used by NewsAgent for Twitter, Tavily, and company name lookups)
- Timeout management, logging, error handling

### Per-Agent Refactoring

**MarketAgent:** Replace ~80 lines of AV+yfinance fetch code with:
- `data_provider.get_quote(ticker)` + `data_provider.get_price_history(ticker)`
- Slice history into 1y/3m/1m windows
- `analyze()` unchanged

**FundamentalsAgent:** Replace ~150 lines of 5 AV endpoints + yfinance fetch code with:
- `data_provider.get_company_overview(ticker)` + `data_provider.get_financials(ticker)` + `data_provider.get_earnings(ticker)`
- **Keep** SEC EDGAR XBRL code — used as supplementary data source for quarterly financials, independent of the primary provider
- **Keep** `_fetch_tavily_context()` — used for LLM equity research context
- LLM equity research call unchanged
- `analyze()` unchanged

**TechnicalAgent:** Replace ~120 lines of 7 AV indicator calls + yfinance local calc with:
- `data_provider.get_price_history(ticker)` + `data_provider.get_technical_indicators(ticker, price_data)`
- Technical indicators always computed locally via OpenBB technical module
- `fetch_data()` populates `av_indicators` dict with computed values so `analyze()` takes the pre-computed indicators branch (preserving existing code path). The `analyze()` method's `av_indicators` branch works regardless of whether values came from AV API or local computation — it just reads dict keys.

**MacroAgent:** Replace ~100 lines of 7 AV macro endpoints with:
- `data_provider.get_macro_indicators()` (ticker-independent, cached 24h)
- If `FRED_API_KEY` is not set, `get_macro_indicators()` returns `None` and agent returns `{"source": "none", "data": {}}` — same graceful degradation as current AV-missing behavior
- `analyze()` unchanged

**OptionsAgent:** Replace ~80 lines of AV REALTIME_OPTIONS + yfinance with:
- `data_provider.get_options_chain(ticker)`
- `analyze()` unchanged

**NewsAgent:** Partial change — keep Tavily (primary) and Twitter (supplementary):
- Replace AV NEWS_SENTIMENT and NewsAPI fallback with `data_provider.get_news(ticker)`
- Keep `_fetch_tavily_news()` as primary
- Keep `_fetch_twitter_posts()` as supplementary
- `analyze()` unchanged

**SentimentAgent:** No changes — LLM-powered, receives articles from NewsAgent.

**SolutionAgent:** No changes — synthesizes agent results.

**LeadershipAgent:** No changes — LLM-powered evaluation.

## Orchestrator Changes

**Remove:**
- `AVRateLimiter` and `AVCache` instantiation
- `_create_shared_session()` / `_close_shared_session()` and their try/finally lifecycle in `analyze_ticker()`
- `_inject_shared_resources()` method (replace with data_provider injection)

**Add:**
- `OpenBBDataProvider` creation at startup (singleton, passed to constructor or created in `__init__`)
- New `_inject_data_provider(agent)` method — sets `agent._data_provider`
- Keep a lightweight `aiohttp.ClientSession` for non-OpenBB HTTP calls (Twitter, Tavily, SEC EDGAR) — injected as `agent._http_session`

**Keep:**
- Agent dependency resolution
- `asyncio.gather()` parallel execution
- Sentiment agent context injection (news articles, twitter posts)
- Solution agent synthesis
- Alert evaluation
- SSE progress streaming

## Configuration

### New .env Variables

```bash
# OpenBB providers
FMP_API_KEY=...              # Primary equity data (free: 250 req/day)
FRED_API_KEY=...             # Macro data (free: 120 req/min)

# Provider overrides (optional)
OPENBB_EQUITY_PROVIDER=fmp        # default: fmp
OPENBB_MACRO_PROVIDER=fred        # default: fred
OPENBB_OPTIONS_PROVIDER=yfinance  # default: cboe
OPENBB_NEWS_PROVIDER=fmp          # default: fmp
```

### Removed .env Variables

```bash
ALPHA_VANTAGE_API_KEY       # No longer used
AV_RATE_LIMIT_PER_MINUTE    # No longer needed
AV_RATE_LIMIT_PER_DAY       # No longer needed
```

### Kept .env Variables

All existing Tavily, Twitter, LLM, scheduler, alert, and agent config variables unchanged.

## API Call Budget

| Source | Before | After | Notes |
|--------|--------|-------|-------|
| Alpha Vantage | ~22/analysis | 0 | Fully replaced |
| FMP | 0 | ~9/analysis | quote, daily, profile, metrics, balance, income, cash, earnings, news |
| FRED | 0 | ~7/analysis | Cached 24h, shared across tickers |
| yfinance | fallback only | fallback only | No API key needed |
| Tavily | 1 | 1 | Unchanged |
| Twitter | 1 | 1 | Unchanged |
| Local compute | 0 | 6 indicators | RSI, MACD, BBands, SMA x3 |

## Files

### Create
- `src/data_provider.py` — OpenBBDataProvider service
- `tests/test_data_provider.py` — Data provider tests

### Modify
- `src/agents/base_agent.py` — Remove AV infrastructure, add data_provider attribute, keep _retry_fetch/_run_blocking
- `src/agents/market_agent.py` — Delegate to data_provider
- `src/agents/fundamentals_agent.py` — Delegate to data_provider (keep SEC EDGAR + Tavily context code)
- `src/agents/technical_agent.py` — Delegate to data_provider, populate av_indicators dict from local compute
- `src/agents/macro_agent.py` — Delegate to data_provider
- `src/agents/options_agent.py` — Delegate to data_provider
- `src/agents/news_agent.py` — Partial: replace AV/NewsAPI with data_provider, keep Tavily/Twitter
- `src/orchestrator.py` — Create and inject data_provider, update constructor signature, keep lightweight aiohttp session for non-OpenBB calls
- `src/api.py` — Remove AVRateLimiter/AVCache imports and instantiation; create/pass OpenBBDataProvider to Orchestrator at all 5 callsites
- `src/scheduler.py` — Remove AVRateLimiter/AVCache imports and instantiation; update Orchestrator construction at all 3 callsites
- `src/config.py` — Add FMP_API_KEY, FRED_API_KEY, OPENBB_*_PROVIDER config vars
- `requirements.txt` — Add openbb, openbb-technical
- `.env.example` — Update variable documentation
- `tests/conftest.py` — Replace AV fixtures with data_provider mocks
- `tests/test_agents/test_base_agent.py` — Update for removed AV methods
- `tests/test_agents/test_options_agent.py` — Update mocks from AV to data_provider
- `tests/test_orchestrator.py` — Update for data_provider injection
- `tests/test_api.py` — Update Orchestrator construction mocks
- `tests/test_scheduler.py` — Update Orchestrator construction mocks

### Delete
- `src/av_cache.py`
- `src/av_rate_limiter.py`
- `tests/test_av_cache.py`
- `tests/test_av_rate_limiter.py`

## Testing Strategy

- Mock `OpenBBDataProvider` methods in agent tests (return fixture dicts)
- Test data_provider in isolation with mocked `obb` calls
- Agent `analyze()` tests unchanged (same input dict structure)
- Integration tests: verify orchestrator creates provider and injects correctly
- No `aioresponses` needed for AV endpoints — replaced by simple method mocks

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| OpenBB SDK sync blocking event loop | `asyncio.to_thread()` moves to thread pool |
| FMP rate limits hit | yfinance fallback configured in OpenBB provider priority |
| OpenBB API changes between versions | Pin `openbb>=4.7.0,<5.0` in requirements |
| AGPL license concerns | Using as library dependency only, not modifying OpenBB source. Note: AGPLv3 network-use clause applies if served to external users — fine for internal/self-hosted use, but requires source availability if deployed as a multi-user SaaS. Consult licensing@openbb.co if commercializing. |
| Data format differences from AV | Normalization in data_provider ensures agents receive same dict structure |
| Large dependency footprint | `openbb` + `openbb-technical` only, not `openbb[all]` |
