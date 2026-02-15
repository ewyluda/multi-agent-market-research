# AGENTS.md - Project Guide for Coding Agents

## Mission
Build and maintain a multi-agent stock market analysis platform with:
- FastAPI backend
- Async multi-agent orchestration with SSE progress streaming
- React frontend (sidebar + tabbed analysis workspace)
- SQLite-backed history, watchlists, schedules, and alerts

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
Client -> FastAPI -> Orchestrator -> [Data Agents] -> Solution Agent -> SQLite -> REST/SSE response
```

Scheduled flow:
```
APScheduler -> Orchestrator -> Database -> AlertEngine notifications
```

Core backend files:
- `src/api.py`: FastAPI app (analysis, SSE, history, export, watchlists, schedules, alerts)
- `src/orchestrator.py`: agent registry/dependencies, parallel execution, progress callbacks
- `src/database.py`: SQLite schema + CRUD for analyses, watchlists, schedules, alert rules/notifications
- `src/scheduler.py`: recurring analysis jobs via APScheduler
- `src/alert_engine.py`: post-analysis rule evaluation and notification creation
- `src/pdf_report.py`: branded PDF export generation
- `src/av_rate_limiter.py`: shared Alpha Vantage rate limiter
- `src/av_cache.py`: TTL cache + in-flight request coalescing
- `src/config.py`: env-driven runtime flags and provider config

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
- `/api/watchlists*` CRUD + ticker membership + batch analyze SSE endpoint

Schedules:
- `/api/schedules*` CRUD + run history

Alerts:
- `/api/alerts*` CRUD + notifications + acknowledge + unacknowledged count

Health:
- `GET /health`

## Frontend
Main app shell:
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/components/ContentHeader.jsx`
- `frontend/src/components/AnalysisTabs.jsx`
- `frontend/src/components/AgentPipelineBar.jsx`

Feature panels/components:
- History: `frontend/src/components/HistoryDashboard.jsx`
- Watchlists: `frontend/src/components/WatchlistPanel.jsx`
- Schedules: `frontend/src/components/SchedulePanel.jsx`
- Alerts: `frontend/src/components/AlertPanel.jsx`
- Social sentiment: `frontend/src/components/SocialBuzz.jsx`
- Options: `frontend/src/components/OptionsFlow.jsx`

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
- Feature flags: `MACRO_AGENT_ENABLED`, `OPTIONS_AGENT_ENABLED`, `SCHEDULER_ENABLED`, `ALERTS_ENABLED`
- Scheduler/limits: `SCHEDULER_MIN_INTERVAL`, `AV_RATE_LIMIT_PER_MINUTE`, `AV_RATE_LIMIT_PER_DAY`

## Development Notes
- Keep SSE event names stable: `progress`, `result`, `error` (watchlist stream also emits `done`).
- Preserve `data_source` metadata in agent outputs for provenance.
- Prefer async-safe I/O; wrap blocking SDK calls in `asyncio.to_thread` where needed.
- SQLite schema changes live in `src/database.py`; migrations are manual and explicit.
- Keep orchestrator dependency behavior intact (e.g., sentiment depends on news context).

## Tests
Pytest suite is available under `tests/`:
- `tests/test_api.py`
- `tests/test_orchestrator.py`
- `tests/test_database.py`
- `tests/test_alert_engine.py`
- `tests/test_scheduler.py`
- `tests/test_pdf_report.py`
- `tests/test_av_cache.py`
- `tests/test_av_rate_limiter.py`
- `tests/test_agents/*`

Run:
```bash
pytest
```

Legacy manual smoke script still exists at `test_api.py`.
