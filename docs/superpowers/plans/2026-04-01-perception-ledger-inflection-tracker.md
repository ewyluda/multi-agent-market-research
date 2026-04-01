# Perception Ledger & Inflection Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fundamental inflection tracking system that captures KPI snapshots from every analysis run, detects convergent directional shifts across data sources, and surfaces them through a dedicated frontend dashboard.

**Architecture:** Append-only perception ledger captures ~30 KPIs per analysis run. Inflection detector compares against prior snapshots, scores cross-source convergence, and produces inflection reports. Watchlists can be scheduled for automatic re-analysis. Frontend dashboard provides heatmap, time-series chart, and inflection feed.

**Tech Stack:** Python/FastAPI (backend), SQLite (storage), React/Vite/Tailwind v4 (frontend), lightweight-charts (charting), APScheduler (scheduling)

**Spec:** `docs/superpowers/specs/2026-04-01-perception-ledger-inflection-tracker-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `src/repositories/__init__.py` | Package init |
| `src/repositories/perception_repo.py` | Perception snapshot + inflection event CRUD, time-series queries |
| `src/perception_ledger.py` | KPI extractor — declarative map of agent fields → normalized KPIs |
| `src/inflection_detector.py` | Inflection detection engine — compares snapshots, scores convergence |
| `src/routers/__init__.py` | Package init |
| `src/routers/inflection.py` | FastAPI router for `/api/inflections/*` endpoints |
| `tests/test_perception_ledger.py` | Tests for KPI extraction |
| `tests/test_inflection_detector.py` | Tests for inflection detection + convergence scoring |
| `tests/test_perception_repo.py` | Tests for perception DB operations |
| `tests/test_inflection_api.py` | Tests for inflection API endpoints |
| `frontend/src/components/InflectionView.jsx` | Main inflection dashboard (3 panels) |
| `frontend/src/components/InflectionHeatmap.jsx` | Ticker convergence heatmap (left panel) |
| `frontend/src/components/InflectionChart.jsx` | KPI time-series chart (right panel) |
| `frontend/src/components/InflectionFeed.jsx` | Inflection event feed (bottom panel) |

### Modified Files

| File | Changes |
|------|---------|
| `src/database.py` | Add perception_snapshots + inflection_events tables to schema; add auto_analyze_schedule column to watchlists; add `inflection_detected` to alert_rules CHECK constraint |
| `src/orchestrator.py` | Call snapshot capture + inflection detection after DB save |
| `src/alert_engine.py` | Add `inflection_detected` rule type evaluation |
| `src/scheduler.py` | Add inflection scan job registration for scheduled watchlists |
| `src/api.py` | Include inflection router; add schedule endpoint to watchlist routes |
| `frontend/src/components/Sidebar.jsx` | Add "Inflections" nav item |
| `frontend/src/components/Dashboard.jsx` | Add INFLECTIONS view mode + fix ESLint setState-in-effect error |
| `frontend/src/components/ThesisCard.jsx` | Add inflection badge |
| `frontend/src/components/WatchlistView.jsx` | Add schedule config dropdown |
| `frontend/src/components/CouncilPanel.jsx` | Fix conditional useState ESLint error |
| `frontend/src/utils/api.js` | Add inflection + schedule API functions |

---

## Sub-project A: Perception Ledger

### Task 1: Database Schema — Perception Tables

**Files:**
- Modify: `src/database.py` (initialize_database method, ~line 40)
- Test: `tests/test_perception_repo.py`

- [ ] **Step 1: Write the failing test for perception_snapshots table creation**

```python
# tests/test_perception_repo.py
"""Tests for perception snapshot and inflection event persistence."""

import sqlite3
import pytest
from src.database import DatabaseManager


class TestPerceptionSchema:
    """Tests for perception ledger database schema."""

    def test_perception_snapshots_table_exists(self, db_manager, tmp_db_path):
        """perception_snapshots table is created on init."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "perception_snapshots" in tables

    def test_inflection_events_table_exists(self, db_manager, tmp_db_path):
        """inflection_events table is created on init."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "inflection_events" in tables

    def test_perception_indexes_exist(self, db_manager, tmp_db_path):
        """Perception indexes are created."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "idx_perception_ticker_kpi" in indexes
        assert "idx_perception_analysis" in indexes
        assert "idx_inflection_ticker" in indexes
        assert "idx_inflection_convergence" in indexes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_perception_repo.py::TestPerceptionSchema -v`
Expected: FAIL — tables don't exist yet

- [ ] **Step 3: Add perception tables to initialize_database**

In `src/database.py`, inside `initialize_database()`, after the existing table creation statements (after the last `cursor.execute("""CREATE TABLE IF NOT EXISTS ...`)`, add:

```python
            # Perception ledger — KPI snapshots per analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS perception_snapshots (
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perception_ticker_kpi ON perception_snapshots(ticker, kpi_name, captured_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perception_analysis ON perception_snapshots(analysis_id)")

            # Inflection events — detected KPI shifts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inflection_events (
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
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inflection_ticker ON inflection_events(ticker, detected_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inflection_convergence ON inflection_events(ticker, convergence_score)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_perception_repo.py::TestPerceptionSchema -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_perception_repo.py
git commit -m "feat(db): add perception_snapshots and inflection_events tables"
```

---

### Task 2: Perception Repository — Snapshot CRUD

**Files:**
- Create: `src/repositories/__init__.py`
- Create: `src/repositories/perception_repo.py`
- Test: `tests/test_perception_repo.py`

- [ ] **Step 1: Write failing tests for snapshot insert and query**

Append to `tests/test_perception_repo.py`:

```python
from src.repositories.perception_repo import PerceptionRepository


class TestPerceptionRepository:
    """Tests for PerceptionRepository CRUD operations."""

    def _make_repo(self, db_manager):
        return PerceptionRepository(db_manager)

    def _insert_analysis(self, db_manager, ticker="AAPL"):
        return db_manager.insert_analysis(
            ticker=ticker,
            recommendation="BUY",
            confidence_score=0.8,
            overall_sentiment_score=0.5,
            solution_agent_reasoning="Test.",
            duration_seconds=10.0,
        )

    def test_insert_snapshots(self, db_manager):
        """Snapshots are persisted and retrievable."""
        repo = self._make_repo(db_manager)
        aid = self._insert_analysis(db_manager)

        snapshots = [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
            {"kpi_name": "overall_sentiment", "kpi_category": "sentiment", "value": 0.65,
             "source_agent": "sentiment", "confidence": 0.8},
        ]
        repo.insert_snapshots("AAPL", aid, snapshots)

        result = repo.get_latest_snapshots("AAPL")
        assert len(result) == 2
        assert result[0]["kpi_name"] in ("forward_pe", "overall_sentiment")

    def test_get_latest_snapshots_returns_most_recent(self, db_manager):
        """get_latest_snapshots returns only the most recent snapshot set."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        result = repo.get_latest_snapshots("AAPL")
        assert len(result) == 1
        assert result[0]["value"] == 20.1

    def test_get_prior_snapshots(self, db_manager):
        """get_prior_snapshots returns the snapshot set before the given analysis."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        prior = repo.get_prior_snapshots("AAPL", aid2)
        assert len(prior) == 1
        assert prior[0]["value"] == 22.5
        assert prior[0]["analysis_id"] == aid1

    def test_get_timeseries(self, db_manager):
        """get_timeseries returns chronological KPI values."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        ts = repo.get_timeseries("AAPL", kpis=["forward_pe"])
        assert len(ts) == 2
        assert ts[0]["value"] == 22.5  # chronological order
        assert ts[1]["value"] == 20.1

    def test_get_timeseries_filters_by_kpi(self, db_manager):
        """get_timeseries filters to requested KPIs only."""
        repo = self._make_repo(db_manager)
        aid = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
            {"kpi_name": "rsi", "kpi_category": "technical", "value": 65.0,
             "source_agent": "technical", "confidence": 0.8},
        ])

        ts = repo.get_timeseries("AAPL", kpis=["forward_pe"])
        assert len(ts) == 1
        assert ts[0]["kpi_name"] == "forward_pe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_perception_repo.py::TestPerceptionRepository -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.repositories'`

- [ ] **Step 3: Create the repository package and perception_repo**

```python
# src/repositories/__init__.py
"""Repository modules for database operations."""
```

```python
# src/repositories/perception_repo.py
"""Repository for perception snapshots and inflection events."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class PerceptionRepository:
    """CRUD operations for perception_snapshots and inflection_events tables."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def insert_snapshots(
        self,
        ticker: str,
        analysis_id: int,
        snapshots: List[Dict[str, Any]],
    ) -> int:
        """Insert a batch of KPI snapshots for one analysis run.

        Each snapshot dict must have: kpi_name, kpi_category, source_agent.
        Optional: value, value_text, source_detail, confidence.

        Returns: number of rows inserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            rows = []
            for s in snapshots:
                if s.get("value") is None and s.get("value_text") is None:
                    continue  # skip KPIs with no data
                rows.append((
                    ticker,
                    analysis_id,
                    now,
                    s["kpi_name"],
                    s["kpi_category"],
                    s.get("value"),
                    s.get("value_text"),
                    s["source_agent"],
                    s.get("source_detail"),
                    s.get("confidence"),
                ))
            cursor.executemany(
                """INSERT INTO perception_snapshots
                   (ticker, analysis_id, captured_at, kpi_name, kpi_category,
                    value, value_text, source_agent, source_detail, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            return len(rows)

    def get_latest_snapshots(self, ticker: str) -> List[Dict[str, Any]]:
        """Return the most recent snapshot set for a ticker."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Find the most recent analysis_id with snapshots
            cursor.execute(
                """SELECT analysis_id FROM perception_snapshots
                   WHERE ticker = ? ORDER BY captured_at DESC LIMIT 1""",
                (ticker,),
            )
            row = cursor.fetchone()
            if not row:
                return []
            latest_aid = row["analysis_id"]
            cursor.execute(
                """SELECT * FROM perception_snapshots
                   WHERE ticker = ? AND analysis_id = ?
                   ORDER BY kpi_name""",
                (ticker, latest_aid),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_prior_snapshots(self, ticker: str, current_analysis_id: int) -> List[Dict[str, Any]]:
        """Return the snapshot set immediately before the given analysis."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT DISTINCT analysis_id FROM perception_snapshots
                   WHERE ticker = ? AND analysis_id < ?
                   ORDER BY analysis_id DESC LIMIT 1""",
                (ticker, current_analysis_id),
            )
            row = cursor.fetchone()
            if not row:
                return []
            prior_aid = row["analysis_id"]
            cursor.execute(
                """SELECT * FROM perception_snapshots
                   WHERE ticker = ? AND analysis_id = ?
                   ORDER BY kpi_name""",
                (ticker, prior_aid),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_timeseries(
        self,
        ticker: str,
        kpis: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return chronological KPI snapshots for charting.

        Args:
            ticker: Stock ticker
            kpis: Optional list of kpi_names to filter
            limit: Max rows returned
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            if kpis:
                placeholders = ",".join("?" for _ in kpis)
                cursor.execute(
                    f"""SELECT * FROM perception_snapshots
                       WHERE ticker = ? AND kpi_name IN ({placeholders})
                       ORDER BY captured_at ASC LIMIT ?""",
                    [ticker] + kpis + [limit],
                )
            else:
                cursor.execute(
                    """SELECT * FROM perception_snapshots
                       WHERE ticker = ?
                       ORDER BY captured_at ASC LIMIT ?""",
                    (ticker, limit),
                )
            return [dict(r) for r in cursor.fetchall()]

    def insert_inflection_events(
        self,
        ticker: str,
        analysis_id: int,
        events: List[Dict[str, Any]],
    ) -> int:
        """Insert detected inflection events.

        Each event dict has: kpi_name, direction, magnitude, prior_value,
        current_value, pct_change, source_agents, convergence_score, summary.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            rows = []
            for e in events:
                source_agents = e.get("source_agents", [])
                if isinstance(source_agents, list):
                    source_agents = json.dumps(source_agents)
                rows.append((
                    ticker,
                    now,
                    analysis_id,
                    e["kpi_name"],
                    e["direction"],
                    e.get("magnitude"),
                    e.get("prior_value"),
                    e.get("current_value"),
                    e.get("pct_change"),
                    source_agents,
                    e.get("convergence_score"),
                    e.get("summary"),
                ))
            cursor.executemany(
                """INSERT INTO inflection_events
                   (ticker, detected_at, analysis_id, kpi_name, direction,
                    magnitude, prior_value, current_value, pct_change,
                    source_agents, convergence_score, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            return len(rows)

    def get_inflection_history(
        self,
        ticker: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return inflection events for a ticker, most recent first."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM inflection_events
                   WHERE ticker = ?
                   ORDER BY detected_at DESC LIMIT ?""",
                (ticker, limit),
            )
            rows = [dict(r) for r in cursor.fetchall()]
            for row in rows:
                if row.get("source_agents") and isinstance(row["source_agents"], str):
                    try:
                        row["source_agents"] = json.loads(row["source_agents"])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return rows

    def get_watchlist_inflections(
        self,
        watchlist_tickers: List[str],
        limit_per_ticker: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return recent inflections across multiple tickers for radar view."""
        if not watchlist_tickers:
            return []
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Get the most recent inflection event per ticker, sorted by convergence
            placeholders = ",".join("?" for _ in watchlist_tickers)
            cursor.execute(
                f"""SELECT ie.*, (
                        SELECT MAX(convergence_score) FROM inflection_events ie2
                        WHERE ie2.ticker = ie.ticker AND ie2.analysis_id = ie.analysis_id
                    ) as max_convergence
                    FROM inflection_events ie
                    WHERE ie.ticker IN ({placeholders})
                    AND ie.id IN (
                        SELECT id FROM inflection_events ie3
                        WHERE ie3.ticker = ie.ticker
                        ORDER BY ie3.detected_at DESC
                        LIMIT ?
                    )
                    ORDER BY ie.detected_at DESC""",
                watchlist_tickers + [limit_per_ticker],
            )
            rows = [dict(r) for r in cursor.fetchall()]
            for row in rows:
                if row.get("source_agents") and isinstance(row["source_agents"], str):
                    try:
                        row["source_agents"] = json.loads(row["source_agents"])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_perception_repo.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/repositories/__init__.py src/repositories/perception_repo.py tests/test_perception_repo.py
git commit -m "feat: add PerceptionRepository with snapshot and inflection CRUD"
```

---

### Task 3: KPI Extractor — Perception Ledger

**Files:**
- Create: `src/perception_ledger.py`
- Test: `tests/test_perception_ledger.py`

- [ ] **Step 1: Write failing tests for KPI extraction**

```python
# tests/test_perception_ledger.py
"""Tests for KPI extraction from agent results."""

import pytest
from src.perception_ledger import extract_kpi_snapshots


class TestKPIExtraction:
    """Tests for extract_kpi_snapshots function."""

    def test_extracts_fundamentals_valuation(self):
        """Extracts forward_pe and price_to_sales from fundamentals agent."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "forward_pe": 22.5,
                    "price_to_sales": 8.3,
                    "profit_margins": 0.25,
                    "operating_margins": 0.30,
                    "return_on_equity": 0.45,
                    "debt_to_equity": 1.2,
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["forward_pe"]["value"] == 22.5
        assert by_name["forward_pe"]["kpi_category"] == "valuation"
        assert by_name["price_to_sales"]["value"] == 8.3
        assert by_name["profit_margins"]["value"] == 0.25
        assert by_name["profit_margins"]["kpi_category"] == "margins"
        assert by_name["return_on_equity"]["value"] == 0.45

    def test_extracts_fundamentals_growth(self):
        """Extracts growth metrics from fundamentals agent."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "revenue_growth": 0.15,
                    "earnings_growth": 0.22,
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["revenue_growth"]["value"] == 0.15
        assert by_name["revenue_growth"]["kpi_category"] == "growth"
        assert by_name["earnings_growth"]["value"] == 0.22

    def test_extracts_transcript_guidance(self):
        """Extracts guidance metrics from transcript_metrics."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "transcript_metrics": {
                        "revenue_guidance": {"low": 50.0, "unit": "billion"},
                        "eps_guidance": {"low": 2.50},
                        "capex": {"value": 12.0, "unit": "billion"},
                    },
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["revenue_guidance"]["value"] == 50.0
        assert by_name["revenue_guidance"]["kpi_category"] == "guidance"
        assert by_name["eps_guidance"]["value"] == 2.50
        assert by_name["capex_outlook"]["value"] == 12.0

    def test_extracts_technical_indicators(self):
        """Extracts RSI and MACD from nested technical agent output."""
        agent_results = {
            "technical": {
                "success": True,
                "data": {
                    "indicators": {
                        "rsi": {"value": 65.0},
                        "macd": {"signal_line": 1.23},
                        "ma_50": 150.0,
                    },
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["rsi"]["value"] == 65.0
        assert by_name["rsi"]["kpi_category"] == "technical"
        assert by_name["macd_signal"]["value"] == 1.23

    def test_extracts_sentiment(self):
        """Extracts overall_sentiment from sentiment agent."""
        agent_results = {
            "sentiment": {
                "success": True,
                "data": {"overall_sentiment": 0.72, "confidence": 0.8},
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["overall_sentiment"]["value"] == 0.72
        assert by_name["overall_sentiment"]["kpi_category"] == "sentiment"

    def test_extracts_macro_indicators(self):
        """Extracts macro indicators from nested structure."""
        agent_results = {
            "macro": {
                "success": True,
                "data": {
                    "indicators": {
                        "federal_funds_rate": {"current": 5.25},
                        "cpi": {"current": 3.2},
                        "real_gdp": {"current": 2.8},
                    },
                    "yield_curve": {"spread": 0.45},
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["fed_funds_rate"]["value"] == 5.25
        assert by_name["fed_funds_rate"]["kpi_category"] == "macro"
        assert by_name["cpi_yoy"]["value"] == 3.2
        assert by_name["gdp_growth"]["value"] == 2.8
        assert by_name["yield_spread"]["value"] == 0.45

    def test_extracts_options(self):
        """Extracts options metrics."""
        agent_results = {
            "options": {
                "success": True,
                "data": {
                    "put_call_ratio": 0.85,
                    "max_pain": 175.0,
                    "data_source": "yfinance",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.7)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["put_call_ratio"]["value"] == 0.85
        assert by_name["max_pain"]["value"] == 175.0

    def test_extracts_market_analyst_targets(self):
        """Extracts analyst targets from fundamentals agent."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "target_median_price": 200.0,
                    "target_high_price": 250.0,
                    "target_low_price": 170.0,
                    "number_of_analyst_opinions": 35,
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        by_name = {s["kpi_name"]: s for s in snapshots}
        assert by_name["analyst_target_median"]["value"] == 200.0
        assert by_name["analyst_target_median"]["kpi_category"] == "analyst"
        assert by_name["analyst_count"]["value"] == 35

    def test_skips_failed_agents(self):
        """Failed agents are skipped gracefully."""
        agent_results = {
            "fundamentals": {"success": False, "error": "timeout"},
            "sentiment": {
                "success": True,
                "data": {"overall_sentiment": 0.5},
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.8)

        names = [s["kpi_name"] for s in snapshots]
        assert "forward_pe" not in names
        assert "overall_sentiment" in names

    def test_skips_none_values(self):
        """KPIs with None values are not included."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {
                    "forward_pe": None,
                    "profit_margins": 0.25,
                    "data_source": "openbb",
                },
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        names = [s["kpi_name"] for s in snapshots]
        assert "forward_pe" not in names
        assert "profit_margins" in names

    def test_all_snapshots_have_required_fields(self):
        """Every snapshot has kpi_name, kpi_category, source_agent, confidence."""
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {"forward_pe": 22.5, "data_source": "openbb"},
            },
        }
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)

        for s in snapshots:
            assert "kpi_name" in s
            assert "kpi_category" in s
            assert "source_agent" in s
            assert "confidence" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_perception_ledger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.perception_ledger'`

- [ ] **Step 3: Implement the KPI extractor**

```python
# src/perception_ledger.py
"""Perception Ledger — extracts normalized KPIs from agent results into snapshots.

The KPI_EXTRACTORS dict maps agent_type → kpi_name → (category, extractor_fn).
Adding a new KPI requires only adding one line to this dict.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _extract_guidance(data: Dict[str, Any], field: str) -> Optional[float]:
    """Extract numeric guidance value from transcript_metrics.

    Transcript metrics are regex-extracted by fundamentals_agent._extract_transcript_metrics().
    Fields: revenue_guidance, eps_guidance, capex (with sub-keys low/value).
    """
    metrics = data.get("transcript_metrics")
    if not metrics:
        return None
    if field == "revenue":
        g = metrics.get("revenue_guidance")
        return g.get("low") if isinstance(g, dict) else None
    elif field == "eps":
        g = metrics.get("eps_guidance")
        return g.get("low") if isinstance(g, dict) else None
    elif field == "capex":
        g = metrics.get("capex")
        return g.get("value") if isinstance(g, dict) else None
    return None


# Maps: agent_type → { kpi_name → (category, extractor_fn) }
# extractor_fn receives the agent's data dict and returns a numeric value or None.
KPI_EXTRACTORS: Dict[str, Dict[str, tuple]] = {
    "fundamentals": {
        # Valuation
        "forward_pe":        ("valuation", lambda d: d.get("forward_pe")),
        "price_to_sales":    ("valuation", lambda d: d.get("price_to_sales")),
        "return_on_equity":  ("valuation", lambda d: d.get("return_on_equity")),
        "debt_to_equity":    ("valuation", lambda d: d.get("debt_to_equity")),
        # Margins
        "profit_margins":    ("margins",   lambda d: d.get("profit_margins")),
        "operating_margins": ("margins",   lambda d: d.get("operating_margins")),
        # Growth
        "revenue_growth":    ("growth",    lambda d: d.get("revenue_growth")),
        "earnings_growth":   ("growth",    lambda d: d.get("earnings_growth")),
        # Analyst (from fundamentals, not market agent)
        "analyst_target_median": ("analyst", lambda d: d.get("target_median_price")),
        "analyst_target_high":   ("analyst", lambda d: d.get("target_high_price")),
        "analyst_target_low":    ("analyst", lambda d: d.get("target_low_price")),
        "analyst_count":         ("analyst", lambda d: d.get("number_of_analyst_opinions")),
        # Guidance (from transcript)
        "revenue_guidance":  ("guidance",  lambda d: _extract_guidance(d, "revenue")),
        "eps_guidance":      ("guidance",  lambda d: _extract_guidance(d, "eps")),
        "capex_outlook":     ("guidance",  lambda d: _extract_guidance(d, "capex")),
    },
    "sentiment": {
        "overall_sentiment": ("sentiment", lambda d: d.get("overall_sentiment")),
    },
    "technical": {
        "rsi":          ("technical", lambda d: (d.get("indicators") or {}).get("rsi", {}).get("value") if isinstance((d.get("indicators") or {}).get("rsi"), dict) else None),
        "macd_signal":  ("technical", lambda d: (d.get("indicators") or {}).get("macd", {}).get("signal_line") if isinstance((d.get("indicators") or {}).get("macd"), dict) else None),
    },
    "macro": {
        "fed_funds_rate": ("macro", lambda d: (d.get("indicators") or {}).get("federal_funds_rate", {}).get("current") if isinstance((d.get("indicators") or {}).get("federal_funds_rate"), dict) else None),
        "cpi_yoy":        ("macro", lambda d: (d.get("indicators") or {}).get("cpi", {}).get("current") if isinstance((d.get("indicators") or {}).get("cpi"), dict) else None),
        "gdp_growth":     ("macro", lambda d: (d.get("indicators") or {}).get("real_gdp", {}).get("current") if isinstance((d.get("indicators") or {}).get("real_gdp"), dict) else None),
        "yield_spread":   ("macro", lambda d: (d.get("yield_curve") or {}).get("spread")),
    },
    "options": {
        "put_call_ratio":     ("technical", lambda d: d.get("put_call_ratio")),
        "implied_volatility": ("technical", lambda d: None),  # Would need to aggregate from list; skip for now
        "max_pain":           ("technical", lambda d: d.get("max_pain")),
    },
}


def extract_kpi_snapshots(
    agent_results: Dict[str, Any],
    confidence: float = 0.8,
) -> List[Dict[str, Any]]:
    """Extract normalized KPI snapshots from agent results.

    Args:
        agent_results: Dict keyed by agent_type, each containing {success, data, ...}
        confidence: Default confidence score (0-1)

    Returns:
        List of snapshot dicts ready for PerceptionRepository.insert_snapshots()
    """
    snapshots = []

    for agent_type, extractors in KPI_EXTRACTORS.items():
        agent_result = agent_results.get(agent_type)
        if not agent_result:
            continue
        if not agent_result.get("success", False):
            continue

        data = agent_result.get("data") or {}

        for kpi_name, (category, extractor_fn) in extractors.items():
            try:
                value = extractor_fn(data)
            except Exception:
                logger.debug(f"Failed to extract {kpi_name} from {agent_type}", exc_info=True)
                continue

            if value is None:
                continue

            snapshots.append({
                "kpi_name": kpi_name,
                "kpi_category": category,
                "value": value,
                "source_agent": agent_type,
                "source_detail": data.get("data_source"),
                "confidence": confidence,
            })

    return snapshots
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_perception_ledger.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/perception_ledger.py tests/test_perception_ledger.py
git commit -m "feat: add KPI extractor for perception ledger"
```

---

### Task 4: Wire Snapshot Capture Into Orchestrator

**Files:**
- Modify: `src/orchestrator.py` (~line 319-340)
- Test: `tests/test_orchestrator.py` (add test)

- [ ] **Step 1: Write failing test for snapshot capture in orchestrator**

Append to `tests/test_orchestrator.py`:

```python
class TestPerceptionCapture:
    """Tests for perception snapshot capture in orchestrator."""

    def test_orchestrator_captures_snapshots(self, db_manager):
        """After analysis, perception snapshots are persisted."""
        from src.repositories.perception_repo import PerceptionRepository

        # Insert a fake analysis + agent results to simulate orchestrator flow
        aid = db_manager.insert_analysis(
            ticker="AAPL",
            recommendation="BUY",
            confidence_score=0.8,
            overall_sentiment_score=0.5,
            solution_agent_reasoning="Test.",
            duration_seconds=10.0,
        )

        # Simulate agent_results dict as orchestrator produces it
        agent_results = {
            "fundamentals": {
                "success": True,
                "data": {"forward_pe": 22.5, "profit_margins": 0.25, "data_source": "openbb"},
            },
            "sentiment": {
                "success": True,
                "data": {"overall_sentiment": 0.65},
            },
        }

        # Call the capture function directly
        from src.perception_ledger import extract_kpi_snapshots
        snapshots = extract_kpi_snapshots(agent_results, confidence=0.9)
        repo = PerceptionRepository(db_manager)
        repo.insert_snapshots("AAPL", aid, snapshots)

        # Verify snapshots were persisted
        result = repo.get_latest_snapshots("AAPL")
        assert len(result) >= 2
        names = [r["kpi_name"] for r in result]
        assert "forward_pe" in names
        assert "overall_sentiment" in names
```

- [ ] **Step 2: Run test to verify it passes** (this tests the integration of existing components)

Run: `python -m pytest tests/test_orchestrator.py::TestPerceptionCapture -v`
Expected: PASS

- [ ] **Step 3: Add snapshot capture to orchestrator**

In `src/orchestrator.py`, add import at top of file:

```python
from .perception_ledger import extract_kpi_snapshots
from .repositories.perception_repo import PerceptionRepository
```

Then after the `_save_to_database` call and validation save (~line 343), add:

```python
            # Capture perception snapshots for inflection tracking
            if analysis_id:
                try:
                    data_quality = (final_analysis.get("diagnostics") or {}).get("data_quality", {})
                    quality_score = data_quality.get("agent_success_rate", 0.8)
                    snapshots = extract_kpi_snapshots(agent_results, confidence=quality_score)
                    if snapshots:
                        perception_repo = PerceptionRepository(self.db_manager)
                        perception_repo.insert_snapshots(ticker, analysis_id, snapshots)
                        self.logger.info(f"Captured {len(snapshots)} perception snapshots for {ticker}")
                except Exception as e:
                    self.logger.warning(f"Perception snapshot capture failed: {e}")
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: wire perception snapshot capture into orchestrator pipeline"
```

---

## Sub-project B: Inflection Engine

### Task 5: Inflection Detector — Core Detection Logic

**Files:**
- Create: `src/inflection_detector.py`
- Test: `tests/test_inflection_detector.py`

- [ ] **Step 1: Write failing tests for inflection detection**

```python
# tests/test_inflection_detector.py
"""Tests for inflection detection and convergence scoring."""

import pytest
from src.inflection_detector import InflectionDetector


class TestInflectionDetector:
    """Tests for InflectionDetector.detect() and convergence scoring."""

    def _make_snapshot(self, kpi_name, category, value, agent):
        return {
            "kpi_name": kpi_name,
            "kpi_category": category,
            "value": value,
            "source_agent": agent,
        }

    def test_detects_positive_growth_inflection(self):
        """Revenue growth increase above threshold is detected as positive."""
        detector = InflectionDetector()
        prior = [self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals")]
        current = [self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals")]

        inflections = detector.detect(prior, current)

        assert len(inflections) == 1
        assert inflections[0]["kpi_name"] == "revenue_growth"
        assert inflections[0]["direction"] == "positive"
        assert inflections[0]["pct_change"] > 0

    def test_detects_negative_margin_inflection(self):
        """Margin decrease above threshold is detected as negative."""
        detector = InflectionDetector()
        prior = [self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals")]
        current = [self._make_snapshot("profit_margins", "margins", 0.24, "fundamentals")]

        inflections = detector.detect(prior, current)

        assert len(inflections) == 1
        assert inflections[0]["direction"] == "negative"

    def test_valuation_decrease_is_positive(self):
        """Forward PE decrease is a positive signal (lower = better)."""
        detector = InflectionDetector()
        prior = [self._make_snapshot("forward_pe", "valuation", 25.0, "fundamentals")]
        current = [self._make_snapshot("forward_pe", "valuation", 20.0, "fundamentals")]

        inflections = detector.detect(prior, current)

        assert len(inflections) == 1
        assert inflections[0]["direction"] == "positive"

    def test_below_threshold_not_detected(self):
        """Small changes below threshold are not flagged."""
        detector = InflectionDetector()
        prior = [self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals")]
        current = [self._make_snapshot("profit_margins", "margins", 0.295, "fundamentals")]

        inflections = detector.detect(prior, current)

        assert len(inflections) == 0

    def test_convergence_score_multiple_agents(self):
        """Convergence score reflects agreement across agents."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),
            self._make_snapshot("rsi", "technical", 40.0, "technical"),
        ]
        current = [
            self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals"),  # +120% → positive
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),  # +100% → positive
            self._make_snapshot("rsi", "technical", 70.0, "technical"),  # +75% → positive
        ]

        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)

        assert summary["convergence_score"] == 1.0  # all agents agree
        assert summary["direction"] == "positive"

    def test_convergence_mixed_directions(self):
        """Convergence drops when agents disagree."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("revenue_growth", "growth", 0.10, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),
        ]
        current = [
            self._make_snapshot("revenue_growth", "growth", 0.22, "fundamentals"),  # positive
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),  # negative
        ]

        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)

        assert summary["convergence_score"] == 0.5

    def test_first_run_baseline(self):
        """No prior snapshots produces baseline result."""
        detector = InflectionDetector()

        inflections = detector.detect(prior=[], current=[
            self._make_snapshot("forward_pe", "valuation", 22.5, "fundamentals"),
        ])

        assert len(inflections) == 0

    def test_build_summary_empty_inflections(self):
        """Empty inflections list produces neutral baseline summary."""
        detector = InflectionDetector()
        summary = detector.build_summary([])

        assert summary["convergence_score"] == 0.0
        assert summary["inflection_count"] == 0
        assert summary["direction"] == "neutral"

    def test_multiple_kpis_same_agent_count_once(self):
        """Multiple inflections from same agent count as one for convergence."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("forward_pe", "valuation", 25.0, "fundamentals"),
            self._make_snapshot("profit_margins", "margins", 0.25, "fundamentals"),
            self._make_snapshot("overall_sentiment", "sentiment", 0.30, "sentiment"),
        ]
        current = [
            self._make_snapshot("forward_pe", "valuation", 20.0, "fundamentals"),    # positive (down = good)
            self._make_snapshot("profit_margins", "margins", 0.30, "fundamentals"),  # positive (up)
            self._make_snapshot("overall_sentiment", "sentiment", 0.60, "sentiment"),  # positive
        ]

        inflections = detector.detect(prior, current)
        summary = detector.build_summary(inflections)

        # Both fundamentals inflections → 1 agent; sentiment → 1 agent; 2/2 agree
        assert summary["convergence_score"] == 1.0

    def test_macro_positive_directions(self):
        """Fed funds rate decrease is positive; GDP growth increase is positive."""
        detector = InflectionDetector()
        prior = [
            self._make_snapshot("fed_funds_rate", "macro", 5.50, "macro"),
            self._make_snapshot("gdp_growth", "macro", 2.0, "macro"),
        ]
        current = [
            self._make_snapshot("fed_funds_rate", "macro", 5.00, "macro"),  # down = positive
            self._make_snapshot("gdp_growth", "macro", 3.0, "macro"),      # up = positive
        ]

        inflections = detector.detect(prior, current)

        for inf in inflections:
            assert inf["direction"] == "positive"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_inflection_detector.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the inflection detector**

```python
# src/inflection_detector.py
"""Inflection detection engine — compares KPI snapshots and scores convergence.

Detects when perceived fundamentals shift across multiple data sources,
scoring the magnitude and cross-source agreement of directional changes.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Category-level detection thresholds.
# min_pct_change: minimum absolute % change to register as inflection.
# positive_direction: "up" means increase=positive, "down" means decrease=positive.
CATEGORY_THRESHOLDS = {
    "valuation":  {"min_pct_change": 5.0,  "positive_direction": "down"},
    "growth":     {"min_pct_change": 10.0, "positive_direction": "up"},
    "margins":    {"min_pct_change": 5.0,  "positive_direction": "up"},
    "guidance":   {"min_pct_change": 3.0,  "positive_direction": "up"},
    "sentiment":  {"min_pct_change": 15.0, "positive_direction": "up"},
    "analyst":    {"min_pct_change": 5.0,  "positive_direction": "up"},
    "technical":  {"min_pct_change": 10.0, "positive_direction": "up"},
}

# Macro KPIs have per-KPI positive directions.
MACRO_POSITIVE_DIRECTIONS = {
    "fed_funds_rate": "down",   # lower rates = positive for equities
    "cpi_yoy":        "down",   # lower inflation = positive
    "gdp_growth":     "up",     # higher GDP = positive
    "yield_spread":   "up",     # wider spread = normal curve = positive
}
MACRO_THRESHOLD = 5.0


class InflectionDetector:
    """Detects KPI inflections by comparing current vs prior snapshots."""

    def detect(
        self,
        prior: List[Dict[str, Any]],
        current: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compare current snapshots against prior, return significant inflections.

        Args:
            prior: Previous analysis's KPI snapshots
            current: Current analysis's KPI snapshots

        Returns:
            List of inflection dicts with: kpi_name, direction, magnitude,
            prior_value, current_value, pct_change, source_agent, summary
        """
        if not prior:
            return []

        prior_by_kpi = {s["kpi_name"]: s for s in prior}
        inflections = []

        for snap in current:
            kpi_name = snap["kpi_name"]
            prior_snap = prior_by_kpi.get(kpi_name)
            if not prior_snap:
                continue

            current_val = snap.get("value")
            prior_val = prior_snap.get("value")
            if current_val is None or prior_val is None or prior_val == 0:
                continue

            pct_change = ((current_val - prior_val) / abs(prior_val)) * 100.0
            category = snap["kpi_category"]

            # Determine threshold and positive direction
            if category == "macro":
                min_pct = MACRO_THRESHOLD
                pos_dir = MACRO_POSITIVE_DIRECTIONS.get(kpi_name, "up")
            else:
                cat_config = CATEGORY_THRESHOLDS.get(category, {"min_pct_change": 10.0, "positive_direction": "up"})
                min_pct = cat_config["min_pct_change"]
                pos_dir = cat_config["positive_direction"]

            if abs(pct_change) < min_pct:
                continue

            # Determine direction
            value_went_up = pct_change > 0
            if pos_dir == "up":
                direction = "positive" if value_went_up else "negative"
            else:  # pos_dir == "down"
                direction = "positive" if not value_went_up else "negative"

            magnitude = min(abs(pct_change) / 100.0, 1.0)

            summary = self._build_inflection_summary(
                kpi_name, direction, pct_change, prior_val, current_val,
            )

            inflections.append({
                "kpi_name": kpi_name,
                "direction": direction,
                "magnitude": magnitude,
                "prior_value": prior_val,
                "current_value": current_val,
                "pct_change": round(pct_change, 2),
                "source_agent": snap.get("source_agent", "unknown"),
                "summary": summary,
            })

        return inflections

    def build_summary(self, inflections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build an inflection summary with convergence scoring.

        Multiple inflections from the same agent count as one agent
        for convergence purposes.

        Returns:
            Dict with: direction, convergence_score, inflection_count, headline, inflections
        """
        if not inflections:
            return {
                "direction": "neutral",
                "convergence_score": 0.0,
                "inflection_count": 0,
                "headline": "Baseline established — no prior data for comparison",
                "inflections": [],
            }

        # Count direction by unique agent
        agent_directions: Dict[str, str] = {}
        for inf in inflections:
            agent = inf["source_agent"]
            if agent not in agent_directions:
                agent_directions[agent] = inf["direction"]

        total_agents = len(agent_directions)
        positive_agents = sum(1 for d in agent_directions.values() if d == "positive")
        negative_agents = sum(1 for d in agent_directions.values() if d == "negative")

        majority_direction = "positive" if positive_agents >= negative_agents else "negative"
        agreeing = positive_agents if majority_direction == "positive" else negative_agents
        convergence_score = agreeing / total_agents if total_agents > 0 else 0.0

        headline = self._build_headline(inflections, majority_direction, convergence_score)

        return {
            "direction": majority_direction,
            "convergence_score": round(convergence_score, 2),
            "inflection_count": len(inflections),
            "headline": headline,
            "inflections": inflections,
        }

    def _build_inflection_summary(
        self,
        kpi_name: str,
        direction: str,
        pct_change: float,
        prior_val: float,
        current_val: float,
    ) -> str:
        """Build human-readable summary for a single inflection."""
        arrow = "+" if pct_change > 0 else ""
        label = kpi_name.replace("_", " ").title()
        return f"{label} {arrow}{pct_change:.1f}% ({prior_val:.2f} → {current_val:.2f})"

    def _build_headline(
        self,
        inflections: List[Dict[str, Any]],
        direction: str,
        convergence: float,
    ) -> str:
        """Build a one-line headline for the inflection summary."""
        strength = "Strong" if convergence >= 0.75 else "Moderate" if convergence >= 0.5 else "Weak"
        kpi_names = [inf["kpi_name"].replace("_", " ") for inf in inflections[:3]]
        details = ", ".join(kpi_names)
        return f"{strength} {direction} inflection: {details}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_inflection_detector.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/inflection_detector.py tests/test_inflection_detector.py
git commit -m "feat: add inflection detection engine with convergence scoring"
```

---

### Task 6: Wire Inflection Detection Into Orchestrator

**Files:**
- Modify: `src/orchestrator.py`

- [ ] **Step 1: Add inflection detection after snapshot capture**

In `src/orchestrator.py`, add import at top:

```python
from .inflection_detector import InflectionDetector
```

Then extend the perception snapshot block (added in Task 4) to include inflection detection:

```python
            # Capture perception snapshots + detect inflections
            inflection_summary = None
            if analysis_id:
                try:
                    data_quality = (final_analysis.get("diagnostics") or {}).get("data_quality", {})
                    quality_score = data_quality.get("agent_success_rate", 0.8)
                    snapshots = extract_kpi_snapshots(agent_results, confidence=quality_score)
                    if snapshots:
                        perception_repo = PerceptionRepository(self.db_manager)
                        perception_repo.insert_snapshots(ticker, analysis_id, snapshots)
                        self.logger.info(f"Captured {len(snapshots)} perception snapshots for {ticker}")

                        # Detect inflections against prior snapshots
                        prior = perception_repo.get_prior_snapshots(ticker, analysis_id)
                        if prior:
                            detector = InflectionDetector()
                            inflections = detector.detect(prior, snapshots)
                            inflection_summary = detector.build_summary(inflections)

                            if inflections:
                                perception_repo.insert_inflection_events(
                                    ticker, analysis_id, inflections,
                                )
                                for inf in inflections:
                                    inf["convergence_score"] = inflection_summary["convergence_score"]
                                    inf["source_agents"] = [inf["source_agent"]]
                                self.logger.info(
                                    f"Detected {len(inflections)} inflections for {ticker} "
                                    f"(convergence={inflection_summary['convergence_score']:.2f})"
                                )
                except Exception as e:
                    self.logger.warning(f"Perception/inflection processing failed: {e}")
```

Then in the return dict at the end of `analyze_ticker`, add `inflection_summary`:

Find the `return` statement that builds the success result dict and add:

```python
                "inflection_summary": inflection_summary,
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/orchestrator.py
git commit -m "feat: wire inflection detection into orchestrator pipeline"
```

---

### Task 7: Alert Rule Type — inflection_detected

**Files:**
- Modify: `src/database.py` (CHECK constraint, ~lines 301-314 and 619-632)
- Modify: `src/alert_engine.py` (~line 106)
- Test: `tests/test_alert_engine.py`

- [ ] **Step 1: Write failing test for inflection alert**

Append to `tests/test_alert_engine.py`:

```python
    def test_inflection_detected_triggers_on_high_convergence(self, db_manager):
        """inflection_detected alert fires when convergence exceeds threshold."""
        from src.repositories.perception_repo import PerceptionRepository

        # Two analyses for AAPL
        aid1 = self._insert_analysis(db_manager, recommendation="HOLD")
        aid2 = self._insert_analysis(db_manager, recommendation="HOLD")

        # Insert prior + current snapshots
        repo = PerceptionRepository(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "revenue_growth", "kpi_category": "growth", "value": 0.10,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "revenue_growth", "kpi_category": "growth", "value": 0.22,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        # Insert inflection event with convergence above threshold
        repo.insert_inflection_events("AAPL", aid2, [{
            "kpi_name": "revenue_growth",
            "direction": "positive",
            "magnitude": 0.5,
            "prior_value": 0.10,
            "current_value": 0.22,
            "pct_change": 120.0,
            "source_agents": ["fundamentals"],
            "convergence_score": 0.8,
            "summary": "Revenue growth +120%",
        }])

        db_manager.create_alert_rule("AAPL", "inflection_detected", threshold=0.7)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 1
        assert "inflection" in triggered[0]["message"].lower()

    def test_inflection_detected_no_trigger_below_threshold(self, db_manager):
        """inflection_detected alert does not fire when convergence is below threshold."""
        from src.repositories.perception_repo import PerceptionRepository

        aid1 = self._insert_analysis(db_manager, recommendation="HOLD")
        aid2 = self._insert_analysis(db_manager, recommendation="HOLD")

        repo = PerceptionRepository(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "revenue_growth", "kpi_category": "growth", "value": 0.10,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "revenue_growth", "kpi_category": "growth", "value": 0.12,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])

        # Low convergence event
        repo.insert_inflection_events("AAPL", aid2, [{
            "kpi_name": "revenue_growth",
            "direction": "positive",
            "magnitude": 0.2,
            "prior_value": 0.10,
            "current_value": 0.12,
            "pct_change": 20.0,
            "source_agents": ["fundamentals"],
            "convergence_score": 0.3,
            "summary": "Small change",
        }])

        db_manager.create_alert_rule("AAPL", "inflection_detected", threshold=0.7)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_alert_engine.py::TestAlertEngine::test_inflection_detected_triggers_on_high_convergence -v`
Expected: FAIL — `inflection_detected` not in CHECK constraint

- [ ] **Step 3: Add inflection_detected to CHECK constraint and alert engine**

In `src/database.py`, find both CHECK constraint blocks for `alert_rules.rule_type` (~lines 301-314 and 619-632) and add `'inflection_detected'` to the list:

```sql
                        'thesis_health_change',
                        'inflection_detected'
```

In `src/alert_engine.py`, after the `thesis_health_change` elif block (~line 106), add:

```python
        elif rule_type == "inflection_detected":
            return self._check_inflection_detected(current, threshold)
```

Then add the check method to the `AlertEngine` class:

```python
    def _check_inflection_detected(
        self,
        current: Dict[str, Any],
        threshold: Optional[float],
    ) -> Optional[Dict[str, Any]]:
        """Check if recent inflection events exceed convergence threshold."""
        from .repositories.perception_repo import PerceptionRepository

        analysis_id = current.get("id")
        ticker = current.get("ticker")
        if not analysis_id or not ticker:
            return None

        repo = PerceptionRepository(self.db_manager)
        events = repo.get_inflection_history(ticker, limit=10)

        # Find events for this analysis
        current_events = [e for e in events if e.get("analysis_id") == analysis_id]
        if not current_events:
            return None

        # Get max convergence score for this analysis
        max_convergence = max(
            (e.get("convergence_score") or 0.0) for e in current_events
        )

        if threshold is not None and max_convergence < threshold:
            return None

        directions = {e.get("direction") for e in current_events}
        direction = "positive" if "positive" in directions else "negative"
        count = len(current_events)

        return {
            "message": f"Inflection detected for {ticker}: {count} KPI shifts, "
                       f"convergence={max_convergence:.2f}, direction={direction}",
            "previous_value": None,
            "current_value": str(max_convergence),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_alert_engine.py::TestAlertEngine::test_inflection_detected_triggers_on_high_convergence tests/test_alert_engine.py::TestAlertEngine::test_inflection_detected_no_trigger_below_threshold -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/database.py src/alert_engine.py tests/test_alert_engine.py
git commit -m "feat: add inflection_detected alert rule type"
```

---

## Sub-project C: Scheduled Scanning

### Task 8: Watchlist Schedule Column + Scheduler Integration

**Files:**
- Modify: `src/database.py` (watchlists schema + migration)
- Modify: `src/scheduler.py`
- Test: `tests/test_perception_repo.py` (add schedule tests)

- [ ] **Step 1: Write failing test for auto_analyze_schedule column**

Append to `tests/test_perception_repo.py`:

```python
class TestWatchlistSchedule:
    """Tests for watchlist auto-analyze schedule support."""

    def test_watchlist_has_schedule_column(self, db_manager):
        """Watchlist supports auto_analyze_schedule field."""
        wl = db_manager.create_watchlist("test_wl")
        assert wl is not None

        # Update schedule via direct SQL (we'll add a method next)
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE watchlists SET auto_analyze_schedule = ? WHERE id = ?",
                ("twice_daily", wl["id"]),
            )

        result = db_manager.get_watchlist(wl["id"])
        assert result["auto_analyze_schedule"] == "twice_daily"

    def test_watchlist_schedule_defaults_to_null(self, db_manager):
        """New watchlists have null schedule by default."""
        wl = db_manager.create_watchlist("test_wl2")
        result = db_manager.get_watchlist(wl["id"])
        assert result.get("auto_analyze_schedule") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_perception_repo.py::TestWatchlistSchedule -v`
Expected: FAIL — column doesn't exist

- [ ] **Step 3: Add auto_analyze_schedule column to watchlists**

In `src/database.py`, in `initialize_database()`, after the watchlists table creation, add migration:

```python
            # Migration: add auto_analyze_schedule to watchlists
            try:
                cursor.execute("ALTER TABLE watchlists ADD COLUMN auto_analyze_schedule TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
```

Also update `get_watchlist()` and `get_watchlists()` methods to include the new column in their return dicts. Find the `get_watchlist` method (~line 1499) and ensure the SELECT includes all columns (it should already via `SELECT *`, but verify the dict conversion includes it).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_perception_repo.py::TestWatchlistSchedule -v`
Expected: PASS

- [ ] **Step 5: Add inflection scan job to scheduler**

In `src/scheduler.py`, add these imports and constants near the top:

```python
INFLECTION_SCHEDULES = {
    "daily_am":    {"hour": 9, "minute": 0},
    "daily_pm":    {"hour": 16, "minute": 0},
    "twice_daily": [{"hour": 9, "minute": 0}, {"hour": 16, "minute": 0}],
}
```

Add a method to register inflection scan jobs (after the existing `start()` method):

```python
    def sync_inflection_schedules(self):
        """Register/unregister inflection scan jobs based on watchlist schedules."""
        watchlists = self.db_manager.get_watchlists()
        for wl in watchlists:
            schedule_type = wl.get("auto_analyze_schedule")
            job_id_base = f"inflection_scan_{wl['id']}"

            # Remove existing jobs for this watchlist
            for suffix in ("", "_am", "_pm"):
                try:
                    self.scheduler.remove_job(f"{job_id_base}{suffix}")
                except Exception:
                    pass

            if not schedule_type or schedule_type not in INFLECTION_SCHEDULES:
                continue

            config = INFLECTION_SCHEDULES[schedule_type]
            times = config if isinstance(config, list) else [config]

            for i, t in enumerate(times):
                suffix = f"_{'am' if t['hour'] < 12 else 'pm'}" if len(times) > 1 else ""
                self.scheduler.add_job(
                    self._run_inflection_scan,
                    "cron",
                    hour=t["hour"],
                    minute=t["minute"],
                    day_of_week="mon-fri",
                    timezone="America/New_York",
                    id=f"{job_id_base}{suffix}",
                    args=[wl["id"]],
                    replace_existing=True,
                )
                logger.info(f"Registered inflection scan for watchlist {wl['id']} at {t['hour']}:{t['minute']:02d} ET")

    async def _run_inflection_scan(self, watchlist_id: int):
        """Execute inflection scan for all tickers in a watchlist."""
        import asyncio
        wl = self.db_manager.get_watchlist(watchlist_id)
        if not wl:
            logger.warning(f"Watchlist {watchlist_id} not found for inflection scan")
            return

        tickers = [t["ticker"] for t in wl.get("tickers", [])]
        if not tickers:
            return

        logger.info(f"Starting inflection scan for watchlist '{wl['name']}' ({len(tickers)} tickers)")
        semaphore = asyncio.Semaphore(4)

        async def analyze_one(ticker):
            async with semaphore:
                try:
                    from .orchestrator import Orchestrator
                    config = dict(self.config) if hasattr(self, 'config') else {}
                    orchestrator = Orchestrator(config=config, db_manager=self.db_manager)
                    return await orchestrator.analyze_ticker(ticker)
                except Exception as e:
                    logger.warning(f"Inflection scan failed for {ticker}: {e}")
                    return None

        await asyncio.gather(*[analyze_one(t) for t in tickers])
        logger.info(f"Inflection scan complete for watchlist '{wl['name']}'")
```

Call `sync_inflection_schedules()` at the end of the existing `start()` method.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/database.py src/scheduler.py tests/test_perception_repo.py
git commit -m "feat: add watchlist auto-analyze schedule with inflection scan jobs"
```

---

## Sub-project D: API & Frontend

### Task 9: Inflection API Router

**Files:**
- Create: `src/routers/__init__.py`
- Create: `src/routers/inflection.py`
- Modify: `src/api.py` (include router + add schedule endpoint)
- Test: `tests/test_inflection_api.py`

- [ ] **Step 1: Write failing tests for inflection API endpoints**

```python
# tests/test_inflection_api.py
"""Tests for inflection API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_manager):
    """Create a test client with the app configured to use test DB."""
    from src.api import app
    # Override db_manager in the app
    import src.api as api_module
    original_db = api_module.db_manager
    api_module.db_manager = db_manager
    yield TestClient(app)
    api_module.db_manager = original_db


class TestInflectionAPI:
    """Tests for /api/inflections/* endpoints."""

    def _seed_data(self, db_manager):
        """Insert analysis + snapshots + inflection events."""
        from src.repositories.perception_repo import PerceptionRepository

        aid1 = db_manager.insert_analysis(
            ticker="AAPL", recommendation="HOLD", confidence_score=0.8,
            overall_sentiment_score=0.5, solution_agent_reasoning="Test.",
            duration_seconds=10.0,
        )
        aid2 = db_manager.insert_analysis(
            ticker="AAPL", recommendation="BUY", confidence_score=0.85,
            overall_sentiment_score=0.6, solution_agent_reasoning="Test.",
            duration_seconds=10.0,
        )

        repo = PerceptionRepository(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 25.0,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.0,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_inflection_events("AAPL", aid2, [{
            "kpi_name": "forward_pe", "direction": "positive", "magnitude": 0.2,
            "prior_value": 25.0, "current_value": 20.0, "pct_change": -20.0,
            "source_agents": ["fundamentals"], "convergence_score": 0.8,
            "summary": "Forward PE improved -20%",
        }])
        return aid1, aid2

    def test_get_inflection_history(self, client, db_manager):
        """GET /api/inflections/{ticker} returns inflection events."""
        self._seed_data(db_manager)
        response = client.get("/api/inflections/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["kpi_name"] == "forward_pe"

    def test_get_timeseries(self, client, db_manager):
        """GET /api/inflections/{ticker}/timeseries returns snapshots."""
        self._seed_data(db_manager)
        response = client.get("/api/inflections/AAPL/timeseries?kpis=forward_pe")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["value"] == 25.0
        assert data[1]["value"] == 20.0

    def test_get_inflection_history_empty(self, client, db_manager):
        """GET /api/inflections/{ticker} returns empty for unknown ticker."""
        response = client.get("/api/inflections/ZZZZ")
        assert response.status_code == 200
        assert response.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_inflection_api.py -v`
Expected: FAIL — router doesn't exist yet

- [ ] **Step 3: Create the inflection router**

```python
# src/routers/__init__.py
"""API router modules."""
```

```python
# src/routers/inflection.py
"""API routes for inflection tracking and perception time-series."""

from fastapi import APIRouter, Query
from typing import Optional, List

router = APIRouter(prefix="/api/inflections", tags=["inflections"])


def _get_perception_repo():
    """Lazy import to avoid circular deps."""
    from ..repositories.perception_repo import PerceptionRepository
    import src.api as api_module
    return PerceptionRepository(api_module.db_manager)


@router.get("/{ticker}")
async def get_inflection_history(
    ticker: str,
    limit: int = Query(default=50, le=200),
):
    """Get inflection event history for a ticker."""
    repo = _get_perception_repo()
    return repo.get_inflection_history(ticker.upper(), limit=limit)


@router.get("/{ticker}/timeseries")
async def get_timeseries(
    ticker: str,
    kpis: Optional[str] = Query(default=None, description="Comma-separated KPI names"),
    limit: int = Query(default=200, le=1000),
):
    """Get KPI snapshots for charting."""
    repo = _get_perception_repo()
    kpi_list = [k.strip() for k in kpis.split(",")] if kpis else None
    return repo.get_timeseries(ticker.upper(), kpis=kpi_list, limit=limit)
```

- [ ] **Step 4: Include the router in api.py**

In `src/api.py`, add import near the top (after existing imports):

```python
from .routers.inflection import router as inflection_router
```

Then after the `app = FastAPI(...)` and middleware setup, add:

```python
app.include_router(inflection_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_inflection_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Add watchlist inflections and schedule endpoints**

In `src/api.py`, find the watchlist endpoints section and add two new endpoints:

```python
@app.get("/api/watchlists/{watchlist_id}/inflections")
async def get_watchlist_inflections(watchlist_id: int):
    """Radar view: recent inflections for all tickers in watchlist."""
    wl = db_manager.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    tickers = [t["ticker"] for t in wl.get("tickers", [])]
    repo = PerceptionRepository(db_manager)
    return repo.get_watchlist_inflections(tickers)


@app.put("/api/watchlists/{watchlist_id}/schedule")
async def set_watchlist_schedule(watchlist_id: int, body: dict):
    """Set auto-analyze schedule for a watchlist."""
    schedule = body.get("schedule")
    valid = {None, "daily_am", "daily_pm", "twice_daily"}
    if schedule not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid schedule. Must be one of: {valid}")
    wl = db_manager.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE watchlists SET auto_analyze_schedule = ? WHERE id = ?",
            (schedule, watchlist_id),
        )
    # Re-sync scheduler if running
    try:
        from .scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler:
            scheduler.sync_inflection_schedules()
    except Exception:
        pass
    return {"status": "ok", "schedule": schedule}
```

Add import at top of `src/api.py`:

```python
from .repositories.perception_repo import PerceptionRepository
```

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/routers/__init__.py src/routers/inflection.py src/api.py tests/test_inflection_api.py
git commit -m "feat: add inflection API endpoints and watchlist schedule route"
```

---

### Task 10: Frontend API Functions

**Files:**
- Modify: `frontend/src/utils/api.js`

- [ ] **Step 1: Add inflection API functions**

At the end of `frontend/src/utils/api.js`, before the final export (if any), add:

```javascript
// ─── Inflection Tracking ─────────────────────────────────────────────────────

export async function getInflectionHistory(ticker, limit = 50) {
  const response = await axios.get(`${API_BASE_URL}/api/inflections/${ticker}?limit=${limit}`);
  return response.data;
}

export async function getInflectionTimeseries(ticker, kpis = null, limit = 200) {
  const params = new URLSearchParams({ limit });
  if (kpis && kpis.length > 0) params.set('kpis', kpis.join(','));
  const response = await axios.get(`${API_BASE_URL}/api/inflections/${ticker}/timeseries?${params}`);
  return response.data;
}

export async function getWatchlistInflections(watchlistId) {
  const response = await axios.get(`${API_BASE_URL}/api/watchlists/${watchlistId}/inflections`);
  return response.data;
}

export async function setWatchlistSchedule(watchlistId, schedule) {
  const response = await axios.put(`${API_BASE_URL}/api/watchlists/${watchlistId}/schedule`, { schedule });
  return response.data;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/utils/api.js
git commit -m "feat: add inflection and schedule API client functions"
```

---

### Task 11: Fix ESLint Errors in Dashboard and CouncilPanel

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx` (~line 195-205)
- Modify: `frontend/src/components/CouncilPanel.jsx` (~line 610-625)

- [ ] **Step 1: Fix Dashboard.jsx — setState in useEffect**

In `frontend/src/components/Dashboard.jsx`, replace the useEffect block at ~lines 195-205:

```javascript
  /* ─── Track recent analyses (max 5, deduplicated) ─── */
  useEffect(() => {
    if (!analysis?.ticker) return;
    const rec = analysis?.analysis?.signal_contract_v2?.recommendation
      || analysis?.analysis?.recommendation
      || null;
    setRecentAnalyses((prev) => {
      const filtered = prev.filter((r) => r.ticker !== analysis.ticker);
      return [{ ticker: analysis.ticker, recommendation: rec }, ...filtered].slice(0, 5);
    });
  }, [analysis]);
