# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI Assistant Guide

## Project Overview

This is a **Multi-Agent Market Research Platform** that analyzes stocks using 7 specialized AI agents working in parallel, followed by a solution agent that synthesizes their outputs into a final recommendation.

**Key Concept**: Real-time stock analysis powered by distributed AI agents, each with a specific domain of expertise (news, sentiment, fundamentals, market data, technical analysis, macroeconomics).

## Architecture

```
User → FastAPI API → Orchestrator → [7 Agents Run in Parallel]
                                          ↓
                                    Solution Agent (Synthesizer)
                                          ↓
                                    Database (SQLite)
                                          ↓
                                    JSON Response
```

### Agent Roles

1. **News Agent** (`src/agents/news_agent.py`) - Fetches financial news with relevance filtering + Twitter/X social posts (concurrent via `asyncio.create_task`)
2. **Sentiment Agent** (`src/agents/sentiment_agent.py`) - LLM-based sentiment analysis on news + Twitter posts (5 factors: earnings, guidance, stock_reactions, strategic_news, social_sentiment)
3. **Fundamentals Agent** (`src/agents/fundamentals_agent.py`) - Company financials, health metrics, and LLM equity research
4. **Market Agent** (`src/agents/market_agent.py`) - Price trends and market conditions
5. **Technical Agent** (`src/agents/technical_agent.py`) - RSI, MACD, Bollinger Bands, SMA
6. **Macro Agent** (`src/agents/macro_agent.py`) - US macroeconomic indicators (fed funds rate, CPI, GDP, treasury yields, unemployment, inflation)
7. **Options Agent** (`src/agents/options_agent.py`) - Options chain data, put/call ratios, unusual activity, max pain analysis
8. **Solution Agent** (`src/agents/solution_agent.py`) - Synthesizes all outputs with chain-of-thought reasoning

### Data Source Priority (per agent)

All data-fetching agents use a centralized `OpenBBDataProvider` (`src/data_provider.py`) injected via `agent._data_provider`. Agents do **not** call external APIs directly.

| Agent                  | OpenBB Provider                                         | Fallback                  |
| ---------------------- | ------------------------------------------------------- | ------------------------- |
| **Market Agent**       | FMP (quote, price history)                              | yfinance                  |
| **Fundamentals Agent** | FMP (profile, financials, earnings)                     | yfinance + SEC EDGAR XBRL |
| **News Agent**         | Tavily (primary) → OpenBB/FMP (free tier blocks: 402)  | empty                     |
| **Technical Agent**    | FMP price history + local pandas compute                | yfinance + local calc     |
| **Macro Agent**        | FRED (fed_funds, treasuries, CPI, GDP, unemployment...) | None                      |
| **Sentiment Agent**    | N/A (LLM-powered)                                       | N/A                       |
| **Options Agent**      | yfinance via OpenBB                                     | None                      |

Each agent inherits from `BaseAgent` which provides:

- `_retry_fetch(func)` — exponential backoff with jitter for synchronous fallback calls
- `_run_blocking(func)` — runs sync functions via `asyncio.to_thread()`
- `_shared_session` — aiohttp session injected by orchestrator for connection pooling
- `_data_provider` — `OpenBBDataProvider` instance injected by orchestrator
- `data_source` tracking in analysis output (`"openbb"` or `"yfinance"`)

## Core Files

### Entry Points

- **`run.py`** - Application startup script (runs FastAPI server)
- **`src/api.py`** - FastAPI application with REST and SSE endpoints

### Core Logic

- **`src/orchestrator.py`** - Coordinates agents (configurable pipeline), manages shared session and data provider
- **`src/data_provider.py`** - Centralized OpenBB Platform SDK wrapper; TTL cache, async-safe via `asyncio.to_thread()`
- **`src/database.py`** - SQLite operations, caching, data persistence
- **`src/config.py`** - Environment variable management, configuration
- **`src/models.py`** - Pydantic models for data validation
- **`src/pdf_report.py`** - PDF report generation using ReportLab
- **`src/scheduler.py`** - Background analysis scheduler using APScheduler
- **`src/alert_engine.py`** - Alert rule evaluation engine for post-analysis notifications
- **`src/signal_contract.py`** - Deterministic signal contract v2 builder/validator (score → EV, scenarios, confidence calibration)
- **`src/portfolio_engine.py`** - Portfolio advisory overlay engine (position sizing, risk budget, sector limits)
- **`src/rollout_canary.py`** - Phase 7 rollout preflight and staged promotion runner
- **`src/rollout_metrics.py`** - Phase 7 rollout gate metrics and V2 alert rule type registry
- **`src/backfill_signal_contract.py`** - Backfills signal_contract_v2 column for historical analyses
- **`src/validation_rules.py`** - Deterministic rule engine (Tier 1a): direction, regime, options, technical consistency checks; penalty cap 0.40
- **`src/agents/council_validator_agent.py`** - LLM-powered council validator (Tier 1b): single LLM call validates investor claims against raw agent data; graceful fallback; penalty cap 0.25
- **`src/thesis_health.py`** - Thesis health indicator drift detection and aggregate rollup (INTACT/WATCHING/DETERIORATING/BROKEN)
- **`src/council_synthesis.py`** - Deterministic council consensus aggregation (stance distribution, disagreements, scenarios)
- **`src/agents/council_synthesis_agent.py`** - LLM-powered council synthesis narrative agent with graceful fallback

### Agent Directory Structure

