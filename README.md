# Multi-Agent Market Research Platform

Real-time AI-powered US equity analysis with a quant PM upgrade layer.

## Overview
This platform runs specialized agents (news, sentiment, fundamentals, market, technical, macro, options) and synthesizes their outputs into a unified decision payload.

The latest architecture adds a quant/PM-oriented interface:
- Deterministic `signal_contract_v2`
- Optimizer-driven `portfolio_action_v2`
- Calibration economics and reliability bins
- EV/regime/quality-aware alerts
- Cross-sectional watchlist opportunity ranking
- PM-focused dashboard tabs and cards

By default, long-form chain-of-thought is not persisted or shown (`COT_PERSISTENCE_ENABLED=false`).

## Quant PM Upgrade (Implemented)
- `signal_contract_v2` generation and validation in `src/signal_contract.py`
- Versioned analysis payloads via `analysis_schema_version` (`v1`/`v2`)
- Deterministic EV/risk/quality/conflict metrics in orchestrator contract build path
- Portfolio optimizer v2 in `src/portfolio_engine.py`
- Calibration economics in scheduler outcomes (`realized_return_net_pct`, drawdown proxy, utility)
- Reliability bin snapshots (`confidence_reliability_bins`) + calibration API
- Signal-contract backfill utility (`src/backfill_signal_contract.py`) with checkpointed 180-day backfill flow
- Phase 7 canary runner (`src/rollout_canary.py`) for preflight + Stage A/B/C/D promotion checks
- Alerts v2 rule taxonomy (`ev_*`, `regime_change`, `data_quality_below`, `calibration_drop`)
- Watchlist bounded-concurrency analysis + opportunities ranking endpoint
- Frontend PM workflow consolidation (`Overview`, `Risk`, `Opportunities`, `Diagnostics`)

## Architecture

```
Client -> FastAPI -> Orchestrator -> [Data Agents] -> Solution Agent
                                                   -> signal_contract_v2
                                                   -> PortfolioEngine
                                                   -> SQLite
                                                   -> REST/SSE response
```

Scheduled flow:

```
APScheduler -> Orchestrator -> analysis_outcomes/calibration_snapshots/reliability_bins -> AlertEngine
```

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- API keys (at least one LLM provider; Alpha Vantage strongly recommended)

### Install
```bash
# Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..

# Configure env
cp .env.example .env
```

### Run
```bash
# Backend
source venv/bin/activate
python run.py

# Frontend
cd frontend
npm run dev
```

### Docker (dev)
```bash
docker compose -f docker-compose.dev.yml up --build
```

## API Endpoints

### Analysis
- `POST /api/analyze/{ticker}`
- `GET /api/analyze/{ticker}/stream`
- `GET /api/analysis/{ticker}/latest`
- `GET /api/analysis/{ticker}/history`
- `GET /api/analysis/{ticker}/history/detailed`
  - supports filters for recommendation/date and v2 fields (`ev_score_7d`, `confidence_calibrated`, `data_quality_score`, `regime_label`)
- `GET /api/analysis/tickers`
- `DELETE /api/analysis/{analysis_id}`

### Exports
- `GET /api/analysis/{ticker}/export/csv`
- `GET /api/analysis/{ticker}/export/pdf`

### Watchlists
- `/api/watchlists*` CRUD + ticker membership
- `POST /api/watchlists/{watchlist_id}/analyze` (event stream, optional `?agents=` filter)
- `GET /api/watchlists/{watchlist_id}/opportunities?limit=&min_quality=&min_ev=`

### Schedules
- `/api/schedules*` CRUD + run history

### Portfolio
- `GET /api/portfolio`
- `PUT /api/portfolio/profile`
- `/api/portfolio/holdings*` CRUD

### Calibration
- `GET /api/calibration/summary`
- `GET /api/calibration/ticker/{ticker}`
- `GET /api/calibration/reliability?horizon_days=1|7|30`

### Rollout Operations
- `GET /api/rollout/phase7/status?window_hours=`
  - returns Stage A/B computed gate status, key metrics, and current feature-flag posture

### Macro Catalysts
- `GET /api/macro-events`

