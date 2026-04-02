# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Multi-Agent Market Research Platform** — real-time stock analysis via 9 specialized AI agents running in parallel, with thesis and solution synthesis agents, producing actionable recommendations.

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
| Leadership | `leadership_agent.py` | LLM-powered executive assessment | N/A |
| Thesis | `thesis_agent.py` | Two-pass LLM bull/bear debate (synthesis phase) | Pass 1 fallback |
| Solution | `solution_agent.py` | Synthesizes all agent outputs (LLM) | N/A |
| CouncilValidator | `council_validator_agent.py` | Validates council analysis coherence | N/A |
| CouncilSynthesis | `council_synthesis_agent.py` | Aggregates council consensus | N/A |

All data agents use `OpenBBDataProvider` (`src/data_provider.py`) injected via `agent._data_provider`. Agents do **not** call external APIs directly. Each inherits from `BaseAgent` which provides `_retry_fetch()`, `_run_blocking()`, shared session, and data provider injection.

### Investor Council (`src/agents/council/`)

26 legendary investor personas (opt-in via `POST /api/analyze/{ticker}/council`). 5 primary always-on, 21 secondary opt-in (max 7 total). Loaded dynamically via `importlib.import_module`. Profiles in `profiles.py`.

## Core Files

| File | Purpose |
|------|---------|
| `run.py` | App startup (FastAPI server) |
| `src/api.py` | REST + SSE endpoints |
| `src/orchestrator.py` | Agent coordination, pipeline, shared resources |
| `src/data_provider.py` | OpenBB SDK wrapper; TTL cache, async-safe, FMP Ultimate endpoints |
| `src/database.py` | SQLite CRUD, caching, persistence |
| `src/config.py` | Environment variable management |
| `src/models.py` | Pydantic models |
| `src/llm_guardrails.py` | Deterministic LLM output validation (price targets, sentiment, scenarios, cross-checks) |
| `src/signal_contract.py` | Signal contract v2 builder/validator |
| `src/portfolio_engine.py` | Portfolio advisory overlay |
| `src/validation_rules.py` | Deterministic rule engine + recommendation override |
| `src/thesis_health.py` | Thesis health drift detection |
| `src/council_synthesis.py` | Council consensus aggregation |
| `src/scheduler.py` | APScheduler background jobs |
| `src/alert_engine.py` | Alert rule evaluation |
| `src/perception_ledger.py` | KPI extractor — declarative agent→KPI mapping |
| `src/inflection_detector.py` | Inflection detection + convergence scoring |
| `src/repositories/perception_repo.py` | Perception snapshot + inflection event CRUD |
| `src/routers/inflection.py` | `/api/inflections/*` endpoints |

## Quick Reference

