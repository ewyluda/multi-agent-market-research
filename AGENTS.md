# AGENTS.md - Project Guide for Coding Agents

## Mission
Build and maintain a multi-agent market research platform that now supports a quant/PM workflow:
- FastAPI backend
- Async multi-agent orchestration with SSE progress streaming
- React frontend (sidebar + PM-focused tabbed workspace)
- SQLite-backed analyses, outcomes/calibration, watchlists, schedules, portfolio data, and alerts

## Quickstart
Backend:
```bash
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Dev Docker stack:
```bash
docker compose -f docker-compose.dev.yml up --build
```

## Architecture
Primary request flow:
```
Client -> FastAPI -> Orchestrator -> [Data Agents] -> Solution Agent -> signal_contract_v2 -> PortfolioEngine -> SQLite -> REST/SSE response
```

Scheduled flow:
```
APScheduler -> Orchestrator -> analysis_outcomes/calibration_snapshots/confidence_reliability_bins -> AlertEngine notifications
```

## Core Backend Files
- `src/api.py`: FastAPI app (analysis, SSE, history, export, watchlists, schedules, portfolio, calibration, alerts)
- `src/orchestrator.py`: agent registry/dependencies, parallel execution, diagnostics, `signal_contract_v2` attachment
- `src/signal_contract.py`: deterministic `signal_contract_v2` builder/validator
- `src/portfolio_engine.py`: legacy advisory overlay + optimizer-driven `portfolio_action_v2`
- `src/backfill_signal_contract.py`: 180-day `signal_contract_v2` backfill utility with checkpoint + report output
- `src/database.py`: SQLite schema + idempotent migration guards + CRUD
- `src/scheduler.py`: recurring jobs + calibration economics + reliability bin generation
- `src/alert_engine.py`: post-analysis rule evaluation (legacy + v2 rule types)
- `src/models.py`: API request/response contracts and typed payloads
- `src/pdf_report.py`: branded PDF export generation
- `src/av_rate_limiter.py`: shared Alpha Vantage rate limiter
- `src/av_cache.py`: TTL cache + in-flight request coalescing
- `src/config.py`: env-driven runtime flags and provider config
- `src/rollout_metrics.py`: Phase 7 rollout gate metrics + pass/fail evaluation helpers
- `src/rollout_canary.py`: CLI canary runner for preflight + Stage A/B/C/D rollout checks

## Agent Map
- News: `src/agents/news_agent.py`
- Market: `src/agents/market_agent.py`
- Fundamentals: `src/agents/fundamentals_agent.py`
- Technical: `src/agents/technical_agent.py`
- Macro: `src/agents/macro_agent.py`
- Options: `src/agents/options_agent.py`
- Sentiment: `src/agents/sentiment_agent.py` (depends on news context)
- Synthesis: `src/agents/solution_agent.py`

Default orchestrator pipeline includes:
`news, market, fundamentals, technical, macro, options, sentiment`

## Data Sources
Primary: Alpha Vantage across data agents (market/fundamentals/news/technical/macro/options)

Fallbacks and supplements:
- yfinance (market, fundamentals, technical, options)
- NewsAPI (news fallback)
- SEC EDGAR (company/fundamentals fallback paths)
- Twitter/X API v2 (news + social sentiment context)

LLM providers:
- Anthropic
- OpenAI
- xAI (Grok via OpenAI-compatible client)

## API Surface (Current)
Analysis:
- `POST /api/analyze/{ticker}`
- `GET /api/analyze/{ticker}/stream` (SSE events: `progress`, `result`, `error`)
- `GET /api/analysis/{ticker}/latest`
- `GET /api/analysis/{ticker}/history`
- `GET /api/analysis/{ticker}/history/detailed`
- `GET /api/analysis/tickers`
- `DELETE /api/analysis/{analysis_id}`

Exports:
- `GET /api/analysis/{ticker}/export/csv`
- `GET /api/analysis/{ticker}/export/pdf`

Watchlists:
- `/api/watchlists*` CRUD + ticker membership
- `POST /api/watchlists/{watchlist_id}/analyze` (event-stream payload with `result`, `error`, `done`; optional `?agents=`)
- `GET /api/watchlists/{watchlist_id}/opportunities`

Schedules:
- `/api/schedules*` CRUD + run history

Portfolio:
- `GET /api/portfolio`
- `PUT /api/portfolio/profile`
- `/api/portfolio/holdings*` CRUD

Calibration:
- `GET /api/calibration/summary`
- `GET /api/calibration/ticker/{ticker}`
- `GET /api/calibration/reliability?horizon_days=1|7|30`

Rollout operations:
- `GET /api/rollout/phase7/status?window_hours=`

Macro catalysts:
- `GET /api/macro-events`

Alerts:
- `/api/alerts*` CRUD + notifications + acknowledge + unacknowledged count
- v2 rules (feature-gated): `ev_above`, `ev_below`, `regime_change`, `data_quality_below`, `calibration_drop`

Health:
- `GET /health`

## Frontend
Main app shell:
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/ContentHeader.jsx`
- `frontend/src/components/AnalysisTabs.jsx` (`Overview`, `Risk`, `Opportunities`, `Diagnostics`)
- `frontend/src/components/AgentPipelineBar.jsx`