```
src/agents/
├── base_agent.py         # Abstract base class with _retry_fetch(), _run_blocking(), shared session support
├── news_agent.py         # News gathering (Tavily primary → OpenBB/FMP → empty)
├── sentiment_agent.py    # Sentiment analysis (LLM-powered)
├── fundamentals_agent.py # Company fundamentals (OpenBB/FMP → yfinance + SEC EDGAR)
├── market_agent.py       # Market data (OpenBB/FMP → yfinance)
├── technical_agent.py    # Technical indicators (OpenBB price history + local pandas compute)
├── macro_agent.py        # US macroeconomic indicators (OpenBB/FRED)
├── options_agent.py      # Options flow & unusual activity (OpenBB/yfinance)
└── solution_agent.py     # Final synthesis (LLM-powered)
```

### Investor Council Agents (`src/agents/council/`)

Qualitative interpretation layer — 26 legendary investor personas, each with a unique framework and primary question. Opt-in via `POST /api/analyze/{ticker}/council`; does NOT run as part of the standard pipeline.

```
src/agents/council/
├── __init__.py
├── profiles.py              # INVESTOR_PROFILES dict — all 26 profiles (name, tagline, framework, rules)
├── base_council_agent.py    # BaseCouncilAgent: set_context(), _build_prompt(), _parse_llm_response()
├── druckenmiller_agent.py   # Primary (always-on)
├── ptj_agent.py             # Primary (always-on)
├── munger_agent.py          # Primary (always-on)
├── dalio_agent.py           # Primary (always-on)
├── marks_agent.py           # Primary (always-on)
└── <21 secondary agents>    # Opt-in via "Add Voice" button (max 7 total)
```

- Each agent: `INVESTOR_KEY = "<key>"` — profile loaded from `profiles.py` at runtime
- Loaded dynamically via `importlib.import_module` — no import cost at startup
- LLM output schema: `{ stance, thesis_health, qualitative_analysis, primary_question_answered, key_observations[], if_then_scenarios[], disagreement_flag }`
- Stances: `BULLISH | CAUTIOUS | BEARISH | PASS`; Thesis health: `INTACT | WATCHING | DETERIORATING | BROKEN | UNKNOWN`
- New API endpoints: `POST/GET /api/analyze/{ticker}/council`, `POST/GET/DELETE /api/thesis/{ticker}`
- New DB tables: `thesis_cards` (upsert by ticker), `council_results`
- Frontend: `CouncilPanel.jsx` → Council tab (6th tab after Diagnostics)

### Frontend

```
frontend/
├── src/
│   ├── components/
│   │   ├── Dashboard.jsx          # Root layout: Sidebar + ContentHeader + tabbed content + right sidebar
│   │   ├── Sidebar.jsx            # 64px fixed left icon sidebar (6 nav items: analysis/history/watchlist/portfolio/schedules/alerts)
│   │   ├── ContentHeader.jsx      # Sticky header: ticker info, price, change %, search input, progress bar
│   │   ├── AnalysisTabs.jsx       # 6-tab bar (Overview/Risks/Opportunities/Leadership/Diagnostics/Council) + framer-motion underline
│   │   ├── AgentPipelineBar.jsx   # Compact horizontal agent status bar (8 dots, collapsible after completion)
│   │   ├── Recommendation.jsx     # SVG gauge with BUY/HOLD/SELL + agent consensus strip
│   │   ├── PriceChart.jsx         # lightweight-charts candlestick + volume, indicators, source badges
│   │   ├── Summary.jsx            # Exports: VerdictBanner, AtAGlance, OverviewMetrics, ResearchContent, ChangeSummaryPanel
│   │   ├── DiagnosticsPanel.jsx   # Signal disagreement and data-quality diagnostics tab panel
│   │   ├── PortfolioPanel.jsx     # Singleton portfolio profile + holdings CRUD (Portfolio nav view)
│   │   ├── ScenarioPanel.jsx      # Bull/base/bear scenario probabilities and expected return framing
│   │   ├── MacroSnapshot.jsx      # Macro indicators right sidebar widget (fed rate, yields, inflation, GDP)
│   │   ├── NewsFeed.jsx           # Relevance-scored news article list with hover elevation
│   │   ├── HistoryDashboard.jsx   # Analysis history browser (trend charts, filters, pagination)
│   │   ├── WatchlistPanel.jsx     # Watchlist management + batch analyze + comparison table
│   │   ├── OptionsFlow.jsx        # Options flow display (P/C ratio, unusual activity, max pain)
│   │   ├── SchedulePanel.jsx      # Schedule management for recurring analyses
│   │   ├── AlertPanel.jsx         # Alert rules management and notification feed
│   │   ├── CouncilPanel.jsx       # Investor Council tab — 26 personas, thesis card, if-then playbook
│   │   └── Icons.jsx              # SVG icon components (35+ icons)
│   ├── context/
│   │   └── AnalysisContext.jsx    # React context for analysis state
│   ├── hooks/
│   │   ├── useAnalysis.js         # Analysis data fetching hook
│   │   ├── useHistory.js          # History state management (pagination, filters, tickers)
│   │   └── useSSE.js              # SSE streaming hook
│   ├── utils/
│   │   └── api.js                 # API client (analysis + history + watchlist + schedule + alert endpoints)
│   ├── index.css                  # Theme system (Tailwind v4 @theme + CSS custom properties + glass-card classes)
│   └── App.jsx                    # Root component
├── Dockerfile                     # Production frontend (multi-stage: node build → nginx)
├── Dockerfile.dev                 # Development frontend (Vite hot-reload)
├── nginx.conf                     # Nginx reverse proxy with SSE support
├── tailwind.config.js             # Tailwind color configuration
└── package.json
```

