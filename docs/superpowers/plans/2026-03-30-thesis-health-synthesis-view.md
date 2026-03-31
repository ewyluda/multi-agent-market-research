# Thesis Health Monitor + Synthesis View — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add thesis health monitoring (Phase 2.6 in orchestrator) and council synthesis view (deterministic consensus + LLM narrative) with alerts and frontend rendering.

**Architecture:** Two pure-function modules (`thesis_health.py`, `council_synthesis.py`) plus one LLM agent (`council_synthesis_agent.py`). Health checks run in the standard analysis pipeline for tickers with thesis cards. Synthesis runs at the end of every council convene. Both degrade gracefully.

**Tech Stack:** Python 3 / FastAPI / SQLite / React + Tailwind CSS v4 / framer-motion

**Design spec:** `docs/superpowers/specs/2026-03-30-thesis-health-synthesis-view-design.md`

---

### Task 1: Config + DB schema

**Files:**
- Modify: `src/config.py`
- Modify: `src/database.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Add feature flag to `src/config.py`**

In `src/config.py`, after the `VALIDATION_SPOT_CHECK_ON_CONTRADICTION` line, add:

```python
    # Thesis Health Monitor
    THESIS_HEALTH_ENABLED = os.getenv("THESIS_HEALTH_ENABLED", "true").lower() == "true"
```

- [ ] **Step 2: Add config to `tests/conftest.py`**

In `tests/conftest.py`, inside the `test_config` fixture dict, add:

```python
    "THESIS_HEALTH_ENABLED": True,