Feature panels/components:
- History: `frontend/src/components/HistoryDashboard.jsx`
- Watchlists: `frontend/src/components/WatchlistPanel.jsx`
- Schedules: `frontend/src/components/SchedulePanel.jsx`
- Portfolio: `frontend/src/components/PortfolioPanel.jsx`
- Alerts: `frontend/src/components/AlertPanel.jsx`
- Recommendation rail: `frontend/src/components/Recommendation.jsx`
- Summary/rationale/evidence/execution cards: `frontend/src/components/Summary.jsx`

State and API integration:
- Context: `frontend/src/context/AnalysisContext.jsx`
- Hooks: `frontend/src/hooks/useAnalysis.js`, `frontend/src/hooks/useSSE.js`, `frontend/src/hooks/useHistory.js`
- API client: `frontend/src/utils/api.js`

## Configuration
Environment variables are loaded from `.env` (see `src/config.py` and `.env.example`).

Important keys:
- LLM: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`
- Credentials: `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GROK_API_KEY`
- Market/news/social APIs: `ALPHA_VANTAGE_API_KEY`, `NEWS_API_KEY`, `TWITTER_BEARER_TOKEN`
- Runtime: `AGENT_TIMEOUT`, `AGENT_MAX_RETRIES`, `PARALLEL_AGENTS`
- Feature flags:
  - `SIGNAL_CONTRACT_V2_ENABLED`
  - `COT_PERSISTENCE_ENABLED`
  - `PORTFOLIO_OPTIMIZER_V2_ENABLED`
  - `CALIBRATION_ECONOMICS_ENABLED`
  - `ALERTS_V2_ENABLED`
  - `WATCHLIST_RANKING_ENABLED`
  - `UI_PM_DASHBOARD_ENABLED`
  - Scheduled-run rollout overrides:
    - `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED`
    - `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED`
    - `SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED`
    - `SCHEDULED_ALERTS_V2_ENABLED`
  - Existing flags: `MACRO_AGENT_ENABLED`, `OPTIONS_AGENT_ENABLED`, `SCHEDULER_ENABLED`, `ALERTS_ENABLED`
- Scheduler/limits: `SCHEDULER_MIN_INTERVAL`, `AV_RATE_LIMIT_PER_MINUTE`, `AV_RATE_LIMIT_PER_DAY`

## Development Notes
- Keep SSE event names stable: `progress`, `result`, `error` (watchlist stream also emits `done`).
- `signal_contract_v2` is the canonical quant interface when enabled.
- Keep legacy keys (`recommendation`, `score`, `confidence`, `decision_card`, `change_summary`, `portfolio_action`) for compatibility.
- Do not persist/display chain-of-thought by default (`COT_PERSISTENCE_ENABLED=false`).
- Use `GET /api/rollout/phase7/status` for operational gate checks during staged rollout.
- Use `python -m src.rollout_canary --stage ...` for scripted rollout canary checks.
  - Stage C benchmark supports configurable ticker set and required speedup ratio.
  - Use `--stage-c-agents market,technical` to reduce per-ticker API pressure when quotas are tight.
- Preserve `data_source` metadata in agent outputs for provenance.
- Prefer async-safe I/O; wrap blocking SDK calls in `asyncio.to_thread` where needed.
- SQLite schema changes live in `src/database.py`; migrations are manual, explicit, and idempotent.
- Keep orchestrator dependency behavior intact (e.g., sentiment depends on news context).

## Tests
Pytest suite is available under `tests/`:
- `tests/test_api.py`
- `tests/test_orchestrator.py`
- `tests/test_database.py`
- `tests/test_alert_engine.py`
- `tests/test_scheduler.py`
- `tests/test_calibration.py`
- `tests/test_signal_contract.py`
- `tests/test_portfolio_engine.py`
- `tests/test_backfill_signal_contract.py`
- `tests/test_rollout_metrics.py`
- `tests/test_rollout_canary.py`
- `tests/test_pdf_report.py`
- `tests/test_av_cache.py`
- `tests/test_av_rate_limiter.py`
- `tests/test_agents/*`

Run:
```bash
source venv/bin/activate
pytest
```

Legacy manual smoke script still exists at `test_api.py`.