**Frontend Layout**: Sidebar (64px fixed left, `--sidebar-width` CSS var) + main content area. Analysis view: sticky ContentHeader → AgentPipelineBar → AnalysisTabs → tab content panels + right sidebar (280px, Recommendation + MacroSnapshot). Tab content mapping: Overview (PriceChart + OverviewMetrics), Risks (ScenarioPanel + ChangeSummaryPanel), Opportunities (ResearchContent + NewsFeed + OptionsFlow), Diagnostics (DiagnosticsPanel). VIEW_MODES enum (ANALYSIS, HISTORY, WATCHLIST, PORTFOLIO, SCHEDULES, ALERTS) switches between panels. Welcome screen has dot grid background, hero search input, quick-start ticker pills.

**Frontend Theme**: Hero UI dark theme variant (zinc-based). Three color layers:

1. `tailwind.config.js` - Custom color values
2. `@theme` block in `index.css` - Semantic tokens (`--color-primary`, `--color-success`, etc.)
3. `:root` block in `index.css` - CSS custom properties for backgrounds, borders, glows

**Key Frontend Patterns**:

- `Summary.jsx` exports `VerdictBanner`, `AtAGlance`, `OverviewMetrics`, `ResearchContent`, `ChangeSummaryPanel` — `OverviewMetrics` shows at-a-glance cards; `ResearchContent` renders 11-step chain-of-thought; `ChangeSummaryPanel` highlights material changes vs prior run
- `Recommendation.jsx` includes left glow line, gradient arc gauge, animated needle glow (SMIL), and agent consensus strip (bullish/bearish/neutral dots)
- `Sidebar.jsx` has 6 NAV_ITEMS (analysis/history/watchlist/portfolio/schedules/alerts) with tooltip labels, active state glow, and alert notification badge
- `ContentHeader.jsx` shows ticker name, price, change %, data source badges, search input, and loading progress bar
- `AnalysisTabs.jsx` uses framer-motion `layoutId` for animated tab underline; 6 tabs (Overview/Risks/Opportunities/Leadership/Diagnostics/Council) — no icons
- `AgentPipelineBar.jsx` reads from `useAnalysisContext()`, shows 8 agent dots with status colors, collapses after completion
- `MacroSnapshot.jsx` surfaces macro data (fed funds, yields, inflation, GDP) with gradient yield bars
- `PriceChart.jsx` uses lightweight-charts for candlestick + volume, shows indicator cards with hover borders
- `HistoryDashboard.jsx` uses `useHistory` hook for state; SVG `TrendChart` plots scores chronologically with color-coded recommendation dots; `FilterBar` toggles BUY/HOLD/SELL; `Pagination` handles offset-based pages
- `WatchlistPanel.jsx` manages CRUD via `api.js` watchlist functions; SSE `EventSource` for batch analysis; `ComparisonTable` sorts by confidence
- `SchedulePanel.jsx` manages schedule CRUD via `api.js` schedule functions; create/edit/delete schedules with interval selection; enable/disable toggle; expandable run history
- `AlertPanel.jsx` manages alert rules and notifications; legacy rule types (recommendation_change, score_above/below, confidence_above/below); V2 rule types (ev_above, ev_below, regime_change, data_quality_below, calibration_drop); notifications feed with acknowledge; unread filter toggle
- `PortfolioPanel.jsx` manages singleton portfolio profile (risk limits) + holdings via `/api/portfolio` endpoints; accessible via Portfolio nav item
- `ScenarioPanel.jsx` shows bull/base/bear scenarios with probability bars and 7d expected return; reads from `analysis_payload.scenarios`
- `DiagnosticsPanel.jsx` shows signal disagreement and data quality flags; reads from `analysis_payload.diagnostics` and `diagnostics_summary`
- Glass cards use `glass-card` / `glass-card-elevated` CSS classes with hover transitions defined in `index.css`

## Key Technologies

- **FastAPI** - REST API and SSE streaming server
- **SQLite** - Database for caching and persistence
- **Anthropic Claude / OpenAI / xAI Grok** - LLM for sentiment, equity research, and synthesis
- **AsyncIO** - Parallel agent execution
- **aiohttp** - Async HTTP client for SEC EDGAR calls within agents
- **Pydantic** - Data validation and models
- **OpenBB Platform SDK (v4.7+)** - Centralized market data (FMP, FRED, yfinance providers)
- **yfinance** - Fallback/options data source via OpenBB
- **FMP (Financial Modeling Prep)** - Primary equities/fundamentals via OpenBB (free: ~250 req/day)
- **FRED** - Macroeconomic indicators via OpenBB (free, unlimited)
- **Twitter/X API v2** - Social sentiment data (supplementary, `search/recent` endpoint)
- **React + Tailwind CSS v4** - Frontend UI with Hero UI dark theme
- **framer-motion** - Tab underline animations, stagger lists, spring physics for gauges, AnimatePresence for tab transitions
- **lightweight-charts** - TradingView candlestick + volume charts (replaced custom SVG chart)
- **Vite** - Frontend build tool
- **pytest** - Test framework (292 tests with pytest-asyncio, aioresponses, httpx)
- **ReportLab** - PDF report generation
- **APScheduler** - Background job scheduling for recurring analyses
- **Docker** - Containerization (multi-stage builds, nginx reverse proxy)

## Environment Setup