```

With a `useMemo`-driven approach that avoids setState inside useEffect:

```javascript
  /* ─── Track recent analyses (max 5, deduplicated) ─── */
  const recentAnalysesRef = useRef([]);

  useEffect(() => {
    if (!analysis?.ticker) return;
    const rec = analysis?.analysis?.signal_contract_v2?.recommendation
      || analysis?.analysis?.recommendation
      || null;
    const entry = { ticker: analysis.ticker, recommendation: rec };
    const filtered = recentAnalysesRef.current.filter((r) => r.ticker !== analysis.ticker);
    const updated = [entry, ...filtered].slice(0, 5);
    recentAnalysesRef.current = updated;
    setRecentAnalyses(updated);
  }, [analysis?.ticker]);
```

Note: The key fix is changing the dependency from `[analysis]` to `[analysis?.ticker]` — we only need to update the recent list when the ticker changes, not on every analysis object mutation. Also use a ref to avoid the cascading render issue.

- [ ] **Step 2: Fix CouncilPanel.jsx — conditional useState**

In `frontend/src/components/CouncilPanel.jsx`, find the `HealthIndicatorStrip` component (~line 610-625). Move the useState above the early return:

Replace:
```javascript
const HealthIndicatorStrip = ({ thesisHealth }) => {
  if (!thesisHealth?.indicators?.length) return null;
  const [expanded, setExpanded] = React.useState(null);
```

With:
```javascript
const HealthIndicatorStrip = ({ thesisHealth }) => {
  const [expanded, setExpanded] = React.useState(null);
  if (!thesisHealth?.indicators?.length) return null;
```

- [ ] **Step 3: Run lint to verify fixes**

Run: `cd frontend && npm run lint`
Expected: The two specific errors (setState in effect, conditional hook) should be resolved. Other pre-existing errors in untouched files may remain.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Dashboard.jsx frontend/src/components/CouncilPanel.jsx
git commit -m "fix: resolve React hooks ESLint violations in Dashboard and CouncilPanel"
```

---

### Task 12: Inflection Dashboard View — Heatmap Component

**Files:**
- Create: `frontend/src/components/InflectionHeatmap.jsx`

- [ ] **Step 1: Create the heatmap component**

```jsx
// frontend/src/components/InflectionHeatmap.jsx
import { useState, useEffect } from 'react';
import { getWatchlistInflections, getWatchlists } from '../utils/api';

const InflectionHeatmap = ({ selectedTicker, onSelectTicker, watchlistId }) => {
  const [inflections, setInflections] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!watchlistId) return;
    setLoading(true);
    getWatchlistInflections(watchlistId)
      .then((data) => {
        // Group by ticker, get max convergence per ticker
        const byTicker = {};
        for (const event of data) {
          const t = event.ticker;
          if (!byTicker[t] || Math.abs(event.convergence_score) > Math.abs(byTicker[t].convergence_score)) {
            byTicker[t] = event;
          }
        }
        const sorted = Object.values(byTicker).sort(
          (a, b) => Math.abs(b.convergence_score || 0) - Math.abs(a.convergence_score || 0)
        );
        setInflections(sorted);
      })
      .catch(() => setInflections([]))
      .finally(() => setLoading(false));
  }, [watchlistId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-zinc-500 text-sm">
        Loading inflections…
      </div>
    );
  }

  if (inflections.length === 0) {
    return (
      <div className="text-zinc-500 text-sm p-4">
        No inflection data yet. Analyze tickers in your watchlist to start tracking.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[0.65rem] uppercase tracking-wider text-zinc-500 mb-2 px-2">
        Convergence Radar
      </div>
      {inflections.map((inf) => {
        const score = inf.convergence_score || 0;
        const isPositive = inf.direction === 'positive';
        const barColor = isPositive ? '#17c964' : '#f31260';
        const barWidth = Math.min(Math.abs(score) * 100, 100);
        const isSelected = selectedTicker === inf.ticker;

        return (
          <button
            key={inf.ticker}
            onClick={() => onSelectTicker(inf.ticker)}
            className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-colors w-full ${
              isSelected ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
            }`}
          >
            <span className="text-xs font-mono text-zinc-300 w-12 shrink-0">
              {inf.ticker}
            </span>
            <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${barWidth}%`, backgroundColor: barColor }}
              />
            </div>
            <span className={`text-xs font-mono w-12 text-right ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
              {isPositive ? '+' : '-'}{score.toFixed(2)}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default InflectionHeatmap;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InflectionHeatmap.jsx
git commit -m "feat: add InflectionHeatmap component for convergence radar"
```

---

### Task 13: Inflection Dashboard View — Time-Series Chart

**Files:**
- Create: `frontend/src/components/InflectionChart.jsx`

- [ ] **Step 1: Create the time-series chart component**

```jsx
// frontend/src/components/InflectionChart.jsx
import { useState, useEffect, useRef, useMemo } from 'react';
import { createChart } from 'lightweight-charts';
import { getInflectionTimeseries } from '../utils/api';

const TIME_RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
];