### Alerts
- `/api/alerts*` CRUD + notifications + acknowledge + unacknowledged count
- v2 rule types (feature-gated):
  - `ev_above`, `ev_below`, `regime_change`, `data_quality_below`, `calibration_drop`

### Health
- `GET /health`

## Analysis Payload Compatibility
When `SIGNAL_CONTRACT_V2_ENABLED=true`, analysis responses include:
- `analysis.analysis_schema_version = "v2"`
- `analysis.signal_contract_v2`

Legacy fields are still included for compatibility:
- `recommendation`, `score`, `confidence`, `decision_card`, `change_summary`, `portfolio_action`

Additional v2 fields:
- `analysis.portfolio_action_v2`
- `analysis.ev_score_7d`
- `analysis.confidence_calibrated`
- `analysis.data_quality_score`
- `analysis.regime_label`

## Migration Notes
For existing API/UI consumers, the upgrade is designed to be additive-first.

### 1) No immediate breaking changes
- Legacy fields are still present: `recommendation`, `score`, `confidence`, `decision_card`, `change_summary`, `portfolio_action`.
- Existing integrations can continue to run unchanged while you migrate.

### 2) Preferred read order (new clients)
1. Read `analysis.signal_contract_v2` when available.
2. Fall back to legacy fields when `signal_contract_v2` is missing.
3. Use `analysis.analysis_schema_version` to branch behavior (`v1` vs `v2`).

### 3) Reasoning/CoT policy
- Default behavior is concise rationale only (`rationale_summary`).
- Do not depend on long-form reasoning text persistence unless explicitly enabling `COT_PERSISTENCE_ENABLED=true`.

### 4) Portfolio action migration
- Keep reading legacy `portfolio_action` for backward compatibility.
- Prefer `portfolio_action_v2` when `PORTFOLIO_OPTIMIZER_V2_ENABLED=true` for optimizer trace and target-delta details.

### 5) Alert rule migration
- Base rules remain available at all times.
- v2 rules (`ev_above`, `ev_below`, `regime_change`, `data_quality_below`, `calibration_drop`) are accepted only when `ALERTS_V2_ENABLED=true`.

### 6) Watchlist migration
- Watchlist SSE still emits `result`, `error`, and `done`.
- When `WATCHLIST_RANKING_ENABLED=true`, `done` includes an `opportunities` array.
- Ranked opportunities can also be fetched without rerun via:
  - `GET /api/watchlists/{watchlist_id}/opportunities`

### 7) Calibration migration
- Existing calibration summary remains available.
- New reliability endpoint is additive:
  - `GET /api/calibration/reliability?horizon_days=1|7|30`

### 8) Suggested rollout sequence
1. Deploy with new flags off.
2. Enable scheduler-only overrides first:
   - `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED=true`
   - `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED=true`
   - keep global `SIGNAL_CONTRACT_V2_ENABLED=false` and `CALIBRATION_ECONOMICS_ENABLED=false`.
3. Monitor rollout gates with:
   - `GET /api/rollout/phase7/status?window_hours=72`
4. Migrate readers to v2-first with legacy fallback.
5. Enable optimizer/alerts/watchlist ranking flags incrementally.
6. Remove legacy-only paths after your deprecation window.

### 9) Canary automation
Run API canaries against a deployed environment:
```bash
source venv/bin/activate
python -m src.rollout_canary --base-url http://localhost:8000 --stage all --window-hours 72
```

Stage-specific runs:
```bash
python -m src.rollout_canary --base-url http://localhost:8000 --stage preflight
python -m src.rollout_canary --base-url http://localhost:8000 --stage stage_a --window-hours 72
python -m src.rollout_canary --base-url http://localhost:8000 --stage stage_b --window-hours 72
python -m src.rollout_canary --base-url http://localhost:8000 --stage stage_c --window-hours 72
python -m src.rollout_canary --base-url http://localhost:8000 --stage stage_d --window-hours 72 --frontend-url http://localhost:5173
```

