# Analysis Intelligence Upgrade — Design Document

**Date**: 2026-02-17
**Approach**: C — "Analysis Intelligence" (smarts-first, UX polish deferred)

## Goal

Make the analysis output meaningfully better and the platform more robust. Enable all V2 features by default, ground the LLM in its own track record, prevent wasted API budget on invalid tickers, add portfolio-level risk aggregation, and fix the three most impactful stability issues.

## Sections

### 1. Enable V2 Features by Default

Flip all 11 V2 feature flags in `src/config.py` from `"false"` to `"true"`:

- `SIGNAL_CONTRACT_V2_ENABLED` — EV scores, calibrated confidence, regime labels
- `COT_PERSISTENCE_ENABLED` — full chain-of-thought stored in DB
- `PORTFOLIO_OPTIMIZER_V2_ENABLED` — advanced position sizing
- `CALIBRATION_ECONOMICS_ENABLED` — net-return calibration
- `ALERTS_V2_ENABLED` — EV/regime/data-quality alert types
- `WATCHLIST_RANKING_ENABLED` — EV-ranked watchlist ordering
- `UI_PM_DASHBOARD_ENABLED` — frontend PM features
- All 4 `SCHEDULED_*` variants

Flags remain overridable via `.env`.

**Files**: `src/config.py`

### 2. Feed Calibration Data into Solution Agent Prompt

Inject a `## HISTORICAL ACCURACY` section into the LLM prompt so the model can ground its confidence in its own track record.

- Orchestrator already computes `hit_rate_by_horizon` in `_attach_signal_contract_v2()`
- Pass calibration context into `SolutionAgent.__init__()` as optional `calibration_context` dict
- Solution agent appends accuracy block to prompt before reasoning instructions
- DRY the duplicated ~200-line prompt between `_synthesize_with_llm` and `_synthesize_with_openai` into a shared `_build_prompt()` method

**Files**: `src/orchestrator.py`, `src/agents/solution_agent.py`

### 3. Ticker Validation Before Pipeline Runs

Validate that a ticker is a real, tradeable symbol before burning 22 AV requests and 30+ seconds.

- Add `_validate_ticker()` async method to orchestrator
- Lightweight yfinance `Ticker.info` check for `shortName`
- Runs before `_create_shared_session()` and agent dispatch
- Cache validated tickers in-memory (`set`) — repeat analyses skip the check
- Fail-open: if yfinance is down, skip validation and proceed
- Existing regex check in `api.py` stays as first-pass filter

**Files**: `src/orchestrator.py`

### 4. Cross-Ticker Portfolio Risk Aggregation

Add portfolio-level metrics computed across all holdings.

New `PortfolioEngine.portfolio_risk_summary(holdings, profile)` returning:
- Portfolio beta (weighted-average)
- Sector concentration (% per sector, flag breaches of `max_sector_pct`)
- Top holdings exposure (flag positions exceeding `max_position_pct`)
- Total market value
- Sector diversity score

New endpoint: `GET /api/portfolio/risk-summary`

Pure computation over existing DB data — no external API calls.

**Files**: `src/portfolio_engine.py`, `src/api.py`

### 5. Critical Stability Fixes

**5a. WAL mode for SQLite**
- Add `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` in `DatabaseManager.get_connection()`
- Prevents "database is locked" under scheduler concurrency

**5b. Rate limiter: recursion → while-loop**
- Replace `return await self.acquire()` at `av_rate_limiter.py:75` with a `while True` loop
- Prevents stack overflow under burst load

**5c. Protect `_save_to_database`**
- Wrap `orchestrator.py:219` in try/except
- On DB failure: log error, return analysis with `analysis_id: None` and warning flag
- Completed analysis is never lost due to a write failure

**Files**: `src/database.py`, `src/av_rate_limiter.py`, `src/orchestrator.py`

### 6. Change Summary Uncap + Bulk Analysis Endpoint

**6a. Remove change summary truncation**
- Remove `changes = changes[:6]` at `orchestrator.py:1081`
- Update summary string to include all change labels

**6b. Bulk analysis endpoint**
- `POST /api/analyze/batch` with JSON body `{"tickers": [...], "agents": "..."}`
- SSE stream response (same pattern as watchlist batch)
- Concurrency semaphore of 4
- Each ticker validated (Section 3) before dispatch

**Files**: `src/orchestrator.py`, `src/api.py`

### 7. Frontend — Calibration Card + Diagnostics Cleanup

**7a. CalibrationCard.jsx**
- New component in right sidebar below MacroSnapshot
- Shows overall hit rate, sample size, per-horizon accuracy (1d/7d/30d)
- Uses existing `/api/calibration/summary` and `/api/calibration/reliability` endpoints
- Glassmorphic card matching existing design system
- Graceful empty state when no calibration data exists
- Desktop-first layout (no mobile considerations)

**7b. Remove duplicate AgentPipelineBar from Diagnostics tab**
- `Dashboard.jsx:258-266` renders pipeline bar redundantly inside Diagnostics tab
- Remove it — the sticky header already shows it

**Files**: `frontend/src/components/CalibrationCard.jsx`, `frontend/src/components/Dashboard.jsx`

## Out of Scope (Deferred to UX Polish Pass)

- Mobile responsive layout
- Portfolio P&L / market value refresh
- Smarter welcome screen tickers (recent/watchlist)
- Keyboard navigation / accessibility
- `asyncio.to_thread` for DB ops
- `AVCache` maxsize / LRU eviction
- Separate `SOLUTION_AGENT_TIMEOUT`
- SSE heartbeat pings
- Structured error response model
- Transitive dependency resolution in `_resolve_agents`
- SentimentAgent contract cleanup