### Required Environment Variables

```bash
ANTHROPIC_API_KEY=sk-...  # Primary LLM provider
# OR
OPENAI_API_KEY=sk-...     # Alternative LLM provider
# OR
GROK_API_KEY=...          # xAI Grok provider
```

### Recommended API Keys (OpenBB Providers)

```bash
FMP_API_KEY=...           # Financial Modeling Prep — equity quotes, financials, earnings
FRED_API_KEY=...          # Federal Reserve Economic Data — macro indicators
TAVILY_API_KEY=...        # Tavily AI search — primary news source
```

### Optional API Keys

```bash
TWITTER_BEARER_TOKEN=...  # Twitter/X API v2 — social sentiment (supplementary)
```

### Configuration Options (`.env`)

- `LLM_PROVIDER` - "anthropic", "openai", or "xai" (default: anthropic)
- `LLM_MODEL` - Model name (default: claude-3-5-sonnet-20241022)
- `AGENT_TIMEOUT` - Timeout in seconds (default: 30)
- `AGENT_MAX_RETRIES` - Retry attempts per data fetch (default: 2)
- `NEWS_LOOKBACK_DAYS` - Days of news history (default: 7)
- `MAX_NEWS_ARTICLES` - Max articles to fetch (default: 20)
- `FUNDAMENTALS_LLM_ENABLED` - Enable LLM equity research in fundamentals agent (default: true)
- `PARALLEL_AGENTS` - Run data agents in parallel vs sequential (default: true)
- `OPENBB_OPTIONS_PROVIDER` - Options data provider for OpenBB (default: yfinance; cboe not bundled)
- `RSI_PERIOD` - RSI calculation period (default: 14)
- `MACD_FAST` / `MACD_SLOW` / `MACD_SIGNAL` - MACD parameters (default: 12/26/9)
- `BB_PERIOD` / `BB_STD` - Bollinger Bands parameters (default: 20/2)
- `MACRO_AGENT_ENABLED` - Enable/disable macroeconomic agent (default: true)
- `OPTIONS_AGENT_ENABLED` - Enable/disable options flow agent (default: true)
- `SCHEDULER_ENABLED` - Enable/disable background scheduler (default: true)
- `SCHEDULER_MIN_INTERVAL` - Minimum schedule interval in minutes (default: 30)
- `ALERTS_ENABLED` - Enable/disable alert evaluation after analysis (default: true)
- `TWITTER_BEARER_TOKEN` - Twitter/X API v2 Bearer Token for social data (optional, supplementary)
- `TWITTER_MAX_RESULTS` - Max tweets to fetch per analysis (default: 50)
- `TWITTER_MIN_ENGAGEMENT` - Minimum engagement filter for tweets (default: 0)

## Running the Application

### Start Backend Server

```bash
# Activate virtual environment
source venv/bin/activate

# Start server
python run.py
```

Server runs on `http://localhost:8000`

### Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

### API Endpoints

**Analyze Stock**

```bash
POST /api/analyze/{ticker}?agents={comma-separated agent names}

# All agents (default)
curl -X POST http://localhost:8000/api/analyze/NVDA

# Specific agents only
curl -X POST "http://localhost:8000/api/analyze/NVDA?agents=market,technical"
```

**Get Latest Analysis**

```bash
GET /api/analysis/{ticker}/latest
curl http://localhost:8000/api/analysis/NVDA/latest
```

**Get History**

```bash
GET /api/analysis/{ticker}/history?limit=10
curl http://localhost:8000/api/analysis/NVDA/history
```

**SSE Stream (Real-time Updates)**

```bash
GET /api/analyze/{ticker}/stream?agents={comma-separated agent names}
curl -N http://localhost:8000/api/analyze/NVDA/stream
```

**Export Analysis as CSV**

```bash
GET /api/analysis/{ticker}/export/csv?analysis_id={optional_id}

# Latest analysis
curl -O http://localhost:8000/api/analysis/NVDA/export/csv

# Specific analysis
curl -O "http://localhost:8000/api/analysis/NVDA/export/csv?analysis_id=3"
```

**Health Check**

```bash
GET /health
curl http://localhost:8000/health
```

**Detailed History (Paginated + Filtered)**

```bash
GET /api/analysis/{ticker}/history/detailed?limit=20&offset=0&recommendation=BUY
```

**Analyzed Tickers**

```bash
GET /api/analysis/tickers
```

**Delete Analysis**

```bash
DELETE /api/analysis/{analysis_id}
```

**Watchlist CRUD**

```bash
POST   /api/watchlists                           # Create watchlist
GET    /api/watchlists                            # List all watchlists
GET    /api/watchlists/{id}                       # Get watchlist with latest analyses
PUT    /api/watchlists/{id}                       # Rename watchlist
DELETE /api/watchlists/{id}                       # Delete watchlist
POST   /api/watchlists/{id}/tickers               # Add ticker
DELETE /api/watchlists/{id}/tickers/{ticker}       # Remove ticker
POST   /api/watchlists/{id}/analyze               # Batch analyze (SSE stream)
```

**Portfolio CRUD**

```bash
GET    /api/portfolio                      # Get portfolio profile + holdings summary
PUT    /api/portfolio/profile              # Update portfolio profile (risk limits)
GET    /api/portfolio/holdings             # List holdings
POST   /api/portfolio/holdings             # Add holding (ticker, shares, avg_cost, sector, beta)
PUT    /api/portfolio/holdings/{id}        # Update holding
DELETE /api/portfolio/holdings/{id}        # Remove holding
```

