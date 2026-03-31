# CLAUDE.md

## Project Overview

**Multi-Agent Market Research Platform** — real-time stock analysis via 7 specialized AI agents running in parallel, synthesized by a solution agent into a final recommendation.

```
User → FastAPI → Orchestrator → [7 Agents in Parallel] → Solution Agent → SQLite → JSON Response
```

## Agents

| Agent | Source | Data | Fallback |
|-------|--------|------|----------|
| News | `news_agent.py` | Tavily (primary) → OpenBB/FMP | empty |
| Sentiment | `sentiment_agent.py` | LLM-powered (5 factors) | N/A |
| Fundamentals | `fundamentals_agent.py` | FMP (profile, financials, earnings, transcripts) | yfinance + SEC EDGAR |
| Market | `market_agent.py` | FMP (quote, price history) | yfinance |
| Technical | `technical_agent.py` | FMP price history + local pandas | yfinance + local calc |
| Macro | `macro_agent.py` | FRED (fed_funds, CPI, GDP, yields, unemployment) | None |
| Options | `options_agent.py` | yfinance via OpenBB | None |
| Solution | `solution_agent.py` | Synthesizes all agent outputs (LLM) | N/A |

All data agents use `OpenBBDataProvider` (`src/data_provider.py`) injected via `agent._data_provider`. Agents do **not** call external APIs directly. Each inherits from `BaseAgent` which provides `_retry_fetch()`, `_run_blocking()`, shared session, and data provider injection.

### Investor Council (`src/agents/council/`)

26 legendary investor personas (opt-in via `POST /api/analyze/{ticker}/council`). 5 primary always-on, 21 secondary opt-in (max 7 total). Loaded dynamically via `importlib.import_module`. Profiles in `profiles.py`.

## Core Files

| File | Purpose |
|------|---------|
| `run.py` | App startup (FastAPI server) |
| `src/api.py` | REST + SSE endpoints |
| `src/orchestrator.py` | Agent coordination, pipeline, shared resources |
| `src/data_provider.py` | OpenBB SDK wrapper; TTL cache, async-safe |
| `src/database.py` | SQLite CRUD, caching, persistence |
| `src/config.py` | Environment variable management |
| `src/models.py` | Pydantic models |
| `src/signal_contract.py` | Signal contract v2 builder/validator |
| `src/portfolio_engine.py` | Portfolio advisory overlay |
| `src/validation_rules.py` | Deterministic rule engine (Tier 1a) |
| `src/thesis_health.py` | Thesis health drift detection |
| `src/council_synthesis.py` | Council consensus aggregation |
| `src/scheduler.py` | APScheduler background jobs |
| `src/alert_engine.py` | Alert rule evaluation |

## Quick Reference

```bash
source venv/bin/activate && python run.py          # Backend on :8000
cd frontend && npm run dev                          # Frontend on :5173
python -m pytest tests/ -v                          # Run tests
curl -X POST http://localhost:8000/api/analyze/AAPL # Analyze stock
curl http://localhost:8000/health                    # Health check
docker compose up --build                           # Docker production
```

## Environment Variables