```bash
source venv/bin/activate && python run.py                    # Backend on :8000
cd frontend && npm run dev                                   # Frontend on :5173
python -m pytest tests/ -v                                   # Run all tests
python -m pytest tests/test_api.py::test_analyze_ticker -v   # Run single test
python -m pytest tests/ -m "not slow"                        # Skip slow/API tests
python -m pytest tests/ -m integration                       # Integration tests only
python -m pytest tests/ --cov=src --cov-report=term-missing  # With coverage
cd frontend && npm run lint                                  # Lint frontend
curl -X POST http://localhost:8000/api/analyze/AAPL          # Analyze stock
curl http://localhost:8000/health                             # Health check
docker compose up --build                                    # Docker production
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

**Inflections**: `GET /api/inflections/{ticker}`, `GET /api/inflections/{ticker}/timeseries`, `GET /api/watchlists/{id}/inflections`, `PUT /api/watchlists/{id}/schedule`

**Other**: `GET /api/calibration/summary`, `GET /api/rollout/phase7/status`, `GET /api/macro-events`, `GET /health`

## Key Patterns

### Adding a New Agent
1. Create `src/agents/new_agent.py` inheriting `BaseAgent`
2. Implement `async def fetch_data()` and `async def analyze(raw_data)`
3. Use `self._data_provider` for OpenBB calls (injected by orchestrator)
4. Register in `src/orchestrator.py` `AGENT_REGISTRY` dict
5. Add to `DEFAULT_AGENTS` if it should run by default

### Adding a Synthesis Agent (consumes other agents' outputs)
1. Create agent inheriting `BaseAgent` with `__init__(ticker, config, agent_results)`
2. `fetch_data()` returns `agent_results` as-is; `analyze()` does LLM synthesis
3. Register in `AGENT_REGISTRY` but NOT `DEFAULT_AGENTS`
4. Add `_run_<name>_agent()` method to orchestrator, wire into synthesis phase via `asyncio.gather()`
5. Failure must be non-blocking — return `None`, analysis continues without it
6. Pattern: `ThesisAgent`, `SolutionAgent`

### Data Provider
- All `OpenBBDataProvider` methods are async with TTL caching
- **Core methods**: `get_quote`, `get_price_history`, `get_company_overview`, `get_financials`, `get_earnings`, `get_earnings_transcript`, `get_earnings_transcripts`, `get_technical_indicators`, `get_macro_indicators`, `get_options_chain`, `get_news`
- **FMP Ultimate methods**: `get_analyst_estimates`, `get_price_targets`, `get_ratios_ttm`, `get_insider_trading`, `get_share_statistics`, `get_management`, `get_revenue_segments`, `get_peers`, `get_financial_growth`, `get_dcf_valuation`
- `get_earnings_transcript()` calls FMP stable REST API directly (async via aiohttp); `get_earnings_transcripts()` fetches multiple quarters
- Smart transcript truncation: keeps intro (4K) + Q&A section (10K) instead of simple head truncation
- FMP API migrated from `/api/v3/` to `/stable/` endpoints — all legacy URLs return 403

### LLM Guardrails (`src/llm_guardrails.py`)
- `validate_price_targets()` — enforces stop_loss < entry < target, floors/ceilings relative to current price and analyst consensus
- `validate_sentiment()` — clamps scores to [-1,1], normalizes factor weights to sum to 1.0
- `validate_scenarios()` — clamps returns to [-30%,+30%], enforces bull > base > bear monotonicity
- `validate_equity_research()` — regex cross-checks LLM numeric claims against input metrics, warns on >20% deviation
- `validate_thesis_output()` — evidence grounding (fuzzy-match vs extracted facts), catalyst specificity, cross-reference contradictions against agent data
- All functions return `(validated_result, warnings)` — warnings stored in analysis output for transparency
- Recommendation override: if 5+ of 7 agents disagree with LLM recommendation, forced to HOLD via `validation_rules.py`

### Orchestrator Flow
1. Creates shared `aiohttp.ClientSession` + `OpenBBDataProvider`
2. Resolves agents from `AGENT_REGISTRY` (auto-resolves dependencies)
3. Runs data agents in parallel via `asyncio.gather(return_exceptions=True)`
4. Runs sentiment agent (depends on news + market + twitter_posts)
5. Solution + Thesis agents run in parallel (`asyncio.gather`) → DB save → perception snapshot + inflection detection → alert evaluation → cleanup

### Perception Ledger Flow
After DB save, the orchestrator:
1. Calls `extract_kpi_snapshots(agent_results)` — declarative extraction of ~30 KPIs
2. Writes to `perception_snapshots` via `PerceptionRepository`
3. Runs `InflectionDetector.detect(prior, current)` — category-specific thresholds
4. Computes convergence score and persists `inflection_events`
5. Attaches `inflection_summary` to the analysis response

### Adding a New KPI to the Perception Ledger
1. Find the agent's `analyze()` return dict to identify the exact key path
2. Add one entry to `KPI_EXTRACTORS` in `src/perception_ledger.py`
3. The extractor runs automatically on every analysis — no other changes needed

### Council Agent Loading
- `db_manager.get_analysis_with_agents(analysis_id)` loads agent context (returns `agent_results` dict keyed by `agent_type`)
- Methods `get_analysis_by_id()` and `get_agent_results()` do **not** exist
- Council endpoint builds config from `Config` class — orchestrator is per-request, not a singleton

## Frontend

React + Vite + Tailwind CSS v4. Hero UI dark theme (zinc-based).

**Layout**: 64px sidebar + main content (tabbed) + 280px right sidebar. 6 tabs: Overview/Risks/Opportunities/Leadership/Diagnostics/Council. 7 nav views: analysis/history/watchlist/inflections/portfolio/schedules/alerts.

**Theme colors**: Primary `#006fee`, Success `#17c964`, Danger `#f31260`, Warning `#f5a524`, Background `#000000`, Surfaces zinc scale.

**Key components**: `Dashboard.jsx` (root), `Summary.jsx` (exports 5 sub-components), `Recommendation.jsx` (SVG gauge), `PriceChart.jsx` (lightweight-charts), `CouncilPanel.jsx` (investor council), `InflectionView.jsx` (inflection dashboard with heatmap/chart/feed).

Glass cards use `glass-card` / `glass-card-elevated` CSS classes.

## Database

SQLite `market_research.db` — 23 tables including `analyses`, `agent_results`, `watchlists`, `schedules`, `alert_rules`, `portfolio_holdings`, `thesis_cards`, `council_results`, `validation_results`, `thesis_health_snapshots`, `council_synthesis`, `perception_snapshots`, `inflection_events`.

`analyses` table has `signal_contract_v2` (TEXT/JSON) column added via migration at startup.

## Testing

Test markers: `slow` (real API calls, >5s), `integration` (multi-component). Configured in `pyproject.toml` with `asyncio_mode = "auto"`.

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