**Calibration**

```bash
GET /api/calibration/summary              # Overall calibration health across tickers
GET /api/calibration/ticker/{ticker}      # Per-ticker calibration snapshots
GET /api/calibration/reliability          # Confidence reliability bins
```

**Rollout**

```bash
GET /api/rollout/phase7/status            # Phase 7 rollout gate metrics and promotion status
```

**Macro Events**

```bash
GET /api/macro-events                     # Upcoming macro catalyst calendar
```

**Export Analysis as PDF**

```bash
GET /api/analysis/{ticker}/export/pdf?analysis_id={optional_id}

# Latest analysis
curl -O http://localhost:8000/api/analysis/NVDA/export/pdf

# Specific analysis
curl -O "http://localhost:8000/api/analysis/NVDA/export/pdf?analysis_id=3"
```

**Schedule CRUD**

```bash
POST   /api/schedules                            # Create schedule (ticker, interval_minutes)
GET    /api/schedules                             # List all schedules
GET    /api/schedules/{id}                        # Get schedule with recent runs
PUT    /api/schedules/{id}                        # Update schedule (interval, enabled)
DELETE /api/schedules/{id}                        # Delete schedule
```

**Alert CRUD**

```bash
POST   /api/alerts                               # Create alert rule (ticker, rule_type, threshold)
GET    /api/alerts                                # List all rules (?ticker=SYMBOL)
GET    /api/alerts/{id}                           # Get specific rule
PUT    /api/alerts/{id}                           # Update rule
DELETE /api/alerts/{id}                           # Delete rule
GET    /api/alerts/notifications                  # Get notifications (?unacknowledged=true)
GET    /api/alerts/notifications/count            # Unacknowledged count (badge)
POST   /api/alerts/notifications/{id}/acknowledge # Mark as read
```

## Database Schema

**SQLite Database**: `market_research.db`

### Tables

1. **`analyses`** - Main analysis records
   - `id`, `ticker`, `timestamp`, `recommendation`, `score`, `confidence`, `reasoning`

2. **`agent_results`** - Individual agent outputs
   - `id`, `analysis_id`, `agent_name`, `data` (JSON), `duration_seconds`

3. **`price_history`** - Cached price data
   - `ticker`, `timestamp`, `open`, `high`, `low`, `close`, `volume`

4. **`news_cache`** - Cached news articles
   - `ticker`, `title`, `source`, `url`, `summary`, `sentiment_score`, `published_at`

5. **`sentiment_scores`** - Sentiment factor breakdown
   - `analysis_id`, `overall_score`, `news_sentiment`, `social_sentiment`

6. **`watchlists`** - User-created watchlists
   - `id`, `name` (UNIQUE), `created_at`, `updated_at`

7. **`watchlist_tickers`** - Many-to-many: watchlist ↔ ticker
   - `id`, `watchlist_id`, `ticker`, `added_at`, UNIQUE(`watchlist_id`, `ticker`)

8. **`schedules`** - Recurring analysis configuration
   - `id`, `ticker` (UNIQUE), `interval_minutes`, `agents`, `enabled`, `last_run_at`, `next_run_at`

9. **`schedule_runs`** - Schedule execution audit log
   - `id`, `schedule_id`, `analysis_id`, `started_at`, `completed_at`, `success`, `error`

10. **`alert_rules`** - User-defined alert conditions
    - `id`, `ticker`, `rule_type`, `threshold`, `enabled`, `created_at`, `updated_at`

11. **`alert_notifications`** - Triggered alert history
    - `id`, `alert_rule_id`, `analysis_id`, `ticker`, `message`, `previous_value`, `current_value`, `acknowledged`

12. **`portfolio_profile`** - Singleton portfolio risk limits (max_position_pct, max_sector_pct, risk_budget_pct, target_portfolio_beta, max_turnover_pct, default_transaction_cost_bps)

13. **`portfolio_holdings`** - Individual stock positions (ticker, shares, avg_cost, market_value, sector, beta)

14. **`macro_catalyst_events`** - Macro event calendar seeds (date, event_type, description)

15. **`analysis_outcomes`** - Post-analysis outcome tracking for calibration (actual_return, accuracy)

16. **`calibration_snapshots`** - Daily calibration snapshots by horizon (accuracy, brier, mean_net_return_pct, mean_drawdown_pct)

17. **`confidence_reliability_bins`** - Confidence bin reliability buckets for ECE calculation

18. **`validation_results`** - Per-analysis validation report (rule + council contradictions, confidence penalty, spot-check flag)

19. **`validation_feedback`** - Human spot-check verdicts (confirmed/flagged) linked to validation_results via validation_id

20. **`thesis_health_snapshots`** - Per-analysis thesis health snapshots (indicator drift, overall health status)

21. **`council_synthesis`** - Council consensus + LLM narrative per council run

Note: `analyses` table has a `signal_contract_v2` (TEXT/JSON) column added via migration at startup.

## Common Tasks

### Adding a New Agent

1. Create file in `src/agents/` (e.g., `new_agent.py`)
2. Inherit from `BaseAgent` in `src/agents/base_agent.py`
3. Implement `async def fetch_data(self) -> Dict[str, Any]`
4. Implement `async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]`
5. Register agent in `src/orchestrator.py` `AGENT_REGISTRY` dict (include dependencies in `requires`)
6. Add agent name to `DEFAULT_AGENTS` list if it should run by default
7. Update database schema if needed

Example:

```python
from src.agents.base_agent import BaseAgent

class NewAgent(BaseAgent):
    async def fetch_data(self) -> Dict[str, Any]:
        # Fetch raw data — use self._data_provider for OpenBB calls (injected by orchestrator)
        # Session is injected automatically; OpenBB calls run via asyncio.to_thread()
        return {"ticker": self.ticker, "data": {...}}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        # Analyze the fetched data
        return {"status": "success", "data": {...}}
```

### Adding OpenBB Data to a New Agent

Follow the established pattern:

1. `self._data_provider` (`OpenBBDataProvider`) is injected by the orchestrator — call its methods directly
2. All `OpenBBDataProvider` methods are sync; call them via `asyncio.to_thread()` or `self._run_blocking()`
3. Wrap provider calls in try/except; fall through to yfinance fallback on failure
4. Add `data_source` field (`"openbb"` or `"yfinance"`) to track which source was used
5. See `src/data_provider.py` for available methods (get_quote, get_history, get_financials, get_macro, get_options)

### Modifying API Endpoints

Edit `src/api.py` - FastAPI application with all routes.

### Changing LLM Provider

Update `.env`:

```bash
LLM_PROVIDER=openai  # or anthropic or xai
OPENAI_API_KEY=sk-...
```

### Debugging Agent Failures

1. Check logs for specific agent errors
2. Review `agent_results` table in database
3. Check `data_source` field in results to see which source was used
4. Test agent individually:

```python
from src.agents.news_agent import NewsAgent
import asyncio

async def test():
    agent = NewsAgent()
    result = await agent.execute("AAPL")
    print(result)

asyncio.run(test())
```

### Debugging OpenBB Data Issues

1. Check that `FMP_API_KEY` and/or `FRED_API_KEY` are set in `.env` for premium providers
2. OpenBB GH#7113: if you see `ImportError: cannot import name 'OBBject_*'`, the `_ensure_obb()` workaround in `src/data_provider.py` must run before `from openbb import obb` — do not import `obb` at module level
3. FMP news endpoint returns 402 on free tier — this is expected; Tavily is the primary news source
4. OpenBB options provider must be `yfinance` (cboe not bundled); set `OPENBB_OPTIONS_PROVIDER=yfinance`
5. Look for log messages: `"OpenBB data provider not available"`, `"falling back to yfinance"`
6. Test OpenBB directly:

```python
from src.data_provider import OpenBBDataProvider
provider = OpenBBDataProvider()
print(provider.get_quote("AAPL"))
```

## Important Patterns

### Orchestrator Pattern

The `Orchestrator` class coordinates all agents:

1. Creates a shared `aiohttp.ClientSession` for connection pooling
2. Creates a shared `OpenBBDataProvider` instance
3. Resolves which agents to run (from `AGENT_REGISTRY`, with dependency enforcement)
4. Injects shared resources (session, data_provider) into each agent
5. Runs data agents in parallel (or sequential if `PARALLEL_AGENTS=false`) using `asyncio.gather()`
6. Runs sentiment agent (depends on news + market + twitter_posts extracted from news results)
7. Passes all results to Solution Agent for synthesis
8. Saves to database
9. Evaluates alert rules (if ALERTS_ENABLED) and triggers notifications
10. Closes shared session in `finally` block

### Agent Base Class

All agents inherit from `BaseAgent` which provides:

- Error handling and timeout management
- Logging and result validation
- `execute()` method that orchestrates: `fetch_data()` → `analyze()` → return result dict
- `_retry_fetch(func)` — exponential backoff with jitter for synchronous fallback calls
- `_run_blocking(func)` — runs sync functions in a thread pool via `asyncio.to_thread()`
- `_shared_session`, `_data_provider` — injected by orchestrator

### OpenBB Data Provider Pattern

All data agents use `OpenBBDataProvider` (`src/data_provider.py`) as the centralized data layer:

1. `fetch_data()` calls `self._data_provider.get_*()` methods via `self._run_blocking()`
2. Provider handles OpenBB SDK initialization (including GH#7113 workaround), credentials, and TTL caching
3. On failure, agents fall back to yfinance directly
4. Data is normalized to match existing dict key formats so `analyze()` methods work unchanged
5. `data_source` field is set to `"openbb"` or `"yfinance"` based on which source succeeded

### Configurable Agent Pipeline

The API accepts a `?agents=` query parameter to select which agents to run:

- Valid agents: `news`, `sentiment`, `fundamentals`, `market`, `technical`, `macro`, `options`
- Dependencies are auto-resolved (e.g., `sentiment` auto-adds `news`)
- Solution agent always runs to synthesize available results
- The `AGENT_REGISTRY` in `orchestrator.py` maps agent names to classes and dependencies

### Data Flow

```
Ticker → Orchestrator → Agents (parallel) → Solution Agent → Database → API Response

Per Agent:
  fetch_data() → [OpenBB (primary)] → [yfinance/NewsAPI/SEC (fallback)] → analyze() → result
```

## Testing

### Run Test Suite (292 tests)

```bash
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Run specific test module
python -m pytest tests/test_database.py -v

# Skip slow tests
python -m pytest tests/ -v -m "not slow"
```

**Test structure:**

- `tests/conftest.py` — Shared fixtures (temp DB, mock responses, agent factory)
- `tests/test_av_cache.py` — 14 tests (TTL, coalescing, key generation, stats)
- `tests/test_av_rate_limiter.py` — 7 tests (limits, concurrency, exhaustion)
- `tests/test_database.py` — 25 tests (CRUD, isolation, indexing, schedules, alerts)
- `tests/test_agents/test_base_agent.py` — 18 tests (validation, execute flow, data provider, retry)
- `tests/test_agents/test_options_agent.py` — 18 tests (analysis, fetch, helpers, fallback)
- `tests/test_orchestrator.py` — 12 tests (resolution, dependencies, parallel, progress)
- `tests/test_api.py` — 22 tests (all endpoints, error handling, SSE, schedules, alerts)
- `tests/test_pdf_report.py` — 10 tests (PDF generation, all rec types, edge cases)
- `tests/test_scheduler.py` — 7 tests (start/stop, job management, execution)
- `tests/test_alert_engine.py` — 12 tests (all rule types, evaluation logic, DB persistence)
- `tests/test_signal_contract.py` — signal contract v2 builder, validator, calibration math
- `tests/test_portfolio_engine.py` — portfolio advisory overlay, position sizing rules
- `tests/test_rollout_canary.py` — phase 7 rollout preflight and stage promotion checks
- `tests/test_rollout_metrics.py` — rollout gate metric helpers and V2 alert types
- `tests/test_backfill_signal_contract.py` — backfill runner for historical analyses
- `tests/test_calibration.py` — confidence calibration and reliability bin logic
- `tests/test_agents/test_solution_agent.py` — solution agent synthesis and signal contract output
- `tests/test_validation_rules.py` — rule engine unit tests (direction, regime, options, technical, penalty capping)
- `tests/test_council_validator_agent.py` — council validator unit tests (LLM mock, parse, graceful fallback)
- `tests/test_validation_integration.py` — end-to-end validation: rule engine, council validator, DB feedback, alert spot_check
- `tests/test_thesis_health.py` — thesis health indicator drift detection, aggregate rollup, baseline snapshot, string indicators
- `tests/test_council_synthesis.py` — deterministic consensus: stance distribution, tie-breaking, disagreements, scenarios, health mode
- `tests/test_council_synthesis_agent.py` — LLM synthesis narrative agent: parse, fallback, prompt construction
- `tests/test_thesis_health_integration.py` — end-to-end thesis health + council synthesis: DB round-trip, alert firing

### Test API Manually

```bash
# Health check
curl http://localhost:8000/health

# Analyze stock
curl -X POST http://localhost:8000/api/analyze/AAPL
```

### Test Individual Agent

```python
from src.agents.market_agent import MarketAgent
import asyncio

async def test():
    agent = MarketAgent()
    result = await agent.execute("NVDA")
    print(result)

asyncio.run(test())
```

## Common Issues & Solutions

### Import Errors

```bash
# Add project root to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

### Database Locked

```bash
# Delete and recreate database
rm market_research.db
python run.py
```

### API Key Errors

- Check `.env` file exists
- Verify API keys are valid
- Ensure correct provider is set

### Agent Timeout

- Increase `AGENT_TIMEOUT` in `.env`
- Check network connectivity
- Verify external API keys are working

### OpenBB Provider Issues

- `OpenBBDataProvider` initializes lazily on first call — startup is fast but the first analysis may be slower
- FRED macro data is cached 24h by the provider (shared across all tickers in the same process)
- FMP equity/fundamentals data is cached with shorter TTLs per ticker
- If OpenBB fails to initialize, `_data_provider` returns `None` for all calls — agents fall back to yfinance
- Check logs for `"openbb package not installed"` or `"OpenBB data provider not available"`
- `OPENBB_OPTIONS_PROVIDER` must be `yfinance` (default); `cboe` is not bundled in the free OpenBB install

### SQLite In-Memory DB in Tests

- SQLite `:memory:` creates a **new independent DB** on each `get_connection()` call — tables created in one call won't exist in the next
- Use `tempfile.NamedTemporaryFile(suffix='.db', delete=False)` for any test that exercises the full DB schema across multiple calls

### Council Agent Loading

- `db_manager.get_analysis_with_agents(analysis_id)` is the correct method to load agent context — returns `agent_results` dict keyed by `agent_type` with `data` already parsed from JSON. Methods `get_analysis_by_id()` and `get_agent_results()` do **not** exist.
- Council endpoint builds config directly from `Config` class: `config = {attr: getattr(Config, attr) for attr in dir(Config) if not attr.startswith('_')}` — orchestrator is instantiated per-request, not a module-level singleton.

## Frontend Integration

The frontend is in `frontend/` directory (React + Vite + Tailwind CSS v4).

**Layout**: 2-7-3 grid with vertical stacked sections (no tabs). Left sidebar: agent pipeline. Center: chart → executive overview → sentiment → news. Right sidebar: recommendation gauge + macro snapshot.

**Theme**: Hero UI dark variant (zinc-based palette)

- Primary: `#006fee` (blue)
- Success: `#17c964` (green)
- Danger: `#f31260` (pink-red)
- Warning: `#f5a524` (amber)
- Background: `#000000` (pure black)
- Content surfaces: `#18181b` → `#27272a` → `#3f3f46` → `#52525b` (zinc scale)

**Summary.jsx Chain-of-Thought Parsing**: The component maps the LLM's numbered reasoning (1-11) to domain-specific sections using `SECTION_META` — each step gets an icon, accent color, and one-line headline extracted from the first sentence. Sections 1 (Fundamentals) and 11 (Final Recommendation) are expanded by default; others are collapsed.

**Agent Data Surfaced in UI**:

- `agent_results.market.data` → PriceChart (price, volume, trend, change %)
- `agent_results.technical.data` → PriceChart (RSI, MACD, signal strength)
- `agent_results.sentiment.data` → Recommendation consensus strip (score, factors)
- `agent_results.news.data` → NewsFeed (articles, headlines)
- `agent_results.macro.data` → MacroSnapshot (indicators, yield curve, economic cycle, risk environment)
- `agent_results.options.data` → OptionsFlow (P/C ratio, unusual activity, max pain, overall signal)
- `agent_results.*.data.data_source` → ContentHeader source badges (OpenBB/YF)
- All agent signals → Recommendation consensus strip (bullish/bearish/neutral dots)

**Backend provides**:

- REST API for historical data
- SSE streaming for real-time progress updates
- JSON responses with full analysis

**Frontend connects via**:

- Axios for HTTP requests
- EventSource (SSE) for live progress
- `http://localhost:8000` as API base URL

## Development Workflow

1. **Make changes** to agents or orchestrator
2. **Run test suite**: `python -m pytest tests/ -v` (292 tests)
3. **Test locally** with curl or Python
4. **Check database** to verify data persistence
5. **Run API tests** to ensure endpoints work
6. **Test SSE stream** for real-time updates
7. **Build frontend** to verify no build errors: `cd frontend && npm run build`
8. **Docker build** (optional): `docker compose up --build`

## Code Style

- **Async/await** for all I/O operations
- **Type hints** on all functions
- **Pydantic models** for data validation
- **Error handling** with try/except in agents
- **Logging** for debugging
- **aiohttp** for all external HTTP requests in agents
- **`asyncio.gather()`** for concurrent API calls within agents

## Security Notes

- API keys stored in `.env` (not committed to git)
- `.env.example` provided as template
- Database is local SQLite (not exposed)
- CORS configured for frontend access
- OpenBB credentials set via `obb.account.login()` or provider-specific env vars (`FMP_API_KEY`, `FRED_API_KEY`)
- Twitter Bearer Token: use raw value from `.env` — do NOT URL-decode `%2B`/`%3D` characters (causes 401)

## Performance Considerations

- Agents run in **parallel** for speed (configurable via `PARALLEL_AGENTS`)
- **Shared `aiohttp` session** with connection pooling across all agents per analysis
- **Shared `OpenBBDataProvider`** instance with TTL cache deduplicates repeated requests across agents
- OpenBB calls run in a thread pool via `asyncio.to_thread()` to avoid blocking the event loop
- FRED macro data cached 24h (shared across tickers); FMP data cached per-ticker with shorter TTL
- Database **caching** reduces API calls
- Agent **timeout** prevents hanging
- SSE for **real-time** progress streaming (no polling)
- `return_exceptions=True` in `asyncio.gather()` prevents one failed agent from blocking others

## Feature History

All implementation plans and their completion status are indexed at [`docs/plans/INDEX.md`](docs/plans/INDEX.md).

## Next Steps for AI Assistants

When working with this codebase:

1. **Read relevant files** before making changes
2. **Test changes** with individual agent tests first
3. **Check database schema** if modifying data structures
4. **Update `.env.example`** if adding new config options
5. **Maintain async patterns** throughout
6. **Preserve error handling** in all agents
7. **Use type hints** for clarity
8. **Follow existing agent patterns** when adding new ones
9. **Use `OpenBBDataProvider`** when adding new data sources — extend `src/data_provider.py` with new methods
10. **Keep fallback behavior** — never remove existing data sources

## File Reading Priority

For most tasks, read these files first:

1. `src/orchestrator.py` - Understand workflow
2. `src/agents/base_agent.py` - Understand agent interface
3. Specific agent file you're modifying
4. `src/models.py` - Understand data structures
5. `src/config.py` - Understand configuration options
6. `src/database.py` - Understand persistence

## Quick Reference Commands

```bash
# Start backend server
source venv/bin/activate
python run.py

# Start frontend
cd frontend && npm run dev

# Build frontend
cd frontend && npm run build

# Run test suite
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Test API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/analyze/AAPL

# Check database
sqlite3 market_research.db "SELECT * FROM analyses ORDER BY timestamp DESC LIMIT 1;"

# Docker (production)
docker compose up --build

# Docker (development with hot-reload)
docker compose -f docker-compose.dev.yml up --build

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install
```

## Response Format Example

```json
{
  "success": true,
  "ticker": "NVDA",
  "analysis_id": 1,
  "analysis": {
    "recommendation": "BUY|HOLD|SELL",
    "score": "-100 to 100",
    "confidence": "0.0 to 1.0",
    "reasoning": "Detailed explanation...",
    "risks": ["Risk 1", "Risk 2"],
    "opportunities": ["Opp 1", "Opp 2"],
    "price_targets": {
      "entry": 150.0,
      "target": 175.0,
      "stop_loss": 140.0
    },
    "position_size": "SMALL|MEDIUM|LARGE",
    "time_horizon": "SHORT_TERM|MEDIUM_TERM|LONG_TERM"
  },
  "agent_results": {
    "news": { "data_source": "openbb", "...": "..." },
    "sentiment": { "...": "..." },
    "fundamentals": { "data_source": "openbb", "...": "..." },
    "market": { "data_source": "openbb", "...": "..." },
    "technical": { "data_source": "openbb", "...": "..." },
    "macro": { "data_source": "openbb", "...": "..." },
    "options": { "data_source": "yfinance", "...": "..." }
  },
  "duration_seconds": 32.5
}
```

## License

MIT License - See project README.md for details.