Low-pressure Stage C run for tighter Alpha Vantage quotas:
```bash
python -m src.rollout_canary \
  --base-url http://localhost:8000 \
  --stage stage_c \
  --window-hours 72 \
  --stage-c-tickers AAPL,MSFT,NVDA,AMZN \
  --stage-c-agents market,technical
```

Production-grade Stage C benchmark (20 tickers, >=2x target):
```bash
python -m src.rollout_canary \
  --base-url http://localhost:8000 \
  --stage stage_c \
  --window-hours 72 \
  --stage-c-tickers AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,JPM,UNH,AVGO,LLY,XOM,JNJ,V,PG,MA,HD,COST,MRK,NFLX \
  --stage-c-agents market,technical \
  --stage-c-required-speedup 2.0
```

## Configuration
All runtime configuration is in `.env` (`src/config.py`, `.env.example`).

### Key Feature Flags
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

Default for all above is `false` (safe rollout posture).

## Database
SQLite database file: `market_research.db`

### Core tables
- `analyses`
- `agent_results`
- `sentiment_scores`
- `watchlists`, `watchlist_tickers`
- `schedules`, `schedule_runs`
- `portfolio_profile`, `portfolio_holdings`
- `alert_rules`, `alert_notifications`
- `analysis_outcomes`
- `calibration_snapshots`
- `confidence_reliability_bins`

### Quant PM schema highlights
- `analyses`: `analysis_schema_version`, `signal_contract_v2`, `ev_score_7d`, `confidence_calibrated`, `data_quality_score`, `regime_label`, `rationale_summary`
- `analysis_outcomes`: transaction costs/slippage + net return + drawdown + utility
- `calibration_snapshots`: net return/drawdown/utility summary fields
- `alert_rules`: expanded rule taxonomy for v2 alerts

## Project Structure

```
multi-agent-market-research/
├── src/
│   ├── api.py
│   ├── orchestrator.py
│   ├── signal_contract.py
│   ├── rollout_metrics.py
│   ├── rollout_canary.py
│   ├── portfolio_engine.py
│   ├── backfill_signal_contract.py
│   ├── scheduler.py
│   ├── alert_engine.py
│   ├── database.py
│   ├── models.py
│   ├── config.py
│   └── agents/
│       ├── news_agent.py
│       ├── sentiment_agent.py
│       ├── fundamentals_agent.py
│       ├── market_agent.py
│       ├── technical_agent.py
│       ├── macro_agent.py
│       ├── options_agent.py
│       └── solution_agent.py
├── frontend/src/
│   ├── components/
│   │   ├── Dashboard.jsx
│   │   ├── AnalysisTabs.jsx
│   │   ├── Summary.jsx
│   │   ├── Recommendation.jsx
│   │   ├── WatchlistPanel.jsx
│   │   ├── HistoryDashboard.jsx
│   │   ├── AlertPanel.jsx
│   │   └── PortfolioPanel.jsx
│   ├── hooks/
│   ├── context/
│   └── utils/api.js
├── tests/
│   ├── test_api.py
│   ├── test_orchestrator.py
│   ├── test_database.py
│   ├── test_calibration.py
│   ├── test_signal_contract.py
│   ├── test_portfolio_engine.py
│   ├── test_backfill_signal_contract.py
│   ├── test_rollout_metrics.py
│   ├── test_rollout_canary.py
│   └── test_agents/
├── docs/plans/
│   ├── 2026-02-15-actionable-insights-roadmap.md
│   └── 2026-02-16-quant-pm-upgrade-implementation-plan.md
├── docs/reports/
│   └── signal-contract-backfill-report.md
├── AGENTS.md
└── README.md
```

## Testing

```bash
source venv/bin/activate
pytest
```

Current backend suite status in this branch: `214 passed`.

Frontend quality checks:
```bash
cd frontend
npm run lint
npm run build
```

## Documentation
- Quant PM implementation details: `docs/plans/2026-02-16-quant-pm-upgrade-implementation-plan.md`
- Prior roadmap context: `docs/plans/2026-02-15-actionable-insights-roadmap.md`
- Latest backfill audit report: `docs/reports/signal-contract-backfill-report.md`

## License
MIT
