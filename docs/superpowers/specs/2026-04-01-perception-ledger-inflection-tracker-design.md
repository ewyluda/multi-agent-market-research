# Perception Ledger & Inflection Tracker

**Date**: 2026-04-01
**Status**: Approved
**Scope**: Backend data layer, inflection detection engine, scheduled scanning, frontend dashboard, targeted refactoring

## Overview

A fundamental inflection tracking system that detects when the market's perception of a company's future is shifting — by monitoring KPI changes across multiple independent data sources (earnings transcripts, analyst estimates, sentiment, technicals, macro) and flagging convergent directional shifts.

The system captures a normalized set of KPIs as append-only snapshots every time a ticker is analyzed, runs inflection detection against prior snapshots, scores convergence across sources, and surfaces results through a dedicated frontend dashboard and the existing alert engine.

## Architecture

```
Analysis Run
    │
    ├── [existing] 7 data agents → sentiment → solution → DB save
    │
    ├── [NEW] KPI Extractor → perception_snapshots table
    │
    ├── [NEW] Inflection Detector → inflection_events table
    │                                │
    │                                ├── Alert engine (inflection_detected rule type)
    │                                └── Analysis response includes inflection_summary
    │
    └── [existing] alert evaluation → cleanup

Scheduled Scan (APScheduler)
    │
    ├── Watchlist tickers → bounded concurrency (4 workers)
    │   └── Each ticker → full analysis run (triggers above flow)
    │
    └── Runs at 9 AM / 4 PM ET on weekday schedule

Frontend
    │
    ├── [NEW] Inflection Dashboard view (heatmap + time-series + feed)
    ├── [MODIFIED] Thesis card — inflection badge
    ├── [MODIFIED] Watchlist view — schedule config UI
    └── [FIX] ESLint errors in touched files
```

## Data Model

### perception_snapshots

Append-only table capturing normalized KPI values from each analysis run.

```sql
CREATE TABLE perception_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    analysis_id INTEGER REFERENCES analyses(id),
    captured_at TEXT NOT NULL,
    kpi_name TEXT NOT NULL,
    kpi_category TEXT NOT NULL,
    value REAL,
    value_text TEXT,
    source_agent TEXT NOT NULL,
    source_detail TEXT,
    confidence REAL
);

CREATE INDEX idx_perception_ticker_kpi ON perception_snapshots(ticker, kpi_name, captured_at);
CREATE INDEX idx_perception_analysis ON perception_snapshots(analysis_id);
```

### inflection_events

Detected inflection events with convergence scoring.

```sql
CREATE TABLE inflection_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    analysis_id INTEGER REFERENCES analyses(id),
    kpi_name TEXT NOT NULL,
    direction TEXT CHECK(direction IN ('positive', 'negative')),
    magnitude REAL,
    prior_value REAL,
    current_value REAL,
    pct_change REAL,
    source_agents TEXT,
    convergence_score REAL,
    summary TEXT
);

CREATE INDEX idx_inflection_ticker ON inflection_events(ticker, detected_at);
CREATE INDEX idx_inflection_convergence ON inflection_events(ticker, convergence_score);
```

### watchlists table modification

```sql
ALTER TABLE watchlists ADD COLUMN auto_analyze_schedule TEXT;
-- Values: null (manual only), "daily_am", "daily_pm", "twice_daily"
```

### KPI extraction map

| Agent | KPIs | Category |
|-------|------|----------|
| Fundamentals | forward_pe, price_to_sales, profit_margins, operating_margins, revenue_growth, eps_growth, roe, debt_to_equity | valuation, margins, growth |
| Fundamentals (transcripts) | revenue_guidance, eps_guidance, capex_outlook, growth_targets | guidance |
| Market | analyst_target_median, analyst_target_high, analyst_target_low, analyst_count | analyst |
| Technical | rsi, macd_signal, sma_50_vs_200, price_vs_sma_50 | technical |
| Sentiment | overall_sentiment, news_sentiment, social_sentiment | sentiment |
| Macro | fed_funds_rate, cpi_yoy, gdp_growth, yield_spread | macro |
| Options | put_call_ratio, implied_volatility, max_pain | technical |

## Snapshot Capture

### src/perception_ledger.py

Declarative KPI extractor that runs after DB save in the orchestrator. Each entry in `KPI_EXTRACTORS` maps an agent type to a dict of `kpi_name → (category, extractor_fn)` pairs. Adding a new KPI is one line.