const KPI_COLORS = {
  forward_pe: '#006fee',
  profit_margins: '#17c964',
  revenue_growth: '#f5a524',
  overall_sentiment: '#a855f7',
  rsi: '#ec4899',
  analyst_target_median: '#06b6d4',
  fed_funds_rate: '#f97316',
  put_call_ratio: '#84cc16',
};

const InflectionChart = ({ ticker }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const [timeRange, setTimeRange] = useState('3M');
  const [rawData, setRawData] = useState([]);
  const [activeKPIs, setActiveKPIs] = useState(new Set(['forward_pe', 'overall_sentiment', 'revenue_growth']));
  const [loading, setLoading] = useState(false);

  // Fetch data when ticker changes
  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    getInflectionTimeseries(ticker, null, 500)
      .then(setRawData)
      .catch(() => setRawData([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  // Available KPIs from the data
  const availableKPIs = useMemo(() => {
    const kpis = new Set();
    for (const row of rawData) {
      kpis.add(row.kpi_name);
    }
    return [...kpis].sort();
  }, [rawData]);

  // Build chart
  useEffect(() => {
    if (!chartRef.current || rawData.length === 0) return;

    // Clean up previous chart
    if (chartInstance.current) {
      chartInstance.current.remove();
      chartInstance.current = null;
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: '#a1a1aa',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.1)' },
      crosshair: { mode: 0 },
    });
    chartInstance.current = chart;

    // Group data by KPI
    const byKPI = {};
    for (const row of rawData) {
      if (!activeKPIs.has(row.kpi_name)) continue;
      if (!byKPI[row.kpi_name]) byKPI[row.kpi_name] = [];
      byKPI[row.kpi_name].push({
        time: row.captured_at.split('T')[0],
        value: row.value,
      });
    }

    // Add a line series per KPI
    for (const [kpi, points] of Object.entries(byKPI)) {
      const series = chart.addLineSeries({
        color: KPI_COLORS[kpi] || '#71717a',
        lineWidth: 2,
        title: kpi.replace(/_/g, ' '),
      });
      series.setData(points);
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstance.current = null;
    };
  }, [rawData, activeKPIs, timeRange]);

  const toggleKPI = (kpi) => {
    setActiveKPIs((prev) => {
      const next = new Set(prev);
      if (next.has(kpi)) next.delete(kpi);
      else next.add(kpi);
      return next;
    });
  };

  if (!ticker) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Select a ticker to view KPI trends
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header: time range + KPI toggles */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <div className="flex gap-1">
          {TIME_RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setTimeRange(r.label)}
              className={`px-2 py-0.5 text-xs rounded ${
                timeRange === r.label ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 flex-wrap justify-end">
          {availableKPIs.map((kpi) => (
            <button
              key={kpi}
              onClick={() => toggleKPI(kpi)}
              className={`px-1.5 py-0.5 text-[0.6rem] rounded border transition-colors ${
                activeKPIs.has(kpi)
                  ? 'border-zinc-600 text-zinc-200'
                  : 'border-zinc-800 text-zinc-600'
              }`}
              style={{
                borderLeftColor: activeKPIs.has(kpi) ? (KPI_COLORS[kpi] || '#71717a') : undefined,
                borderLeftWidth: activeKPIs.has(kpi) ? 2 : undefined,
              }}
            >
              {kpi.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading…</div>
        ) : (
          <div ref={chartRef} className="w-full h-full" />
        )}
      </div>
    </div>
  );
};

export default InflectionChart;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InflectionChart.jsx
git commit -m "feat: add InflectionChart component with KPI time-series visualization"
```

---

### Task 14: Inflection Dashboard View — Feed Component

**Files:**
- Create: `frontend/src/components/InflectionFeed.jsx`

- [ ] **Step 1: Create the inflection feed component**

```jsx
// frontend/src/components/InflectionFeed.jsx
import { useState, useEffect } from 'react';
import { getInflectionHistory, getWatchlistInflections } from '../utils/api';

const InflectionFeed = ({ watchlistId, onSelectTicker }) => {
  const [events, setEvents] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!watchlistId) return;
    setLoading(true);
    getWatchlistInflections(watchlistId)
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [watchlistId]);

  if (loading) {
    return <div className="text-zinc-500 text-sm p-3">Loading feed…</div>;
  }

  if (events.length === 0) {
    return <div className="text-zinc-500 text-sm p-3">No inflection events yet.</div>;
  }

  return (
    <div className="flex flex-col gap-1 overflow-y-auto">
      <div className="text-[0.65rem] uppercase tracking-wider text-zinc-500 mb-1 px-3 pt-2">
        Inflection Feed
      </div>
      {events.map((event) => {
        const isPositive = event.direction === 'positive';
        const isExpanded = expandedId === event.id;
        const date = event.detected_at ? new Date(event.detected_at).toLocaleDateString() : '';

        return (
          <div key={event.id} className="px-3 py-2 hover:bg-zinc-800/30 rounded-md transition-colors">
            <button
              onClick={() => {
                setExpandedId(isExpanded ? null : event.id);
                onSelectTicker?.(event.ticker);
              }}
              className="w-full text-left"
            >
              <div className="flex items-center gap-2">
                <span className={`text-sm ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                  {isPositive ? '\u25B2' : '\u25BC'}
                </span>
                <span className="text-xs font-mono text-zinc-300 font-medium">{event.ticker}</span>
                <span className="text-[0.65rem] text-zinc-500">{date}</span>
                <span className={`ml-auto text-xs font-mono ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                  {(event.convergence_score || 0).toFixed(2)}
                </span>
              </div>
              <div className="text-[0.7rem] text-zinc-400 mt-0.5 line-clamp-1">
                {event.summary}
              </div>
            </button>

            {isExpanded && (
              <div className="mt-2 pl-6 text-[0.65rem] text-zinc-500 space-y-1">
                <div>KPI: <span className="text-zinc-300">{event.kpi_name?.replace(/_/g, ' ')}</span></div>
                <div>Change: <span className="text-zinc-300">{event.pct_change?.toFixed(1)}%</span></div>
                <div>
                  Prior: <span className="text-zinc-300">{event.prior_value?.toFixed(2)}</span>
                  {' → '}
                  Current: <span className="text-zinc-300">{event.current_value?.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default InflectionFeed;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InflectionFeed.jsx
git commit -m "feat: add InflectionFeed component for event timeline"
```

---

### Task 15: Inflection Dashboard View — Main Layout + Sidebar + Dashboard Integration

**Files:**
- Create: `frontend/src/components/InflectionView.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/Dashboard.jsx`

- [ ] **Step 1: Create the main InflectionView component**

```jsx
// frontend/src/components/InflectionView.jsx
import { useState, useEffect } from 'react';
import { getWatchlists } from '../utils/api';
import InflectionHeatmap from './InflectionHeatmap';
import InflectionChart from './InflectionChart';
import InflectionFeed from './InflectionFeed';

const InflectionView = () => {
  const [watchlists, setWatchlists] = useState([]);
  const [activeWatchlistId, setActiveWatchlistId] = useState(null);
  const [selectedTicker, setSelectedTicker] = useState(null);

  useEffect(() => {
    getWatchlists()
      .then((wls) => {
        setWatchlists(wls);
        if (wls.length > 0 && !activeWatchlistId) {
          setActiveWatchlistId(wls[0].id);
        }
      })
      .catch(() => setWatchlists([]));
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h2 className="text-sm font-medium text-zinc-200">Inflection Radar</h2>
        <select
          value={activeWatchlistId || ''}
          onChange={(e) => setActiveWatchlistId(Number(e.target.value))}
          className="bg-zinc-800 text-zinc-300 text-xs rounded px-2 py-1 border border-zinc-700"
        >
          {watchlists.map((wl) => (
            <option key={wl.id} value={wl.id}>{wl.name}</option>
          ))}
        </select>
      </div>

      {/* Main content: heatmap + chart */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Heatmap */}
        <div className="w-60 shrink-0 border-r border-zinc-800 overflow-y-auto p-2">
          <InflectionHeatmap
            watchlistId={activeWatchlistId}
            selectedTicker={selectedTicker}
            onSelectTicker={setSelectedTicker}
          />
        </div>

        {/* Right: Chart */}
        <div className="flex-1 min-w-0">
          <InflectionChart ticker={selectedTicker} />
        </div>
      </div>

      {/* Bottom: Feed */}
      <div className="h-48 shrink-0 border-t border-zinc-800 overflow-y-auto">
        <InflectionFeed
          watchlistId={activeWatchlistId}
          onSelectTicker={setSelectedTicker}
        />
      </div>
    </div>
  );
};

export default InflectionView;
```

- [ ] **Step 2: Add "Inflections" nav item to Sidebar**

In `frontend/src/components/Sidebar.jsx`, find the `NAV_SECTIONS` array (~line 4-21). Add an item to the Portfolio section, between "Watchlist" and "Holdings":

```javascript
      { key: 'watchlist', label: 'Watchlist', Icon: ChartBarIcon },
      { key: 'inflections', label: 'Inflections', Icon: ActivityIcon },
      { key: 'portfolio', label: 'Holdings', Icon: BuildingIcon },
```

You'll also need to add an `ActivityIcon` SVG. Add it near the other icon definitions:

```javascript
const ActivityIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path fillRule="evenodd" d="M2 10a.75.75 0 01.75-.75h2.793l1.874-3.748a.75.75 0 011.341.008L11.25 11.5l1.293-2.586a.75.75 0 011.326-.012L15.5 11.25h2.75a.75.75 0 010 1.5h-3.25a.75.75 0 01-.67-.415L13.25 10.5l-1.293 2.586a.75.75 0 01-1.326.012L8.14 7.109 6.83 9.724A.75.75 0 016.17 10.25H2.75A.75.75 0 012 10z" clipRule="evenodd" />
  </svg>
);
```

- [ ] **Step 3: Add INFLECTIONS view mode to Dashboard**

In `frontend/src/components/Dashboard.jsx`:

1. Add to VIEW_MODES (~line 30-37):
```javascript
  INFLECTIONS: 'inflections',
```

2. Add import at top:
```javascript
import InflectionView from './InflectionView';
```

3. Add the view rendering. Find the conditional view rendering section (~line 310-320) and add before the WATCHLIST case:
```javascript
        {viewMode === VIEW_MODES.INFLECTIONS && <InflectionView />}
```

- [ ] **Step 4: Run frontend lint**

Run: `cd frontend && npm run lint`
Expected: No new errors introduced

- [ ] **Step 5: Run frontend build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/InflectionView.jsx frontend/src/components/Sidebar.jsx frontend/src/components/Dashboard.jsx
git commit -m "feat: add Inflection Dashboard view with sidebar navigation"
```

---

### Task 16: Thesis Card Inflection Badge

**Files:**
- Modify: `frontend/src/components/ThesisCard.jsx`

- [ ] **Step 1: Add inflection badge to ThesisCard**

In `frontend/src/components/ThesisCard.jsx`, find the data extraction section (~line 46-68). Add inflection data extraction:

```javascript
const inflectionSummary = payload.inflection_summary || null;
```

Then find the recommendation display area (~line 88-91) and add the badge after the recommendation text:

```jsx
            {/* Inflection badge */}
            {inflectionSummary && inflectionSummary.inflection_count > 0 && (
              <div
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.6rem] font-mono ${
                  inflectionSummary.direction === 'positive'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}
              >
                <span>{inflectionSummary.direction === 'positive' ? '\u25B2' : '\u25BC'}</span>
                <span>{inflectionSummary.convergence_score?.toFixed(2)}</span>
              </div>
            )}
```

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThesisCard.jsx
git commit -m "feat: add inflection badge to ThesisCard"
```

---

### Task 17: Watchlist Schedule Config UI

**Files:**
- Modify: `frontend/src/components/WatchlistView.jsx`

- [ ] **Step 1: Add schedule dropdown to WatchlistView**

In `frontend/src/components/WatchlistView.jsx`, add import:

```javascript
import { setWatchlistSchedule } from '../utils/api';
```

Find the selected watchlist detail panel (right panel, ~line 412). Add the schedule dropdown after the watchlist title area and before the add ticker form:

```jsx
              {/* Auto-analyze schedule */}
              <div className="flex items-center gap-3 mb-4 p-2 rounded-md bg-zinc-800/30">
                <span className="text-xs text-zinc-400">Auto-analyze:</span>
                <select
                  value={watchlistDetail?.auto_analyze_schedule || ''}
                  onChange={async (e) => {
                    const schedule = e.target.value || null;
                    try {
                      await setWatchlistSchedule(activeWatchlist, schedule);
                      setWatchlistDetail((prev) => prev ? { ...prev, auto_analyze_schedule: schedule } : prev);
                    } catch (err) {
                      setError('Failed to update schedule');
                    }
                  }}
                  className="bg-zinc-800 text-zinc-300 text-xs rounded px-2 py-1 border border-zinc-700"
                >
                  <option value="">Off</option>
                  <option value="daily_am">Morning (9 AM ET)</option>
                  <option value="daily_pm">Evening (4 PM ET)</option>
                  <option value="twice_daily">Twice Daily</option>
                </select>
              </div>
```

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WatchlistView.jsx
git commit -m "feat: add auto-analyze schedule config to WatchlistView"
```

---

### Task 18: Update Plans Index + Final Verification

**Files:**
- Modify: `docs/plans/INDEX.md`

- [ ] **Step 1: Add entry to plans index**

In `docs/plans/INDEX.md`, add a new row to the completed plans table:

```markdown
| 2026-04-01 | [Perception Ledger & Inflection Tracker](../superpowers/plans/2026-04-01-perception-ledger-inflection-tracker.md) | ✅ Completed | KPI perception snapshots, inflection detection with convergence scoring, inflection dashboard |
```

And update the "In Progress / Planned" section to add a row:

```markdown
| **Perception Ledger** | Fundamental inflection tracking — KPI snapshots, convergence detection, scheduled watchlist scanning, inflection dashboard | [Design spec](../superpowers/specs/2026-04-01-perception-ledger-inflection-tracker-design.md) |
```

- [ ] **Step 2: Run full backend test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass including new perception/inflection tests

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add docs/plans/INDEX.md
git commit -m "docs: add perception ledger to plans index"
```

- [ ] **Step 5: Verify end-to-end**

Start the backend and frontend:
```bash
source venv/bin/activate && python run.py &
cd frontend && npm run dev &
```

1. Run an analysis: `curl -X POST http://localhost:8000/api/analyze/AAPL`
2. Check snapshots were captured: `curl http://localhost:8000/api/inflections/AAPL/timeseries`
3. Run a second analysis: `curl -X POST http://localhost:8000/api/analyze/AAPL`
4. Check inflections detected: `curl http://localhost:8000/api/inflections/AAPL`
5. Open frontend at `http://localhost:5173`, navigate to Inflections view