**Required** (at least one LLM): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GROK_API_KEY`

**Recommended**: `FMP_API_KEY` (equities/fundamentals/transcripts), `FRED_API_KEY` (macro), `TAVILY_API_KEY` (news)

**Optional**: `TWITTER_BEARER_TOKEN` (social sentiment — use raw value, do NOT URL-decode `%2B`/`%3D`)

Key config: `LLM_PROVIDER` (anthropic/openai/xai), `AGENT_TIMEOUT` (30s), `PARALLEL_AGENTS` (true), `FUNDAMENTALS_LLM_ENABLED` (true), `MACRO_AGENT_ENABLED` (true), `OPTIONS_AGENT_ENABLED` (true)

## API Endpoints

**Analysis**: `POST /api/analyze/{ticker}?agents=...`, `GET /api/analyze/{ticker}/stream` (SSE), `GET /api/analysis/{ticker}/latest`, `GET /api/analysis/{ticker}/history/detailed`

**Exports**: `GET /api/analysis/{ticker}/export/csv`, `GET /api/analysis/{ticker}/export/pdf`

**CRUD**: `/api/watchlists*`, `/api/schedules*`, `/api/alerts*`, `/api/portfolio*`

**Council**: `POST/GET /api/analyze/{ticker}/council`, `POST/GET/DELETE /api/thesis/{ticker}`

**Other**: `GET /api/calibration/summary`, `GET /api/rollout/phase7/status`, `GET /api/macro-events`, `GET /health`

## Key Patterns

### Adding a New Agent
1. Create `src/agents/new_agent.py` inheriting `BaseAgent`
2. Implement `async def fetch_data()` and `async def analyze(raw_data)`
3. Use `self._data_provider` for OpenBB calls (injected by orchestrator)
4. Register in `src/orchestrator.py` `AGENT_REGISTRY` dict
5. Add to `DEFAULT_AGENTS` if it should run by default

### Data Provider
- All `OpenBBDataProvider` methods are async with TTL caching
- Methods: `get_quote`, `get_price_history`, `get_company_overview`, `get_financials`, `get_earnings`, `get_earnings_transcript`, `get_technical_indicators`, `get_macro_indicators`, `get_options_chain`, `get_news`
- `get_earnings_transcript()` calls FMP REST API directly (async via aiohttp), not through OpenBB SDK
- FMP transcript endpoint may return 402 on free tier — handled gracefully

### Orchestrator Flow
1. Creates shared `aiohttp.ClientSession` + `OpenBBDataProvider`
2. Resolves agents from `AGENT_REGISTRY` (auto-resolves dependencies)
3. Runs data agents in parallel via `asyncio.gather(return_exceptions=True)`
4. Runs sentiment agent (depends on news + market + twitter_posts)
5. Solution agent synthesizes → DB save → alert evaluation → cleanup

### Council Agent Loading
- `db_manager.get_analysis_with_agents(analysis_id)` loads agent context (returns `agent_results` dict keyed by `agent_type`)
- Methods `get_analysis_by_id()` and `get_agent_results()` do **not** exist
- Council endpoint builds config from `Config` class — orchestrator is per-request, not a singleton

## Frontend

React + Vite + Tailwind CSS v4. Hero UI dark theme (zinc-based).

**Layout**: 64px sidebar + main content (tabbed) + 280px right sidebar. 6 tabs: Overview/Risks/Opportunities/Leadership/Diagnostics/Council. 6 nav views: analysis/history/watchlist/portfolio/schedules/alerts.

**Theme colors**: Primary `#006fee`, Success `#17c964`, Danger `#f31260`, Warning `#f5a524`, Background `#000000`, Surfaces zinc scale.

**Key components**: `Dashboard.jsx` (root), `Summary.jsx` (exports 5 sub-components), `Recommendation.jsx` (SVG gauge), `PriceChart.jsx` (lightweight-charts), `CouncilPanel.jsx` (investor council).

Glass cards use `glass-card` / `glass-card-elevated` CSS classes.

## Database

SQLite `market_research.db` — 21 tables including `analyses`, `agent_results`, `watchlists`, `schedules`, `alert_rules`, `portfolio_holdings`, `thesis_cards`, `council_results`, `validation_results`, `thesis_health_snapshots`, `council_synthesis`.

`analyses` table has `signal_contract_v2` (TEXT/JSON) column added via migration at startup.

## Testing

```bash
python -m pytest tests/ -v                              # All tests
python -m pytest tests/ --cov=src --cov-report=term-missing  # With coverage
```

SQLite `:memory:` creates a new DB on each `get_connection()` call — use `tempfile.NamedTemporaryFile(suffix='.db', delete=False)` for multi-call tests.

## Debugging

- **Agent failures**: Check logs → `agent_results` table → `data_source` field → test agent individually
- **OpenBB issues**: Check `FMP_API_KEY`/`FRED_API_KEY` in `.env`. GH#7113 workaround in `_ensure_obb()` must run before `from openbb import obb`. FMP news returns 402 on free tier (expected). Options provider must be `yfinance`.
- **Import errors**: `export PYTHONPATH=$PYTHONPATH:$(pwd)`
- **DB locked**: `rm market_research.db && python run.py`

## Code Style

Async/await for I/O, type hints on all functions, Pydantic for validation, try/except in agents, `asyncio.gather()` for concurrency.

## Guidelines for AI Assistants

1. Read relevant files before making changes
2. Use `OpenBBDataProvider` for new data sources — extend `src/data_provider.py`
3. Follow existing agent patterns (BaseAgent, data_source tracking, fallback behavior)
4. Maintain async patterns and error handling throughout
5. Test changes: `python -m pytest tests/ -v`
6. All plans indexed at [`docs/plans/INDEX.md`](docs/plans/INDEX.md)

**File reading priority**: `src/orchestrator.py` → `src/agents/base_agent.py` → specific agent → `src/models.py` → `src/config.py` → `src/database.py`