```python
KPI_EXTRACTORS = {
    "fundamentals": {
        "forward_pe":        ("valuation", lambda d: d.get("forward_pe")),
        "price_to_sales":    ("valuation", lambda d: d.get("price_to_sales")),
        "profit_margins":    ("margins",   lambda d: d.get("profit_margins")),
        "operating_margins": ("margins",   lambda d: d.get("operating_margins")),
        "revenue_growth":    ("growth",    lambda d: d.get("revenue_growth")),
        "eps_growth":        ("growth",    lambda d: d.get("eps_growth")),
        "roe":               ("valuation", lambda d: d.get("return_on_equity")),
        "debt_to_equity":    ("valuation", lambda d: d.get("debt_to_equity")),
        "revenue_guidance":  ("guidance",  lambda d: _extract_guidance(d, "revenue")),
        "eps_guidance":      ("guidance",  lambda d: _extract_guidance(d, "eps")),
        "capex_outlook":     ("guidance",  lambda d: _extract_guidance(d, "capex")),
    },
    "market": {
        "analyst_target_median": ("analyst", lambda d: d.get("analyst_estimates", {}).get("price_target_median")),
        "analyst_count":         ("analyst", lambda d: d.get("analyst_estimates", {}).get("analyst_count")),
    },
    "sentiment": {
        "overall_sentiment": ("sentiment", lambda d: d.get("overall_sentiment")),
    },
    "technical": {
        "rsi":            ("technical", lambda d: d.get("rsi")),
        "macd_signal":    ("technical", lambda d: d.get("macd", {}).get("signal")),
        "sma_50_vs_200":  ("technical", lambda d: d.get("sma_50_vs_200")),
        "price_vs_sma_50":("technical", lambda d: d.get("price_vs_sma_50")),
    },
    "macro": {
        "fed_funds_rate": ("macro", lambda d: d.get("fed_funds_rate")),
        "cpi_yoy":        ("macro", lambda d: d.get("cpi_yoy")),
        "gdp_growth":     ("macro", lambda d: d.get("gdp_growth")),
        "yield_spread":   ("macro", lambda d: d.get("yield_spread")),
    },
    "options": {
        "put_call_ratio":     ("technical", lambda d: d.get("put_call_ratio")),
        "implied_volatility": ("technical", lambda d: d.get("implied_volatility")),
        "max_pain":           ("technical", lambda d: d.get("max_pain")),
    },
}
```

**Integration point**: `capture_perception_snapshot(db_manager, analysis_id, ticker, agent_results)` called in `orchestrator.py` after `_save_to_database()`.

Confidence score derived from the analysis's `data_quality_score` in the signal contract. Agents using fallback data sources get lower confidence.

The `_extract_guidance()` helper extracts numeric values from the fundamentals agent's transcript structured extraction output (the regex pre-extraction that already runs before the LLM call — fields like `revenue_guidance_value`, `eps_guidance_value` in the transcript analysis dict). Returns `None` if no guidance was extracted for that quarter.

## Inflection Detection Engine

### src/inflection_detector.py

Compares current snapshot against most recent prior snapshot for the same ticker. Scores changes per KPI and computes cross-source convergence.

**Per-KPI thresholds** (category-level defaults, starting points):

| Category | Min % change | Positive direction |
|----------|-------------|-------------------|
| valuation | 5% | down (lower PE = positive) |
| growth | 10% | up |
| margins | 5% | up |
| guidance | 3% | up (high-signal, low threshold) |
| sentiment | 15% | up |
| analyst | 5% | up |
| technical | 10% | up |
| macro | 5% | per-KPI: fed_funds_rate/cpi_yoy down=positive, gdp_growth/yield_spread up=positive |

**Convergence scoring**:

```
convergence_score = agents_agreeing_on_direction / total_agents_with_inflections
```

Multiple inflections from the same agent count as one agent for convergence purposes — this prevents the fundamentals agent (which produces many KPIs) from dominating the score.

**First-run behavior**: If no prior snapshot exists for a ticker, the detector returns a "baseline established" result with zero inflections. Requires at least two analysis runs to detect shifts.

**Output**: An `inflection_summary` dict attached to the analysis response:

```json
{
    "direction": "positive",
    "convergence_score": 0.85,
    "inflection_count": 7,
    "headline": "Strong positive inflection: guidance raised, analysts revising up, sentiment shift",
    "inflections": [
        {
            "kpi": "revenue_guidance",
            "direction": "positive",
            "pct_change": 12.3,
            "prior_value": 50.0,
            "current_value": 56.15,
            "source_agent": "fundamentals",
            "summary": "Revenue guidance raised +12.3% ($50B → $56.2B)"
        }
    ]
}
```

## Watchlist-Driven Scheduled Tracking

### Schedule configuration

Leverages existing APScheduler in `src/scheduler.py`. Watchlists with `auto_analyze_schedule` set get registered as cron jobs.

```python
INFLECTION_SCHEDULES = {
    "daily_am":    {"cron": "0 9 * * 1-5"},      # 9 AM ET weekdays
    "daily_pm":    {"cron": "0 16 * * 1-5"},      # 4 PM ET weekdays
    "twice_daily": {"cron": "0 9,16 * * 1-5"},    # Both
}
```

### Scheduled job

Iterates watchlist tickers with bounded concurrency (4 workers, existing pattern from watchlist opportunity ranking):

```python
async def run_inflection_scan(watchlist_id: int):
    tickers = db_manager.get_watchlist_tickers(watchlist_id)
    semaphore = asyncio.Semaphore(4)

    async def analyze_one(ticker):
        async with semaphore:
            return await orchestrator.analyze_ticker(ticker)

    await asyncio.gather(*[analyze_one(t) for t in tickers])
```