```

- [ ] **Step 3: Add `thesis_health_snapshots` table to `src/database.py`**

In `src/database.py`, in the `_initialize_tables` method, after the `validation_feedback` table creation, add:

```python
            # Thesis health snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS thesis_health_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    overall_health TEXT NOT NULL CHECK(overall_health IN ('INTACT', 'WATCHING', 'DETERIORATING', 'BROKEN')),
                    previous_health TEXT,
                    health_changed INTEGER DEFAULT 0,
                    indicators_json TEXT NOT NULL,
                    baselines_updated INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_thesis_health_ticker ON thesis_health_snapshots(ticker, created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_thesis_health_analysis ON thesis_health_snapshots(analysis_id)")
```

- [ ] **Step 4: Add `council_synthesis` table to `src/database.py`**

In `src/database.py`, immediately after the `thesis_health_snapshots` table creation, add:

```python
            # Council synthesis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS council_synthesis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    analysis_id INTEGER,
                    consensus_json TEXT NOT NULL,
                    narrative_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_council_synthesis_ticker ON council_synthesis(ticker, created_at DESC)")
```

- [ ] **Step 5: Add `thesis_health_change` to alert_rules CHECK constraint**

In `src/database.py`, find both `CHECK(rule_type IN (` blocks for `alert_rules` (the initial create and the migration create). Add `'thesis_health_change'` after `'spot_check'` in both:

```sql
                        'spot_check',
                        'thesis_health_change'
```

- [ ] **Step 6: Add CRUD methods for thesis health and council synthesis**

At the end of the `DatabaseManager` class in `src/database.py`, after `get_validation_feedback`, add:

```python
    # ── Thesis Health Snapshots ──────────────────────────────────────────────

    def save_thesis_health_snapshot(
        self,
        analysis_id: int,
        ticker: str,
        overall_health: str,
        previous_health: Optional[str],
        health_changed: bool,
        indicators_json: list,
        baselines_updated: int,
    ) -> int:
        """Save a thesis health snapshot. Returns row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO thesis_health_snapshots (
                       analysis_id, ticker, overall_health, previous_health,
                       health_changed, indicators_json, baselines_updated, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id, ticker.upper(), overall_health, previous_health,
                    1 if health_changed else 0,
                    json.dumps(indicators_json) if isinstance(indicators_json, (list, dict)) else indicators_json,
                    baselines_updated, now,
                ),
            )
            return cursor.lastrowid

    def get_latest_thesis_health(self, ticker: str) -> Optional[dict]:
        """Get the most recent thesis health snapshot for a ticker."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM thesis_health_snapshots WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                (ticker.upper(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            if isinstance(result.get("indicators_json"), str):
                try:
                    result["indicators_json"] = json.loads(result["indicators_json"])
                except Exception:
                    pass
            return result

    # ── Council Synthesis ────────────────────────────────────────────────────

    def save_council_synthesis(
        self,
        ticker: str,
        analysis_id: Optional[int],
        synthesis: dict,
    ) -> int:
        """Save council synthesis (consensus + narrative). Returns row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO council_synthesis (
                       ticker, analysis_id, consensus_json, narrative_json, created_at
                   ) VALUES (?, ?, ?, ?, ?)""",
                (
                    ticker.upper(),
                    analysis_id,
                    json.dumps(synthesis.get("consensus", {})),
                    json.dumps(synthesis.get("narrative", {})),
                    now,
                ),
            )
            return cursor.lastrowid

    def get_latest_council_synthesis(self, ticker: str) -> Optional[dict]:
        """Get the most recent council synthesis for a ticker."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM council_synthesis WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                (ticker.upper(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            for field in ("consensus_json", "narrative_json"):
                if isinstance(result.get(field), str):
                    try:
                        result[field] = json.loads(result[field])
                    except Exception:
                        pass
            return result
```

- [ ] **Step 7: Write DB tests**

Add a `TestThesisHealthAndSynthesisTables` class at the end of `tests/test_database.py`:

```python
class TestThesisHealthAndSynthesisTables:
    """Tests for thesis_health_snapshots and council_synthesis tables."""

    def test_save_and_get_thesis_health_snapshot(self, db_manager):
        indicators = [{"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": "62", "drift_pct": 12.7, "status": "drifting"}]
        row_id = db_manager.save_thesis_health_snapshot(
            analysis_id=1, ticker="NVDA", overall_health="WATCHING",
            previous_health="INTACT", health_changed=True,
            indicators_json=indicators, baselines_updated=0,
        )
        assert row_id is not None
        latest = db_manager.get_latest_thesis_health("NVDA")
        assert latest is not None
        assert latest["overall_health"] == "WATCHING"
        assert latest["previous_health"] == "INTACT"
        assert latest["health_changed"] == 1
        assert isinstance(latest["indicators_json"], list)
        assert latest["indicators_json"][0]["name"] == "RSI"

    def test_get_latest_thesis_health_nonexistent(self, db_manager):
        assert db_manager.get_latest_thesis_health("ZZZZ") is None

    def test_save_and_get_council_synthesis(self, db_manager):
        synthesis = {
            "consensus": {"majority_stance": "BULLISH", "conviction_strength": 0.8},
            "narrative": {"narrative": "Council agrees...", "fallback_used": False},
        }
        row_id = db_manager.save_council_synthesis("AAPL", 1, synthesis)
        assert row_id is not None
        latest = db_manager.get_latest_council_synthesis("AAPL")
        assert latest is not None
        assert latest["consensus_json"]["majority_stance"] == "BULLISH"
        assert latest["narrative_json"]["narrative"] == "Council agrees..."

    def test_get_latest_council_synthesis_nonexistent(self, db_manager):
        assert db_manager.get_latest_council_synthesis("ZZZZ") is None
```

- [ ] **Step 8: Run DB tests**

Run: `python -m pytest tests/test_database.py -v`
Expected: All tests pass including the 4 new ones.

- [ ] **Step 9: Commit**

```bash
git add src/config.py src/database.py tests/conftest.py tests/test_database.py
git commit -m "feat(db): add thesis_health_snapshots + council_synthesis tables and CRUD"
```

---

### Task 2: Thesis health module — `src/thesis_health.py`

**Files:**
- Create: `src/thesis_health.py`
- Create: `tests/test_thesis_health.py`

- [ ] **Step 1: Create `tests/test_thesis_health.py`**

```python
"""Tests for thesis health indicator drift detection and aggregate rollup."""

import pytest
from src.thesis_health import evaluate_thesis_health, resolve_indicator_value


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_agent_results():
    return {
        "market": {"success": True, "data": {"current_price": 152.0, "trend": "uptrend"}},
        "technical": {"success": True, "data": {"rsi": 55, "signals": {"overall": "buy", "strength": 30}}},
        "fundamentals": {"success": True, "data": {"health_score": 72, "revenue_growth": 0.28}},
        "options": {"success": True, "data": {"put_call_ratio": 0.8}},
        "sentiment": {"success": True, "data": {"overall_sentiment": 0.4}},
        "macro": {"success": True, "data": {"risk_environment": "risk_on", "yield_curve_slope": 0.5}},
    }


@pytest.fixture
def sample_thesis_card():
    return {
        "ticker": "NVDA",
        "structural_thesis": "AI compute leader",
        "load_bearing_assumption": "revenue growth above 20%",
        "health_indicators": [
            {"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": None},
            {"name": "Revenue Growth", "proxy_signal": "revenue_growth", "baseline_value": "0.28", "current_value": None},
            {"name": "Put/Call Ratio", "proxy_signal": "put_call_ratio", "baseline_value": "0.8", "current_value": None},
        ],
    }


# ── resolve_indicator_value ───────────────────────────────────────────────────

class TestResolveIndicatorValue:
    def test_resolves_market_price(self, sample_agent_results):
        assert resolve_indicator_value("current_price", sample_agent_results) == "152.0"

    def test_resolves_rsi(self, sample_agent_results):
        assert resolve_indicator_value("rsi", sample_agent_results) == "55"

    def test_resolves_fundamentals_key(self, sample_agent_results):
        assert resolve_indicator_value("revenue_growth", sample_agent_results) == "0.28"

    def test_resolves_put_call_ratio(self, sample_agent_results):
        assert resolve_indicator_value("put_call_ratio", sample_agent_results) == "0.8"

    def test_resolves_sentiment(self, sample_agent_results):
        assert resolve_indicator_value("overall_sentiment", sample_agent_results) == "0.4"

    def test_resolves_macro_string(self, sample_agent_results):
        assert resolve_indicator_value("risk_environment", sample_agent_results) == "risk_on"

    def test_unknown_signal_returns_none(self, sample_agent_results):
        assert resolve_indicator_value("nonexistent_signal", sample_agent_results) is None


# ── Drift detection ──────────────────────────────────────────────────────────

class TestDriftDetection:
    def test_all_stable_returns_intact(self, sample_thesis_card, sample_agent_results):
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health=None,
        )
        assert report["overall_health"] == "INTACT"
        assert all(ind["status"] == "stable" for ind in report["indicators"])

    def test_drifting_indicator_returns_watching(self, sample_thesis_card, sample_agent_results):
        # RSI baseline 55, current will be 68 → ~23.6% drift → drifting
        sample_agent_results["technical"]["data"]["rsi"] = 68
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="INTACT",
        )
        assert report["overall_health"] == "WATCHING"
        rsi_ind = next(i for i in report["indicators"] if i["proxy_signal"] == "rsi")
        assert rsi_ind["status"] == "drifting"

    def test_breached_indicator_returns_deteriorating(self, sample_thesis_card, sample_agent_results):
        # RSI baseline 55, current 80 → ~45% drift → breached
        sample_agent_results["technical"]["data"]["rsi"] = 80
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="INTACT",
        )
        assert report["overall_health"] == "DETERIORATING"

    def test_two_breached_returns_broken(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 80
        sample_agent_results["options"]["data"]["put_call_ratio"] = 2.5
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="WATCHING",
        )
        assert report["overall_health"] == "BROKEN"

    def test_load_bearing_breach_returns_broken(self, sample_thesis_card, sample_agent_results):
        # load_bearing_assumption mentions "revenue growth" — if revenue_growth breaches, it's BROKEN
        sample_agent_results["fundamentals"]["data"]["revenue_growth"] = 0.10  # 64% drift from 0.28
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="INTACT",
        )
        assert report["overall_health"] == "BROKEN"


# ── Health change detection ──────────────────────────────────────────────────

class TestHealthChange:
    def test_health_changed_when_different(self, sample_thesis_card, sample_agent_results):
        sample_agent_results["technical"]["data"]["rsi"] = 68
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="INTACT",
        )
        assert report["health_changed"] is True
        assert report["previous_health"] == "INTACT"

    def test_health_unchanged_when_same(self, sample_thesis_card, sample_agent_results):
        report = evaluate_thesis_health(
            thesis_card=sample_thesis_card,
            agent_results=sample_agent_results,
            previous_health="INTACT",
        )
        assert report["health_changed"] is False


# ── Baseline auto-snapshot ───────────────────────────────────────────────────

class TestBaselineSnapshot:
    def test_counts_baselines_needing_snapshot(self, sample_agent_results):
        card = {
            "ticker": "AAPL",
            "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "RSI", "proxy_signal": "rsi", "baseline_value": None, "current_value": None},
                {"name": "Price", "proxy_signal": "current_price", "baseline_value": None, "current_value": None},
            ],
        }
        report = evaluate_thesis_health(
            thesis_card=card,
            agent_results=sample_agent_results,
            previous_health=None,
        )
        assert report["baselines_updated"] == 2
        # When baseline is missing, current == resolved value and drift is 0 → stable
        assert report["overall_health"] == "INTACT"


# ── String indicators ────────────────────────────────────────────────────────

class TestStringIndicators:
    def test_string_unchanged_is_stable(self, sample_agent_results):
        card = {
            "ticker": "TEST",
            "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "Risk Env", "proxy_signal": "risk_environment", "baseline_value": "risk_on", "current_value": None},
            ],
        }
        report = evaluate_thesis_health(
            thesis_card=card,
            agent_results=sample_agent_results,
            previous_health=None,
        )
        assert report["indicators"][0]["status"] == "stable"

    def test_string_changed_is_breached(self, sample_agent_results):
        sample_agent_results["macro"]["data"]["risk_environment"] = "risk_off"
        card = {
            "ticker": "TEST",
            "load_bearing_assumption": "",
            "health_indicators": [
                {"name": "Risk Env", "proxy_signal": "risk_environment", "baseline_value": "risk_on", "current_value": None},
            ],
        }
        report = evaluate_thesis_health(
            thesis_card=card,
            agent_results=sample_agent_results,
            previous_health=None,
        )
        assert report["indicators"][0]["status"] == "breached"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_thesis_health.py -v`
Expected: ImportError — `src.thesis_health` does not exist yet.

- [ ] **Step 3: Create `src/thesis_health.py`**

```python
"""Thesis health indicator drift detection and aggregate rollup.

Pure functions. No classes, no state, no LLM calls.
Maps thesis card health_indicators to agent result data, computes drift
from baselines, and rolls up to INTACT/WATCHING/DETERIORATING/BROKEN.
"""

from typing import Any, Dict, List, Optional


# ── Proxy signal → agent data path mapping ────────────────────────────────────

_SIGNAL_MAP = {
    # Market
    "price": ("market", "current_price"),
    "current_price": ("market", "current_price"),
    # Technical
    "rsi": ("technical", "rsi"),
    "macd": ("technical", "signals", "strength"),
    "signal_strength": ("technical", "signals", "strength"),
    # Fundamentals
    "revenue_growth": ("fundamentals", "revenue_growth"),
    "margins": ("fundamentals", "margins"),
    "health_score": ("fundamentals", "health_score"),
    # Options
    "put_call_ratio": ("options", "put_call_ratio"),
    # Sentiment
    "overall_sentiment": ("sentiment", "overall_sentiment"),
    # Macro
    "risk_environment": ("macro", "risk_environment"),
    "yield_curve": ("macro", "yield_curve_slope"),
    "yield_curve_slope": ("macro", "yield_curve_slope"),
}


def resolve_indicator_value(proxy_signal: str, agent_results: Dict[str, Any]) -> Optional[str]:
    """Resolve a proxy_signal to its current value from agent_results. Returns string or None."""
    path = _SIGNAL_MAP.get(proxy_signal)
    if not path:
        return None

    agent_key = path[0]
    agent_data = (agent_results.get(agent_key) or {}).get("data") or {}

    value = agent_data
    for key in path[1:]:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None

    return str(value) if value is not None else None


def _is_numeric(s: str) -> bool:
    """Check if a string represents a numeric value."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _compute_drift(baseline: str, current: str) -> Dict[str, Any]:
    """Compute drift between baseline and current values.

    Returns dict with drift_pct (float or None) and status (stable/drifting/breached).
    """
    if _is_numeric(baseline) and _is_numeric(current):
        b = float(baseline)
        c = float(current)
        if abs(b) < 1e-9:
            drift_pct = 0.0 if abs(c) < 1e-9 else 100.0
        else:
            drift_pct = abs(c - b) / abs(b) * 100.0

        if drift_pct <= 10.0:
            status = "stable"
        elif drift_pct <= 25.0:
            status = "drifting"
        else:
            status = "breached"

        return {"drift_pct": round(drift_pct, 2), "status": status}
    else:
        # String comparison
        changed = str(baseline).strip().lower() != str(current).strip().lower()
        return {"drift_pct": None, "status": "breached" if changed else "stable"}


_HEALTH_ORDER = {"INTACT": 0, "WATCHING": 1, "DETERIORATING": 2, "BROKEN": 3}


def evaluate_thesis_health(
    *,
    thesis_card: Dict[str, Any],
    agent_results: Dict[str, Any],
    previous_health: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate thesis health for a ticker. Returns ThesisHealthReport."""
    indicators = thesis_card.get("health_indicators") or []
    load_bearing = str(thesis_card.get("load_bearing_assumption") or "").lower()
    ticker = thesis_card.get("ticker", "")

    evaluated = []
    baselines_updated = 0

    for ind in indicators:
        proxy = ind.get("proxy_signal", "")
        name = ind.get("name", proxy)
        baseline = ind.get("baseline_value")
        current_str = resolve_indicator_value(proxy, agent_results)

        if current_str is None:
            continue

        if baseline is None or str(baseline).strip() == "":
            # Auto-snapshot: use current value as baseline → zero drift
            baseline = current_str
            baselines_updated += 1

        drift_info = _compute_drift(baseline, current_str)

        evaluated.append({
            "name": name,
            "proxy_signal": proxy,
            "baseline_value": str(baseline),
            "current_value": current_str,
            "drift_pct": drift_info["drift_pct"],
            "status": drift_info["status"],
        })

    # Aggregate health
    statuses = [e["status"] for e in evaluated]
    breached_count = statuses.count("breached")
    drifting_count = statuses.count("drifting")

    # Check if any breached indicator is load-bearing
    load_bearing_breached = False
    if load_bearing:
        for e in evaluated:
            if e["status"] == "breached" and load_bearing in e["name"].lower():
                load_bearing_breached = True
                break

    if breached_count >= 2 or load_bearing_breached:
        overall = "BROKEN"
    elif breached_count == 1:
        overall = "DETERIORATING"
    elif drifting_count > 0:
        overall = "WATCHING"
    else:
        overall = "INTACT"

    health_changed = previous_health is not None and overall != previous_health

    return {
        "ticker": ticker,
        "overall_health": overall,
        "previous_health": previous_health,
        "health_changed": health_changed,
        "indicators": evaluated,
        "baselines_updated": baselines_updated,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_thesis_health.py -v`
Expected: All 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/thesis_health.py tests/test_thesis_health.py
git commit -m "feat: add thesis health indicator drift detection module"
```

---

### Task 3: Council synthesis module — `src/council_synthesis.py`

**Files:**
- Create: `src/council_synthesis.py`
- Create: `tests/test_council_synthesis.py`

- [ ] **Step 1: Create `tests/test_council_synthesis.py`**

```python
"""Tests for deterministic council consensus aggregation."""

import pytest
from src.council_synthesis import build_consensus


@pytest.fixture
def sample_council_results():
    return [
        {"investor": "druckenmiller", "investor_name": "Stanley Druckenmiller", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts rates", "action": "then add exposure", "conviction": "high"}]},
        {"investor": "ptj", "investor_name": "Paul Tudor Jones", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "price", "condition": "If price breaks 160", "action": "then trail stop", "conviction": "medium"}]},
        {"investor": "munger", "investor_name": "Charlie Munger", "stance": "CAUTIOUS", "thesis_health": "WATCHING", "disagreement_flag": "Disagrees with bullish macro thesis", "if_then_scenarios": [{"type": "event", "condition": "If margins compress", "action": "then reduce position", "conviction": "high"}]},
        {"investor": "dalio", "investor_name": "Ray Dalio", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If yield curve inverts further", "action": "then hedge", "conviction": "low"}]},
        {"investor": "marks", "investor_name": "Howard Marks", "stance": "BEARISH", "thesis_health": "DETERIORATING", "disagreement_flag": "Sees cycle top signals", "if_then_scenarios": []},
    ]


class TestStanceDistribution:
    def test_counts_stances(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["stance_distribution"]["bullish"] == 3
        assert consensus["stance_distribution"]["cautious"] == 1
        assert consensus["stance_distribution"]["bearish"] == 1
        assert consensus["stance_distribution"]["pass"] == 0

    def test_majority_stance(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert consensus["majority_stance"] == "BULLISH"

    def test_conviction_strength(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        # 3 bullish out of 5 non-PASS = 0.6
        assert consensus["conviction_strength"] == pytest.approx(0.6)


class TestTieBreaking:
    def test_tie_favors_bullish_over_cautious(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "CAUTIOUS", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["majority_stance"] == "BULLISH"

    def test_pass_excluded_from_conviction(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "PASS", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["conviction_strength"] == pytest.approx(1.0)


class TestDisagreements:
    def test_extracts_disagreement_flags(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        assert len(consensus["disagreements"]) == 2
        investors = [d["investor"] for d in consensus["disagreements"]]
        assert "munger" in investors
        assert "marks" in investors


class TestTopScenarios:
    def test_top_scenarios_sorted_by_conviction(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        scenarios = consensus["top_scenarios"]
        assert len(scenarios) <= 3
        # First two should be "high" conviction
        high_scenarios = [s for s in scenarios if s["conviction"] == "high"]
        assert len(high_scenarios) >= 1

    def test_deduplicates_identical_conditions(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None,
             "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts rates", "action": "then add", "conviction": "high"}]},
            {"investor": "b", "investor_name": "B", "stance": "BULLISH", "thesis_health": "INTACT", "disagreement_flag": None,
             "if_then_scenarios": [{"type": "macro", "condition": "if fed cuts rates", "action": "then buy", "conviction": "high"}]},
        ]
        consensus = build_consensus(results)
        # Same condition (case-insensitive) → only 1 scenario
        assert len(consensus["top_scenarios"]) == 1


class TestThesisHealthConsensus:
    def test_mode_of_health_values(self, sample_council_results):
        consensus = build_consensus(sample_council_results)
        # 3 INTACT, 1 WATCHING, 1 DETERIORATING → mode is INTACT
        assert consensus["thesis_health_consensus"] == "INTACT"

    def test_unknown_excluded_from_mode(self):
        results = [
            {"investor": "a", "investor_name": "A", "stance": "BULLISH", "thesis_health": "WATCHING", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "b", "investor_name": "B", "stance": "BULLISH", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
            {"investor": "c", "investor_name": "C", "stance": "BULLISH", "thesis_health": "UNKNOWN", "disagreement_flag": None, "if_then_scenarios": []},
        ]
        consensus = build_consensus(results)
        assert consensus["thesis_health_consensus"] == "WATCHING"


class TestEmptyResults:
    def test_empty_council_returns_defaults(self):
        consensus = build_consensus([])
        assert consensus["majority_stance"] == "PASS"
        assert consensus["conviction_strength"] == 0.0
        assert consensus["disagreements"] == []
        assert consensus["top_scenarios"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_council_synthesis.py -v`
Expected: ImportError — `src.council_synthesis` does not exist yet.

- [ ] **Step 3: Create `src/council_synthesis.py`**

```python
"""Deterministic council consensus aggregation.

Pure functions. No classes, no state, no LLM calls.
Aggregates council investor results into stance distribution,
disagreements, top scenarios, and thesis health consensus.
"""

from collections import Counter
from typing import Any, Dict, List


# Tie-breaking priority: bullish > cautious > bearish > pass
_STANCE_PRIORITY = {"BULLISH": 0, "CAUTIOUS": 1, "BEARISH": 2, "PASS": 3}
_CONVICTION_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_consensus(council_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build deterministic consensus from council investor results."""
    if not council_results:
        return {
            "stance_distribution": {"bullish": 0, "cautious": 0, "bearish": 0, "pass": 0},
            "majority_stance": "PASS",
            "conviction_strength": 0.0,
            "thesis_health_consensus": "UNKNOWN",
            "disagreements": [],
            "top_scenarios": [],
        }

    # Stance distribution
    stances = [r.get("stance", "PASS").upper() for r in council_results]
    dist = {"bullish": 0, "cautious": 0, "bearish": 0, "pass": 0}
    for s in stances:
        key = s.lower() if s.lower() in dist else "pass"
        dist[key] += 1

    # Majority stance with tie-breaking
    non_pass = [(s, c) for s, c in dist.items() if s != "pass" and c > 0]
    if non_pass:
        non_pass.sort(key=lambda x: (-x[1], _STANCE_PRIORITY.get(x[0].upper(), 99)))
        majority = non_pass[0][0].upper()
        total_non_pass = sum(c for _, c in non_pass)
        majority_count = non_pass[0][1]
        conviction = round(majority_count / total_non_pass, 4) if total_non_pass > 0 else 0.0
    else:
        majority = "PASS"
        conviction = 0.0

    # Thesis health consensus (mode, excluding UNKNOWN)
    health_values = [
        r.get("thesis_health", "UNKNOWN").upper()
        for r in council_results
        if r.get("thesis_health", "UNKNOWN").upper() != "UNKNOWN"
    ]
    if health_values:
        health_counter = Counter(health_values)
        health_consensus = health_counter.most_common(1)[0][0]
    else:
        health_consensus = "UNKNOWN"

    # Disagreements
    disagreements = []
    for r in council_results:
        flag = r.get("disagreement_flag")
        if flag and str(flag).strip():
            disagreements.append({
                "investor": r.get("investor", "unknown"),
                "investor_name": r.get("investor_name", r.get("investor", "unknown")),
                "flag": str(flag).strip(),
            })

    # Top scenarios: collect all, sort by conviction, deduplicate, take top 3
    all_scenarios = []
    for r in council_results:
        investor = r.get("investor", "unknown")
        for s in r.get("if_then_scenarios", []):
            scenario = dict(s) if isinstance(s, dict) else {}
            if not scenario.get("condition"):
                continue
            scenario["investor"] = investor
            all_scenarios.append(scenario)

    # Sort by conviction priority
    all_scenarios.sort(key=lambda s: _CONVICTION_ORDER.get(str(s.get("conviction", "low")).lower(), 99))

    # Deduplicate by condition (case-insensitive)
    seen_conditions = set()
    top_scenarios = []
    for s in all_scenarios:
        condition_key = str(s.get("condition", "")).strip().lower()
        if condition_key in seen_conditions:
            continue
        seen_conditions.add(condition_key)
        top_scenarios.append({
            "investor": s.get("investor", ""),
            "type": s.get("type", ""),
            "condition": s.get("condition", ""),
            "action": s.get("action", ""),
            "conviction": s.get("conviction", "low"),
        })
        if len(top_scenarios) >= 3:
            break

    return {
        "stance_distribution": dist,
        "majority_stance": majority,
        "conviction_strength": conviction,
        "thesis_health_consensus": health_consensus,
        "disagreements": disagreements,
        "top_scenarios": top_scenarios,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_council_synthesis.py -v`
Expected: All 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/council_synthesis.py tests/test_council_synthesis.py
git commit -m "feat: add deterministic council consensus aggregation module"
```

---

### Task 4: Council synthesis agent — `src/agents/council_synthesis_agent.py`

**Files:**
- Create: `src/agents/council_synthesis_agent.py`
- Create: `tests/test_council_synthesis_agent.py`

- [ ] **Step 1: Create `tests/test_council_synthesis_agent.py`**

```python
"""Tests for LLM-powered council synthesis narrative agent."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.council_synthesis_agent import CouncilSynthesisAgent


@pytest.fixture
def agent_config():
    return {
        "LLM_PROVIDER": "anthropic",
        "llm_config": {
            "provider": "anthropic",
            "model": "claude-3-5-haiku-20241022",
            "api_key": "test-key",
            "temperature": 0.0,
            "max_tokens": 1024,
        },
        "AGENT_TIMEOUT": 30,
    }


@pytest.fixture
def sample_context():
    return {
        "council_results": [
            {"investor": "druckenmiller", "stance": "BULLISH", "qualitative_analysis": "Macro tailwind intact.", "key_observations": ["Strong momentum"]},
            {"investor": "marks", "stance": "BEARISH", "qualitative_analysis": "Cycle top risk.", "key_observations": ["Overvaluation"]},
        ],
        "thesis_health": {"overall_health": "WATCHING", "indicators": [{"name": "RSI", "status": "drifting"}]},
        "signal_contract": {"direction": "bullish", "confidence": {"raw": 0.75}},
        "validation": {"overall_status": "clean", "total_confidence_penalty": 0.0},
    }


class TestCouncilSynthesisAgent:
    def test_empty_report_on_no_context(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        report = agent._empty_narrative()
        assert report["fallback_used"] is True
        assert report["narrative"] == ""
        assert report["position_implication"] == ""
        assert report["watch_item"] == ""

    def test_parses_valid_llm_response(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        llm_text = json.dumps({
            "narrative": "The council is split. Druckenmiller sees macro tailwinds while Marks flags cycle-top risk.",
            "position_implication": "Hold with tighter stop at 140",
            "watch_item": "Fed rate decision on June 18",
        })
        result = agent._parse_narrative_response(llm_text)
        assert result["fallback_used"] is False
        assert "split" in result["narrative"]
        assert result["position_implication"] != ""
        assert result["watch_item"] != ""

    def test_malformed_response_returns_fallback(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        result = agent._parse_narrative_response("this is not json at all!!!")
        assert result["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_execute_no_context_returns_empty(self, agent_config):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        result = await agent.execute()
        assert result["success"] is True
        assert result["data"]["fallback_used"] is True

    def test_prompt_includes_council_and_health(self, agent_config, sample_context):
        agent = CouncilSynthesisAgent("AAPL", agent_config)
        agent.set_synthesis_context(**sample_context)
        prompt = agent._build_synthesis_prompt()
        assert "druckenmiller" in prompt.lower()
        assert "marks" in prompt.lower()
        assert "WATCHING" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_council_synthesis_agent.py -v`
Expected: ImportError — module does not exist yet.

- [ ] **Step 3: Create `src/agents/council_synthesis_agent.py`**

```python
"""LLM-powered council synthesis narrative agent.

Reads council results + thesis health + signal contract + validation report
and produces a ~200-word unified interpretation. Graceful fallback if LLM fails.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CouncilSynthesisAgent(BaseAgent):
    """Synthesizes council output into a unified narrative via LLM."""

    def __init__(self, ticker: str, config: Dict[str, Any]):
        super().__init__(ticker, config)
        self._council_results: List[Dict[str, Any]] = []
        self._thesis_health: Optional[Dict[str, Any]] = None
        self._signal_contract: Optional[Dict[str, Any]] = None
        self._validation: Optional[Dict[str, Any]] = None

    def get_agent_type(self) -> str:
        return "council_synthesis"

    def set_synthesis_context(
        self,
        council_results: List[Dict[str, Any]],
        thesis_health: Optional[Dict[str, Any]] = None,
        signal_contract: Optional[Dict[str, Any]] = None,
        validation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Inject council output and supporting data before execution."""
        self._council_results = council_results or []
        self._thesis_health = thesis_health
        self._signal_contract = signal_contract
        self._validation = validation

    async def fetch_data(self) -> Dict[str, Any]:
        """No external fetch needed; context injected via set_synthesis_context."""
        return {}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Produce synthesis narrative from council + supporting context."""
        if not self._council_results:
            return self._empty_narrative()

        prompt = self._build_synthesis_prompt()

        try:
            llm_text = await self._call_llm(prompt)
            return self._parse_narrative_response(llm_text)
        except Exception as exc:
            logger.warning(f"Council synthesis LLM call failed: {exc}")
            return self._empty_narrative(fallback_used=True)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_synthesis_prompt(self) -> str:
        sections = [
            "You are a senior investment analyst synthesizing the output of an investor council.",
            f"\n## Ticker: {self.ticker}",
            "\n## Council Results:",
        ]

        for r in self._council_results:
            investor = r.get("investor_name") or r.get("investor", "Unknown")
            stance = r.get("stance", "PASS")
            analysis = r.get("qualitative_analysis", "")
            obs = r.get("key_observations", [])
            obs_text = "; ".join(obs[:3]) if obs else "none"
            sections.append(f"\n**{investor}** — {stance}")
            sections.append(f"Analysis: {analysis}")
            sections.append(f"Key observations: {obs_text}")

        if self._thesis_health:
            health = self._thesis_health.get("overall_health", "UNKNOWN")
            indicators = self._thesis_health.get("indicators", [])
            ind_summary = ", ".join(
                f"{i['name']}: {i['status']}" for i in indicators[:5]
            )
            sections.append(f"\n## Thesis Health: {health}")
            if ind_summary:
                sections.append(f"Indicators: {ind_summary}")

        if self._signal_contract:
            direction = self._signal_contract.get("direction", "unknown")
            conf = (self._signal_contract.get("confidence") or {}).get("raw", "?")
            sections.append(f"\n## Signal Contract: direction={direction}, confidence={conf}")

        if self._validation:
            val_status = self._validation.get("overall_status", "unknown")
            penalty = self._validation.get("total_confidence_penalty", 0)
            sections.append(f"\n## Validation: status={val_status}, penalty={penalty}")

        sections.append("""
## Task

Produce a JSON object with exactly these fields:
{
  "narrative": "<~200 words: what does the council agree on, where do they disagree, what does it mean for the position, what's the one thing to watch>",
  "position_implication": "<one-line action: e.g. Hold with tighter stop / Add on weakness / Reduce to half>",
  "watch_item": "<single most important thing to monitor>"
}

Respond ONLY with valid JSON. No markdown fences, no commentary.""")

        return "\n".join(sections)

    # ── Parse ─────────────────────────────────────────────────────────────────

    def _parse_narrative_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response into SynthesisNarrative."""
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Council synthesis JSON parse failed: {exc}")
            return self._empty_narrative(fallback_used=True)

        llm_config = self.config.get("llm_config", {})
        return {
            "narrative": str(data.get("narrative", "")),
            "position_implication": str(data.get("position_implication", "")),
            "watch_item": str(data.get("watch_item", "")),
            "llm_provider": llm_config.get("provider", "unknown"),
            "fallback_used": False,
        }

    def _empty_narrative(self, fallback_used: bool = False) -> Dict[str, Any]:
        return {
            "narrative": "",
            "position_implication": "",
            "watch_item": "",
            "llm_provider": self.config.get("llm_config", {}).get("provider", "unknown"),
            "fallback_used": fallback_used if fallback_used else (not bool(self._council_results)),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_council_synthesis_agent.py -v`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/agents/council_synthesis_agent.py tests/test_council_synthesis_agent.py
git commit -m "feat: add LLM-powered council synthesis narrative agent"
```

---

### Task 5: Orchestrator — wire Phase 2.6 thesis health

**Files:**
- Modify: `src/orchestrator.py`

- [ ] **Step 1: Add import at top of `src/orchestrator.py`**

After the existing `from .validation_rules import validate as run_validation_rules` line, add:

```python
from .thesis_health import evaluate_thesis_health
```

- [ ] **Step 2: Insert Phase 2.6 block in `analyze_ticker()`**

In `src/orchestrator.py`, find the comment `# Baseline observability for rollout gating`. Insert the following block **before** that comment and **after** the Phase 2.5 validation block (after the `except Exception as _val_exc:` block's closing):

```python
            # Phase 2.6: Thesis Health Check
            thesis_health_report: Optional[Dict[str, Any]] = None
            if self.config.get("THESIS_HEALTH_ENABLED", True):
                thesis_card = self.db_manager.get_thesis_card(ticker)
                if thesis_card and thesis_card.get("health_indicators"):
                    try:
                        prev_snapshot = self.db_manager.get_latest_thesis_health(ticker)
                        prev_health = prev_snapshot.get("overall_health") if prev_snapshot else None

                        thesis_health_report = evaluate_thesis_health(
                            thesis_card=thesis_card,
                            agent_results=agent_results,
                            previous_health=prev_health,
                        )

                        # Auto-snapshot baselines back to thesis card
                        if thesis_health_report.get("baselines_updated", 0) > 0:
                            for ind in thesis_health_report["indicators"]:
                                for tc_ind in thesis_card.get("health_indicators", []):
                                    if tc_ind["proxy_signal"] == ind["proxy_signal"] and not tc_ind.get("baseline_value"):
                                        tc_ind["baseline_value"] = ind["current_value"]
                            self.db_manager.upsert_thesis_card(ticker, thesis_card)

                        final_analysis["thesis_health"] = thesis_health_report
                    except Exception as _th_exc:
                        self.logger.warning(f"Thesis health check failed (non-blocking): {_th_exc}")

```

- [ ] **Step 3: Persist thesis health snapshot after DB save**

In `src/orchestrator.py`, after the validation result persistence block (the `if analysis_id and validation_report is not None:` block), add:

```python
            # Persist thesis health snapshot
            if analysis_id and thesis_health_report is not None:
                try:
                    self.db_manager.save_thesis_health_snapshot(
                        analysis_id=analysis_id,
                        ticker=ticker,
                        overall_health=thesis_health_report["overall_health"],
                        previous_health=thesis_health_report.get("previous_health"),
                        health_changed=thesis_health_report.get("health_changed", False),
                        indicators_json=thesis_health_report.get("indicators", []),
                        baselines_updated=thesis_health_report.get("baselines_updated", 0),
                    )
                except Exception as _db_exc:
                    self.logger.warning(f"Failed to save thesis health snapshot: {_db_exc}")
```

- [ ] **Step 4: Run existing orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All existing tests still pass (Phase 2.6 is a no-op when no thesis card exists).

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py
git commit -m "feat: wire Phase 2.6 thesis health check in orchestrator"
```

---

### Task 6: Alert engine — `thesis_health_change` rule type

**Files:**
- Modify: `src/alert_engine.py`
- Modify: `tests/test_alert_engine.py`

- [ ] **Step 1: Add dispatch in `src/alert_engine.py`**

In the `_evaluate_rule` method, after the `spot_check` elif block, add:

```python
        elif rule_type == "thesis_health_change":
            return self._check_thesis_health_change(current, previous)
```

- [ ] **Step 2: Add `_check_thesis_health_change` method**

In `src/alert_engine.py`, after the `_check_spot_check` method, add:

```python
    def _check_thesis_health_change(self, current, previous) -> Optional[Dict[str, Any]]:
        """Fire when thesis health degrades from one analysis to the next."""
        payload = self._analysis_payload(current)
        th = payload.get("thesis_health") or {}
        if not th.get("health_changed"):
            return None

        overall = th.get("overall_health", "UNKNOWN")
        prev = th.get("previous_health", "UNKNOWN")

        # Only fire on degradation, not improvement
        _order = {"INTACT": 0, "WATCHING": 1, "DETERIORATING": 2, "BROKEN": 3}
        if _order.get(overall, -1) <= _order.get(prev, -1):
            return None

        # Build message with top drifting/breached indicators
        indicators = th.get("indicators", [])
        drifted = [i for i in indicators if i.get("status") in ("drifting", "breached")]
        details = []
        for i in drifted[:3]:
            drift_str = f"{i.get('drift_pct', 0):.0f}%" if i.get("drift_pct") is not None else "changed"
            details.append(
                f"{i['name']} {i['status']} {drift_str} from baseline "
                f"({i.get('baseline_value', '?')} → {i.get('current_value', '?')})"
            )

        message = f"[THESIS HEALTH] {current.get('ticker', '')} — {prev} → {overall}"
        if details:
            message += "\n" + "\n".join(details)

        return {
            "message": message,
            "previous_value": prev,
            "current_value": overall,
        }
```

- [ ] **Step 3: Add alert engine tests**

At the end of `tests/test_alert_engine.py`, add a new test class:

```python
class TestThesisHealthChangeAlert:
    """Tests for the thesis_health_change alert rule type."""

    def _make_engine(self, db_manager):
        return AlertEngine(db_manager)

    def test_fires_on_degradation(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {
            "ticker": "NVDA",
            "analysis": {
                "thesis_health": {
                    "overall_health": "WATCHING",
                    "previous_health": "INTACT",
                    "health_changed": True,
                    "indicators": [
                        {"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": "68", "drift_pct": 23.6, "status": "drifting"},
                    ],
                }
            },
        }
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is not None
        assert "THESIS HEALTH" in result["message"]
        assert "INTACT → WATCHING" in result["message"]
        assert result["previous_value"] == "INTACT"
        assert result["current_value"] == "WATCHING"

    def test_silent_on_improvement(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {
            "ticker": "NVDA",
            "analysis": {
                "thesis_health": {
                    "overall_health": "INTACT",
                    "previous_health": "WATCHING",
                    "health_changed": True,
                    "indicators": [],
                }
            },
        }
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is None

    def test_silent_when_no_change(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {
            "ticker": "NVDA",
            "analysis": {
                "thesis_health": {
                    "overall_health": "INTACT",
                    "previous_health": "INTACT",
                    "health_changed": False,
                    "indicators": [],
                }
            },
        }
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is None

    def test_silent_when_no_thesis_health(self, db_manager):
        engine = self._make_engine(db_manager)
        current = {"ticker": "NVDA", "analysis": {}}
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is None
```

- [ ] **Step 4: Run alert engine tests**

Run: `python -m pytest tests/test_alert_engine.py -v`
Expected: All tests pass including the 4 new ones.

- [ ] **Step 5: Commit**

```bash
git add src/alert_engine.py tests/test_alert_engine.py
git commit -m "feat: add thesis_health_change alert rule type"
```

---

### Task 7: API — attach synthesis to council response

**Files:**
- Modify: `src/api.py`
- Modify: `src/models.py`

- [ ] **Step 1: Add synthesis field to `CouncilAnalysisResponse` in `src/models.py`**

In `src/models.py`, in the `CouncilAnalysisResponse` class, add after the `duration_seconds` field:

```python
    synthesis: Optional[dict] = Field(default=None, description="Council synthesis: consensus + narrative")
```

- [ ] **Step 2: Wire synthesis into the council endpoint**

In `src/api.py`, in the `run_council` function, find the line:

```python
    # Persist to DB
    results_dicts = [r.model_dump() for r in investor_results]
    db_manager.save_council_results(ticker, results_dicts, analysis_id=analysis_row.get("id"))
```

Insert the following **between** that save and the `return CouncilAnalysisResponse(...)`:

```python
    # Build council synthesis (Tier 1: deterministic + Tier 2: optional LLM)
    from .council_synthesis import build_consensus
    from .agents.council_synthesis_agent import CouncilSynthesisAgent

    consensus = build_consensus(results_dicts)

    # Load thesis health from latest analysis if available
    latest_analysis = db_manager.get_latest_analysis(ticker)
    analysis_payload = latest_analysis.get("analysis_payload") or {} if latest_analysis else {}
    if isinstance(analysis_payload, str):
        try:
            analysis_payload = json.loads(analysis_payload)
        except Exception:
            analysis_payload = {}
    thesis_health = analysis_payload.get("thesis_health")
    signal_contract = analysis_payload.get("signal_contract_v2")
    validation = analysis_payload.get("validation")

    # Tier 2: LLM narrative (optional, graceful fallback)
    empty_narrative = {"narrative": "", "position_implication": "", "watch_item": "", "llm_provider": "", "fallback_used": True}
    narrative = empty_narrative
    try:
        synth_agent = CouncilSynthesisAgent(ticker, config)
        synth_agent.set_synthesis_context(
            council_results=results_dicts,
            thesis_health=thesis_health,
            signal_contract=signal_contract,
            validation=validation,
        )
        timeout = config.get("AGENT_TIMEOUT", 30)
        synth_result = await asyncio.wait_for(synth_agent.execute(), timeout=timeout)
        if synth_result.get("success") and synth_result.get("data"):
            narrative = synth_result["data"]
    except Exception as synth_exc:
        logger.warning(f"Council synthesis narrative failed (non-blocking): {synth_exc}")

    synthesis = {"consensus": consensus, "narrative": narrative}

    # Persist synthesis
    try:
        db_manager.save_council_synthesis(ticker, analysis_row.get("id"), synthesis)
    except Exception as _db_exc:
        logger.warning(f"Failed to save council synthesis: {_db_exc}")
```

- [ ] **Step 3: Add `synthesis` to the return statement**

In `src/api.py`, update the `return CouncilAnalysisResponse(...)` call at the end of `run_council` to include:

```python
        synthesis=synthesis,
```

Add it after `disagreements=disagreements,`.

- [ ] **Step 4: Also attach synthesis in the GET endpoint**

In `src/api.py`, in the `get_council_results` function (the GET handler), before the `return CouncilAnalysisResponse(...)`, add:

```python
    # Load cached synthesis if available
    cached_synthesis = db_manager.get_latest_council_synthesis(ticker)
    synthesis = None
    if cached_synthesis:
        synthesis = {
            "consensus": cached_synthesis.get("consensus_json"),
            "narrative": cached_synthesis.get("narrative_json"),
        }
```

Then update the return to include `synthesis=synthesis,` after `disagreements=disagreements,`.

- [ ] **Step 5: Run API tests**

Run: `python -m pytest tests/test_api.py -v`
Expected: All existing tests pass. The new `synthesis` field defaults to `None` so existing tests are unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/api.py src/models.py
git commit -m "feat: attach council synthesis to council API response"
```

---

### Task 8: Frontend — SynthesisCard + HealthIndicatorStrip

**Files:**
- Modify: `frontend/src/components/CouncilPanel.jsx`

- [ ] **Step 1: Add SynthesisCard component**

In `frontend/src/components/CouncilPanel.jsx`, after the `PlaybookSection` component definition (before `const CouncilPanel = ...`), add:

```jsx
// ── Synthesis Card ──────────────────────────────────────────────────────────

const SynthesisCard = ({ synthesis, thesisHealth }) => {
  if (!synthesis?.consensus) return null;
  const { consensus, narrative } = synthesis;
  const dist = consensus.stance_distribution || {};
  const total = (dist.bullish || 0) + (dist.cautious || 0) + (dist.bearish || 0);
  const majority = consensus.majority_stance || 'PASS';
  const conviction = Math.round((consensus.conviction_strength || 0) * 100);
  const healthConsensus = consensus.thesis_health_consensus || 'UNKNOWN';
  const disagreements = consensus.disagreements || [];
  const topScenarios = consensus.top_scenarios || [];

  const healthColor = healthConfig[healthConsensus]?.color || healthConfig.UNKNOWN.color;
  const healthBg = healthConfig[healthConsensus]?.bg || healthConfig.UNKNOWN.bg;
  const majorityConfig = stanceConfig[majority] || stanceConfig.PASS;

  return (
    <Motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card-elevated rounded-xl p-5 space-y-4"
    >
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">Council Synthesis</p>
          <span
            className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
            style={{ color: majorityConfig.color, background: majorityConfig.bg, border: `1px solid ${majorityConfig.border}` }}
          >
            {majority} ({conviction}% conviction)
          </span>
          {healthConsensus !== 'UNKNOWN' && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ color: healthColor, background: healthBg }}>
              Thesis: {healthConsensus}
            </span>
          )}
        </div>
      </div>

      {/* Stance distribution bar */}
      {total > 0 && (
        <div className="flex rounded-full overflow-hidden h-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
          {dist.bullish > 0 && (
            <div style={{ width: `${(dist.bullish / total) * 100}%`, background: stanceConfig.BULLISH.color }} className="transition-all duration-500" />
          )}
          {dist.cautious > 0 && (
            <div style={{ width: `${(dist.cautious / total) * 100}%`, background: stanceConfig.CAUTIOUS.color }} className="transition-all duration-500" />
          )}
          {dist.bearish > 0 && (
            <div style={{ width: `${(dist.bearish / total) * 100}%`, background: stanceConfig.BEARISH.color }} className="transition-all duration-500" />
          )}
        </div>
      )}

      {/* Disagreements */}
      {disagreements.length > 0 && (
        <div className="space-y-1.5">
          {disagreements.map((d, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className="text-amber-400 mt-0.5 shrink-0">⚡</span>
              <span className="text-gray-400"><span className="text-gray-200 font-medium">{d.investor_name || d.investor}</span>: {d.flag}</span>
            </div>
          ))}
        </div>
      )}

      {/* Top if-then scenarios */}
      {topScenarios.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-gray-600">Top Scenarios</p>
          {topScenarios.map((s, i) => (
            <div key={i} className="text-[11px] text-gray-400 flex items-start gap-2">
              <span className="text-accent-cyan shrink-0 mt-0.5">→</span>
              <span><span className="text-gray-300">{s.condition}</span> {s.action}</span>
              <span className="text-[9px] text-gray-600 ml-auto shrink-0">{s.investor}</span>
            </div>
          ))}
        </div>
      )}

      {/* LLM Narrative */}
      {narrative?.narrative && !narrative.fallback_used && (
        <div className="space-y-2 pt-2 border-t border-white/5">
          <p className="text-[11px] text-gray-300 leading-relaxed">{narrative.narrative}</p>
          {narrative.position_implication && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="text-accent-cyan font-bold">▸</span>
              <span className="text-gray-200 font-medium">{narrative.position_implication}</span>
            </div>
          )}
          {narrative.watch_item && (
            <div className="flex items-center gap-2 text-[10px] text-gray-500">
              <span>👁</span>
              <span>Watch: {narrative.watch_item}</span>
            </div>
          )}
        </div>
      )}
    </Motion.div>
  );
};

// ── Health Indicator Strip ───────────────────────────────────────────────────

const statusDot = { stable: '#17c964', drifting: '#f5a524', breached: '#f31260' };

const HealthIndicatorStrip = ({ thesisHealth }) => {
  if (!thesisHealth?.indicators?.length) return null;
  const [expanded, setExpanded] = React.useState(null);
  const indicators = thesisHealth.indicators;

  return (
    <div className="flex flex-wrap gap-2">
      {indicators.map((ind, i) => {
        const isExpanded = expanded === i;
        return (
          <button
            key={ind.proxy_signal || i}
            onClick={() => setExpanded(isExpanded ? null : i)}
            className="flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-lg border border-white/8 bg-white/[0.02] hover:bg-white/[0.05] transition-colors cursor-pointer"
          >
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: statusDot[ind.status] || statusDot.stable }} />
            <span className="text-gray-400">{ind.name}</span>
            <span className="text-gray-200 font-medium">{ind.current_value}</span>
            {isExpanded && ind.baseline_value && (
              <span className="text-gray-600 ml-1">
                baseline: {ind.baseline_value}
                {ind.drift_pct != null && ` (${ind.drift_pct.toFixed(1)}%)`}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
```

- [ ] **Step 2: Render SynthesisCard and HealthIndicatorStrip in main component**

In `frontend/src/components/CouncilPanel.jsx`, in the main `CouncilPanel` component's return JSX, find:

```jsx
      {/* Disagreement banner */}
      <AnimatePresence>
        {hasResults && <DisagreementBanner disagreements={disagreements} />}
      </AnimatePresence>
```

Insert the following **before** that block (i.e., between the error div and the disagreement banner):

```jsx
      {/* Synthesis card */}
      {hasResults && councilData?.synthesis && (
        <SynthesisCard
          synthesis={councilData.synthesis}
          thesisHealth={analysis?.analysis?.thesis_health || analysis?.thesis_health}
        />
      )}

      {/* Health indicator strip */}
      {(analysis?.analysis?.thesis_health || analysis?.thesis_health) && (
        <HealthIndicatorStrip
          thesisHealth={analysis?.analysis?.thesis_health || analysis?.thesis_health}
        />
      )}
```

- [ ] **Step 3: Build frontend to verify no errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CouncilPanel.jsx
git commit -m "feat(ui): add SynthesisCard and HealthIndicatorStrip to Council tab"
```

---

### Task 9: Integration tests + full suite

**Files:**
- Create: `tests/test_thesis_health_integration.py`

- [ ] **Step 1: Create integration test file**

```python
"""Integration tests for thesis health monitor + council synthesis."""

import json
import pytest
from src.thesis_health import evaluate_thesis_health
from src.council_synthesis import build_consensus


class TestThesisHealthEndToEnd:
    """Full flow: thesis card + agent results → health report → alert check."""

    def test_full_health_check_flow(self, db_manager):
        # Create a thesis card
        card = db_manager.upsert_thesis_card("NVDA", {
            "structural_thesis": "AI compute leader",
            "load_bearing_assumption": "revenue growth",
            "health_indicators": [
                {"name": "RSI", "proxy_signal": "rsi", "baseline_value": "55", "current_value": None},
                {"name": "Revenue Growth", "proxy_signal": "revenue_growth", "baseline_value": "0.28", "current_value": None},
            ],
        })
        assert card["ticker"] == "NVDA"

        # Run health check with stable data
        agent_results = {
            "technical": {"success": True, "data": {"rsi": 55}},
            "fundamentals": {"success": True, "data": {"revenue_growth": 0.28}},
        }
        report = evaluate_thesis_health(
            thesis_card=card,
            agent_results=agent_results,
            previous_health=None,
        )
        assert report["overall_health"] == "INTACT"

        # Save snapshot
        row_id = db_manager.save_thesis_health_snapshot(
            analysis_id=1, ticker="NVDA",
            overall_health=report["overall_health"],
            previous_health=report.get("previous_health"),
            health_changed=report["health_changed"],
            indicators_json=report["indicators"],
            baselines_updated=report["baselines_updated"],
        )
        assert row_id is not None

        # Run health check with drifted data
        agent_results["technical"]["data"]["rsi"] = 70
        report2 = evaluate_thesis_health(
            thesis_card=card,
            agent_results=agent_results,
            previous_health="INTACT",
        )
        assert report2["overall_health"] == "WATCHING"
        assert report2["health_changed"] is True

        # Verify alert engine catches it
        from src.alert_engine import AlertEngine
        engine = AlertEngine(db_manager)
        current = {"ticker": "NVDA", "analysis": {"thesis_health": report2}}
        rule = {"rule_type": "thesis_health_change", "threshold": None}
        result = engine._evaluate_rule(rule, current, previous=None)
        assert result is not None
        assert "INTACT → WATCHING" in result["message"]


class TestCouncilSynthesisEndToEnd:
    """Full flow: council results → consensus + DB persistence."""

    def test_consensus_and_persist(self, db_manager):
        council_results = [
            {"investor": "druckenmiller", "investor_name": "Druckenmiller", "stance": "BULLISH", "thesis_health": "INTACT",
             "disagreement_flag": None, "if_then_scenarios": [{"type": "macro", "condition": "If Fed cuts", "action": "add", "conviction": "high"}]},
            {"investor": "marks", "investor_name": "Marks", "stance": "BEARISH", "thesis_health": "DETERIORATING",
             "disagreement_flag": "Cycle top risk", "if_then_scenarios": []},
        ]
        consensus = build_consensus(council_results)
        assert consensus["majority_stance"] == "BULLISH"
        assert len(consensus["disagreements"]) == 1

        synthesis = {"consensus": consensus, "narrative": {"narrative": "", "fallback_used": True}}
        row_id = db_manager.save_council_synthesis("AAPL", 1, synthesis)
        assert row_id is not None

        loaded = db_manager.get_latest_council_synthesis("AAPL")
        assert loaded is not None
        assert loaded["consensus_json"]["majority_stance"] == "BULLISH"
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_thesis_health_integration.py -v`
Expected: All tests pass.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (previous 249 + new tests).

- [ ] **Step 4: Commit all remaining changes**

```bash
git add tests/test_thesis_health_integration.py
git commit -m "test: add thesis health + council synthesis integration tests"
```

- [ ] **Step 5: Push to main**

```bash
git push origin main
```

---

### Task 10: Update CLAUDE.md and plans index

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/plans/INDEX.md`

- [ ] **Step 1: Update plans INDEX.md**

In `docs/plans/INDEX.md`, in the "In Progress / Planned" table, update the Investor Council row to reflect Phase 3 + 4 completion, and add a completed entry to the main table:

Add to the completed plans table:
```markdown
| 2026-03-30 | [Thesis Health + Synthesis View](../superpowers/plans/2026-03-30-thesis-health-synthesis-view.md) | ✅ Completed | Thesis health monitor (Phase 2.6) + council synthesis (deterministic consensus + LLM narrative) |
```

Update the Investor Council entry in "In Progress / Planned":
```markdown
| **Investor Council** | Qualitative layer — 26 investor personas. Phase 2 (primary 5) complete. **Phase 3 (thesis health monitor) complete. Phase 4 (synthesis view) complete.** Phase 5 (ATLAS layering) planned. | [Design spec](../superpowers/specs/2026-03-30-thesis-health-synthesis-view-design.md) |
```

- [ ] **Step 2: Update test count in CLAUDE.md**

Update all references to the test count to match the new total (run `python -m pytest tests/ --co -q | tail -1` to get exact count).

- [ ] **Step 3: Add new files to CLAUDE.md core files section**

After the validation_rules/council_validator entries:
```markdown
- **`src/thesis_health.py`** - Thesis health indicator drift detection and aggregate rollup (INTACT/WATCHING/DETERIORATING/BROKEN)
- **`src/council_synthesis.py`** - Deterministic council consensus aggregation (stance distribution, disagreements, scenarios)
- **`src/agents/council_synthesis_agent.py`** - LLM-powered council synthesis narrative agent with graceful fallback
```

Add to the DB tables list:
```markdown
20. **`thesis_health_snapshots`** - Per-analysis thesis health snapshots (indicator drift, overall health status)
21. **`council_synthesis`** - Council consensus + LLM narrative per council run
```

- [ ] **Step 4: Commit and push**

```bash
git add CLAUDE.md CLAUDE.MD docs/plans/INDEX.md
git commit -m "docs: update CLAUDE.md and plans index for thesis health + synthesis view"
git push origin main
```