Snapshot capture and inflection detection happen inside the orchestrator as part of every analysis run — no special handling needed for scheduled vs manual runs.

Jobs are registered/unregistered when watchlist schedule settings change via the API.

## API Endpoints

### New endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/inflections/{ticker}` | Inflection event history for a ticker |
| GET | `/api/inflections/{ticker}/timeseries` | KPI snapshots for charting (accepts `?range=1M\|3M\|6M\|1Y` and `?kpis=forward_pe,sentiment`) |
| GET | `/api/watchlists/{id}/inflections` | Radar view: latest inflections for all tickers in watchlist, sorted by convergence score |
| PUT | `/api/watchlists/{id}/schedule` | Set auto-analyze schedule |

### Modified endpoints

| Method | Path | Change |
|--------|------|--------|
| POST | `/api/analyze/{ticker}` | Response includes `inflection_summary` when prior snapshots exist |
| GET | `/api/analysis/{ticker}/latest` | Response includes `inflection_summary` |

## Frontend

### New: Inflection Dashboard View

New nav item "Inflections" in sidebar, between Watchlist and Portfolio.

**Three-panel layout:**

1. **Ticker Heatmap** (left, ~250px) — All watchlist tickers ranked by latest convergence score. Color-coded horizontal bars (green = positive, red = negative). Click to select ticker for time-series view.

2. **KPI Time-Series Chart** (right, fills remaining width) — Selected ticker's KPI trajectories as multi-line chart. Inflection points marked as dots on the lines. Toggle individual KPI lines on/off. Time range selector: 1M / 3M / 6M / 1Y. Uses lightweight-charts (already a dependency).

3. **Inflection Feed** (bottom, ~200px height) — Chronological feed of detected inflection events across all watchlist tickers. Each card: ticker, date, convergence score, direction, one-line summary. Click to expand and see individual KPI changes.

### Modified: Thesis Card

Small inflection badge when inflections are detected — direction arrow + convergence score. Clicking navigates to the inflection dashboard filtered to that ticker.

### Modified: Watchlist View

Schedule configuration UI — dropdown or toggle to set auto-analyze schedule (Off / Morning / Evening / Twice Daily) per watchlist.

### ESLint fixes in touched files

- Fix React hooks violations in `CouncilPanel.jsx` (conditional useState, line 617) and `Dashboard.jsx` (setState in useEffect, line 201)
- Clean up unused imports/variables in `WatchlistView.jsx`, `HistoryView.jsx`
- Remaining lint errors in untouched files stay as-is

## Backend Refactoring

Targeted extraction of repositories and routers that this feature touches. Not a full refactor — remaining code stays in place.

### Database layer

Extract from `DatabaseManager`:

| New file | Methods extracted | ~LOC |
|----------|------------------|------|
| `src/repositories/analysis_repo.py` | save_analysis, get_analysis_with_agents, get_latest_analysis, history queries | 400 |
| `src/repositories/watchlist_repo.py` | watchlist CRUD, ticker management + new schedule support | 300 |
| `src/repositories/perception_repo.py` | NEW: snapshot CRUD, inflection CRUD, time-series queries, watchlist aggregations | 250 |

`DatabaseManager` keeps remaining ~2,200 LOC (portfolio, alerts, calibration, council, etc.) and delegates to extracted repositories for the methods that moved. Existing callers continue to work — `DatabaseManager` methods become thin wrappers that call the repository.

### API layer

Extract from `api.py` using FastAPI `APIRouter`:

| New file | Routes extracted | ~LOC |
|----------|-----------------|------|
| `src/routers/analysis.py` | `/api/analyze/*`, `/api/analysis/*` | 400 |
| `src/routers/watchlist.py` | `/api/watchlists/*` + new schedule/inflection endpoints | 250 |
| `src/routers/inflection.py` | NEW: `/api/inflections/*` | 150 |

`api.py` keeps remaining ~1,200 LOC and includes routers via `app.include_router()`.

## Sub-project Breakdown

| Sub-project | Scope | Dependencies |
|---|---|---|
| **A: Perception Ledger** | DB schema + migrations, repository extraction (analysis, watchlist, perception), KPI extractors, snapshot capture integration in orchestrator | None |
| **B: Inflection Engine** | Detection logic, convergence scoring, inflection_events persistence, inflection_summary in analysis response, alert rule type | A |
| **C: Scheduled Scanning** | Watchlist schedule column, APScheduler job registration, bounded concurrency scan, schedule API endpoint | A, B |
| **D: Frontend Dashboard** | Inflection view (3 panels), thesis badge, watchlist schedule UI, ESLint fixes in touched files, API router extraction | A, B (needs API endpoints) |

## Out of Scope

- Historical backfill (pulling years of past data) — future enhancement once the ledger is populated
- Threshold calibration against price outcomes — future enhancement similar to existing calibration engine
- Full DatabaseManager refactor (only extracting what this feature touches)
- Full api.py refactor (only extracting touched routes)
- TypeScript migration
- Accessibility overhaul (separate initiative)
- Mobile responsive design (separate initiative)
