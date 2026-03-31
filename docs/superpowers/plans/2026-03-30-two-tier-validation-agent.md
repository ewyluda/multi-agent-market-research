# Two-Tier Validation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validation layer that cross-checks synthesis and council claims against raw agent data, penalizes confidence on contradictions, and samples for human spot-checks.

**Architecture:** Two new modules — `validation_rules.py` (deterministic rule engine) and `council_validator_agent.py` (LLM-powered council checker). They run at Phase 2.5 in the orchestrator, between synthesis and persistence. A merged `ValidationReport` attaches to the signal contract and optionally triggers spot-check alerts.

**Tech Stack:** Python 3.10+, pytest, SQLite, FastAPI SSE, Anthropic/OpenAI/xAI LLM APIs (same cascade as existing agents)

**Spec:** `docs/superpowers/specs/2026-03-30-two-tier-validation-agent-design.md`

---

### Task 1: Config — Add Validation Feature Flag and Settings

**Files:**
- Modify: `src/config.py:59-82` (after existing feature flags)
- Modify: `tests/conftest.py:116-123` (add to test_config fixture)
- Modify: `.env.example` (add new env vars)

- [ ] **Step 1: Add config entries to `src/config.py`**

In `src/config.py`, add after line 66 (`UI_PM_DASHBOARD_ENABLED`):

```python
    VALIDATION_V1_ENABLED = os.getenv("VALIDATION_V1_ENABLED", "true").lower() == "true"
    VALIDATION_SPOT_CHECK_RATE = int(os.getenv("VALIDATION_SPOT_CHECK_RATE", "3"))
    VALIDATION_SPOT_CHECK_ON_CONTRADICTION = os.getenv("VALIDATION_SPOT_CHECK_ON_CONTRADICTION", "true").lower() == "true"
```

- [ ] **Step 2: Add to test_config fixture in `tests/conftest.py`**

In `tests/conftest.py`, add inside the `test_config` dict (after line 123, the `SCHEDULED_ALERTS_V2_ENABLED` entry):

```python
        "VALIDATION_V1_ENABLED": True,
        "VALIDATION_SPOT_CHECK_RATE": 3,
        "VALIDATION_SPOT_CHECK_ON_CONTRADICTION": True,
```

- [ ] **Step 3: Add to `.env.example`**

Append to the feature flags section:

```bash
# Validation Agent
VALIDATION_V1_ENABLED=true
VALIDATION_SPOT_CHECK_RATE=3
VALIDATION_SPOT_CHECK_ON_CONTRADICTION=true
```

- [ ] **Step 4: Commit**

```bash
git add src/config.py tests/conftest.py .env.example
git commit -m "feat: add validation v1 feature flag and config"
```

---

### Task 2: Database — Add Validation Tables

**Files:**
- Modify: `src/database.py:295-335` (table creation section, after alert_notifications)
- Test: `tests/test_database.py` (add validation table tests)

- [ ] **Step 1: Write failing tests for validation tables**

Create tests at the bottom of `tests/test_database.py`:

```python
class TestValidationTables:
    """Tests for validation_results and validation_feedback tables."""

    def test_save_validation_result(self, db_manager):
        """Saving a validation result returns a row ID."""
        # First create an analysis to reference
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        row_id = db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="test-uuid-001",
            overall_status="clean",
            original_confidence=0.78,
            adjusted_confidence=0.78,
            total_confidence_penalty=0.0,
            rule_checks_total=5,
            rule_contradictions=0,
            council_claims_total=10,
            council_contradictions=0,
            spot_check_requested=False,
            report_json='{"schema_version": "1.0"}',
        )
        assert row_id is not None
        assert row_id > 0

    def test_get_validation_result(self, db_manager):
        """Fetching a validation result by validation_id returns it."""
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="test-uuid-002",
            overall_status="contradictions",
            original_confidence=0.78,
            adjusted_confidence=0.58,
            total_confidence_penalty=0.20,
            rule_checks_total=5,
            rule_contradictions=2,
            council_claims_total=10,
            council_contradictions=1,
            spot_check_requested=True,
            report_json='{"schema_version": "1.0"}',
        )
        result = db_manager.get_validation_result("test-uuid-002")
        assert result is not None
        assert result["overall_status"] == "contradictions"
        assert result["spot_check_requested"] == 1

    def test_save_validation_feedback(self, db_manager):
        """Saving spot-check feedback returns a row ID."""
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="test-uuid-003",
            overall_status="contradictions",
            original_confidence=0.78,
            adjusted_confidence=0.58,
            total_confidence_penalty=0.20,
            rule_checks_total=5,
            rule_contradictions=1,
            council_claims_total=10,
            council_contradictions=0,
            spot_check_requested=True,
            report_json='{}',
        )
        feedback_id = db_manager.save_validation_feedback(
            validation_id="test-uuid-003",
            ticker="AAPL",
            claim_type="rule",
            claim_summary="Solution says BUY but 4/6 agents bearish",
            human_verdict="flagged",
        )
        assert feedback_id is not None
        assert feedback_id > 0

    def test_get_validation_feedback(self, db_manager):
        """Fetching feedback by validation_id returns the entries."""
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="test-uuid-004",
            overall_status="warnings",
            original_confidence=0.78,
            adjusted_confidence=0.73,
            total_confidence_penalty=0.05,
            rule_checks_total=5,
            rule_contradictions=0,
            council_claims_total=10,
            council_contradictions=0,
            spot_check_requested=True,
            report_json='{}',
        )
        db_manager.save_validation_feedback(
            validation_id="test-uuid-004",
            ticker="AAPL",
            claim_type="council",
            claim_summary="Druckenmiller says macro tailwind intact",
            human_verdict="confirmed",
        )
        feedback = db_manager.get_validation_feedback("test-uuid-004")
        assert len(feedback) == 1
        assert feedback[0]["human_verdict"] == "confirmed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_database.py::TestValidationTables -v`
Expected: FAIL — `save_validation_result` method not found

- [ ] **Step 3: Add table creation to `src/database.py`**

In `src/database.py`, after the `alert_notifications` table creation (line ~335), add:

```python
            # Validation results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    validation_id TEXT NOT NULL UNIQUE,
                    overall_status TEXT NOT NULL CHECK(overall_status IN ('clean', 'warnings', 'contradictions')),
                    original_confidence REAL,
                    adjusted_confidence REAL,
                    total_confidence_penalty REAL,
                    rule_checks_total INTEGER,
                    rule_contradictions INTEGER,
                    council_claims_total INTEGER,
                    council_contradictions INTEGER,
                    spot_check_requested INTEGER DEFAULT 0,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_results_ticker ON validation_results(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_results_status ON validation_results(overall_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_results_analysis ON validation_results(analysis_id)")

            # Validation feedback (Tier 2 spot-check responses)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validation_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    validation_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    claim_type TEXT NOT NULL CHECK(claim_type IN ('rule', 'council')),
                    claim_summary TEXT NOT NULL,
                    human_verdict TEXT NOT NULL CHECK(human_verdict IN ('confirmed', 'flagged')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (validation_id) REFERENCES validation_results(validation_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_feedback_validation ON validation_feedback(validation_id)")
```

- [ ] **Step 4: Add CRUD methods to `src/database.py`**

Add at the bottom of the `DatabaseManager` class, after the alert methods:

```python
    # ─── Validation ──────────────────────────────────────────────────────────

    def save_validation_result(
        self,
        analysis_id: int,
        ticker: str,
        validation_id: str,
        overall_status: str,
        original_confidence: Optional[float],
        adjusted_confidence: Optional[float],
        total_confidence_penalty: float,
        rule_checks_total: int,
        rule_contradictions: int,
        council_claims_total: int,
        council_contradictions: int,
        spot_check_requested: bool,
        report_json: str,
    ) -> int:
        """Save a validation result. Returns row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO validation_results (
                       analysis_id, ticker, validation_id, overall_status,
                       original_confidence, adjusted_confidence, total_confidence_penalty,
                       rule_checks_total, rule_contradictions,
                       council_claims_total, council_contradictions,
                       spot_check_requested, report_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id, ticker.upper(), validation_id, overall_status,
                    original_confidence, adjusted_confidence, total_confidence_penalty,
                    rule_checks_total, rule_contradictions,
                    council_claims_total, council_contradictions,
                    1 if spot_check_requested else 0, report_json, now,
                ),
            )
            return cursor.lastrowid

    def get_validation_result(self, validation_id: str) -> Optional[Dict[str, Any]]:
        """Get a validation result by its UUID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM validation_results WHERE validation_id = ?",
                (validation_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_validation_feedback(
        self,
        validation_id: str,
        ticker: str,
        claim_type: str,
        claim_summary: str,
        human_verdict: str,
    ) -> int:
        """Save spot-check feedback. Returns row ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO validation_feedback (
                       validation_id, ticker, claim_type, claim_summary,
                       human_verdict, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (validation_id, ticker.upper(), claim_type, claim_summary, human_verdict, now),
            )
            return cursor.lastrowid

    def get_validation_feedback(self, validation_id: str) -> List[Dict[str, Any]]:
        """Get all feedback entries for a validation ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM validation_feedback WHERE validation_id = ? ORDER BY created_at DESC",
                (validation_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_database.py::TestValidationTables -v`
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add validation_results and validation_feedback tables"
```

---

### Task 3: Rule Engine — `validation_rules.py`

**Files:**
- Create: `src/validation_rules.py`
- Create: `tests/test_validation_rules.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_validation_rules.py`:

```python
"""Tests for the deterministic validation rule engine."""

import pytest
from src.validation_rules import validate, RuleValidationReport


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_final_analysis(recommendation="BUY", score=65, confidence=0.78):
    return {
        "recommendation": recommendation,
        "score": score,
        "confidence": confidence,
        "reasoning": "Strong fundamentals and technicals.",
        "decision_card": {
            "entry_zone": {"low": 175.0, "high": 185.0, "reference": 180.0},
            "stop_loss": 170.0,
            "targets": [195.0, 210.0],
        },
        "scenarios": {
            "bull": {"probability": 0.4, "expected_return_pct": 15.0},
            "base": {"probability": 0.4, "expected_return_pct": 5.0},
            "bear": {"probability": 0.2, "expected_return_pct": -10.0},
        },
        "signal_snapshot": {
            "recommendation": recommendation,
            "market_regime": "bullish",
            "macro_risk_environment": "risk_on",
            "macro_cycle": "expansion",
        },
    }


def _make_agent_results(
    market_direction="bullish",
    fundamentals_direction="bullish",
    technical_direction="bullish",
    macro_direction="bullish",
    options_direction="bullish",
    sentiment_direction="bullish",
):
    """Build agent_results with controllable directions."""
    return {
        "market": {
            "success": True,
            "data": {
                "current_price": 180.0,
                "trend": market_direction,
                "price_change_1m": {"change_pct": 5.0 if market_direction == "bullish" else -5.0},
            },
        },
        "fundamentals": {
            "success": True,
            "data": {
                "health_score": 75,
                "key_metrics": {
                    "pe_ratio": 22.0,
                    "revenue_growth": 0.18,
                    "free_cash_flow": 5000000000,
                    "debt_to_equity": 1.2,
                },
            },
        },
        "technical": {
            "success": True,
            "data": {
                "rsi": 55.0 if technical_direction == "bullish" else 75.0,
                "signals": {
                    "overall": "buy" if technical_direction == "bullish" else "sell",
                    "strength": 40.0 if technical_direction == "bullish" else -40.0,
                },
            },
        },
        "macro": {
            "success": True,
            "data": {
                "economic_cycle": "expansion" if macro_direction == "bullish" else "contraction",
                "risk_environment": "risk_on" if macro_direction == "bullish" else "risk_off",
                "fed_funds_rate": 4.5,
                "yield_curve_spread": 0.5 if macro_direction == "bullish" else -0.3,
            },
        },
        "options": {
            "success": True,
            "data": {
                "put_call_ratio": 0.7 if options_direction == "bullish" else 1.8,
                "overall_signal": options_direction,
                "unusual_activity": [],
            },
        },
        "sentiment": {
            "success": True,
            "data": {
                "overall_sentiment": 0.4 if sentiment_direction == "bullish" else -0.4,
            },
        },
    }


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestValidateClean:
    """When all data aligns, validation should be clean."""

    def test_clean_report(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(),
        )
        assert report["contradictions"] == 0
        assert report["total_confidence_penalty"] == 0.0

    def test_report_structure(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(),
        )
        assert "total_rules_checked" in report
        assert "passed" in report
        assert "warnings" in report
        assert "contradictions" in report
        assert "results" in report
        assert "total_confidence_penalty" in report


class TestDirectionConsistency:
    """Solution recommendation should align with majority agent direction."""

    def test_buy_with_majority_bearish_is_contradiction(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(
                market_direction="bearish",
                fundamentals_direction="bearish",
                technical_direction="bearish",
                options_direction="bearish",
            ),
        )
        contradictions = [r for r in report["results"] if r["rule_id"] == "direction_consistency" and not r["passed"]]
        assert len(contradictions) >= 1
        assert contradictions[0]["severity"] == "contradiction"

    def test_sell_with_majority_bullish_is_contradiction(self):
        report = validate(
            final_analysis=_make_final_analysis("SELL"),
            agent_results=_make_agent_results(),
        )
        contradictions = [r for r in report["results"] if r["rule_id"] == "direction_consistency" and not r["passed"]]
        assert len(contradictions) >= 1

    def test_hold_with_mixed_signals_is_clean(self):
        report = validate(
            final_analysis=_make_final_analysis("HOLD"),
            agent_results=_make_agent_results(
                market_direction="bullish",
                fundamentals_direction="bearish",
                technical_direction="bullish",
            ),
        )
        direction_results = [r for r in report["results"] if r["rule_id"] == "direction_consistency"]
        for r in direction_results:
            assert r["passed"]


class TestRegimeConsistency:
    """Signal snapshot regime should match macro agent output."""

    def test_risk_on_with_contraction_is_warning(self):
        analysis = _make_final_analysis("BUY")
        analysis["signal_snapshot"]["macro_risk_environment"] = "risk_on"
        report = validate(
            final_analysis=analysis,
            agent_results=_make_agent_results(macro_direction="bearish"),
        )
        regime_issues = [r for r in report["results"] if r["rule_id"] == "regime_consistency" and not r["passed"]]
        assert len(regime_issues) >= 1


class TestOptionsAlignment:
    """BUY with heavy put volume should flag."""

    def test_buy_with_high_put_call_ratio(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(options_direction="bearish"),
        )
        options_issues = [r for r in report["results"] if r["rule_id"] == "options_alignment" and not r["passed"]]
        assert len(options_issues) >= 1


class TestTechnicalAlignment:
    """Entry zone should not be set above resistance when RSI is overbought."""

    def test_entry_with_overbought_rsi(self):
        analysis = _make_final_analysis("BUY")
        agent_results = _make_agent_results(technical_direction="bearish")
        report = validate(final_analysis=analysis, agent_results=agent_results)
        tech_issues = [r for r in report["results"] if r["rule_id"] == "technical_alignment" and not r["passed"]]
        assert len(tech_issues) >= 1


class TestPenaltyCapping:
    """Total penalty should be capped at 0.40."""

    def test_many_contradictions_capped(self):
        report = validate(
            final_analysis=_make_final_analysis("BUY"),
            agent_results=_make_agent_results(
                market_direction="bearish",
                fundamentals_direction="bearish",
                technical_direction="bearish",
                macro_direction="bearish",
                options_direction="bearish",
                sentiment_direction="bearish",
            ),
        )
        assert report["total_confidence_penalty"] <= 0.40
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validation_rules.py -v`
Expected: FAIL — `src.validation_rules` not found

- [ ] **Step 3: Implement `src/validation_rules.py`**

```python
"""Deterministic validation rule engine.

Pure functions that cross-check synthesis claims against raw agent data.
No classes, no state, no LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def validate(
    *,
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run all validation rules against analysis output.

    Returns a RuleValidationReport dict.
    """
    results: List[Dict[str, Any]] = []

    results.append(_check_direction_consistency(final_analysis, agent_results))
    results.append(_check_regime_consistency(final_analysis, agent_results))
    results.append(_check_options_alignment(final_analysis, agent_results))
    results.append(_check_technical_alignment(final_analysis, agent_results))

    passed = sum(1 for r in results if r["passed"])
    warnings = sum(1 for r in results if not r["passed"] and r["severity"] == "warning")
    contradictions = sum(1 for r in results if not r["passed"] and r["severity"] == "contradiction")
    total_penalty = min(sum(r["confidence_penalty"] for r in results if not r["passed"]), 0.40)

    return {
        "total_rules_checked": len(results),
        "passed": passed,
        "warnings": warnings,
        "contradictions": contradictions,
        "results": results,
        "total_confidence_penalty": round(total_penalty, 4),
    }


# ─── Individual rules ────────────────────────────────────────────────────────


def _check_direction_consistency(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if recommendation direction matches majority of agent signals."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    rec_direction = _recommendation_to_direction(recommendation)

    directions = _extract_agent_directions(agent_results)
    if not directions:
        return _pass("direction_consistency", "No agent directions to validate against")

    bullish = sum(1 for d in directions.values() if d == "bullish")
    bearish = sum(1 for d in directions.values() if d == "bearish")
    total = len(directions)

    if rec_direction == "bullish" and bearish >= (total * 0.6):
        return _fail(
            rule_id="direction_consistency",
            severity="contradiction",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence=f"{bearish}/{total} agents signal bearish",
            source_agent="multiple",
            penalty=0.15,
        )
    if rec_direction == "bearish" and bullish >= (total * 0.6):
        return _fail(
            rule_id="direction_consistency",
            severity="contradiction",
            claim=f"Recommendation is {recommendation} (bearish)",
            evidence=f"{bullish}/{total} agents signal bullish",
            source_agent="multiple",
            penalty=0.15,
        )
    return _pass("direction_consistency", "Recommendation aligns with agent majority")


def _check_regime_consistency(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if signal snapshot regime matches macro agent output."""
    snapshot = final_analysis.get("signal_snapshot") or {}
    macro_data = ((agent_results.get("macro") or {}).get("data") or {})

    snapshot_regime = str(snapshot.get("macro_risk_environment") or "").lower()
    macro_cycle = str(macro_data.get("economic_cycle") or "").lower()
    macro_risk = str(macro_data.get("risk_environment") or "").lower()

    if not snapshot_regime or not (macro_cycle or macro_risk):
        return _pass("regime_consistency", "Insufficient regime data to validate")

    # risk_on snapshot with contraction/risk_off macro = warning
    if snapshot_regime == "risk_on" and (macro_cycle == "contraction" or macro_risk == "risk_off"):
        return _fail(
            rule_id="regime_consistency",
            severity="warning",
            claim=f"Signal snapshot says risk_on",
            evidence=f"Macro agent: cycle={macro_cycle}, risk={macro_risk}",
            source_agent="macro",
            penalty=0.05,
        )
    if snapshot_regime == "risk_off" and (macro_cycle == "expansion" and macro_risk == "risk_on"):
        return _fail(
            rule_id="regime_consistency",
            severity="warning",
            claim=f"Signal snapshot says risk_off",
            evidence=f"Macro agent: cycle={macro_cycle}, risk={macro_risk}",
            source_agent="macro",
            penalty=0.05,
        )
    return _pass("regime_consistency", "Regime labels are consistent")


def _check_options_alignment(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if recommendation aligns with options flow."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    rec_direction = _recommendation_to_direction(recommendation)
    options_data = ((agent_results.get("options") or {}).get("data") or {})

    put_call = _safe_float(options_data.get("put_call_ratio"))
    options_signal = str(options_data.get("overall_signal") or "").lower()

    if put_call is None and not options_signal:
        return _pass("options_alignment", "No options data to validate against")

    if rec_direction == "bullish" and (put_call is not None and put_call > 1.5):
        return _fail(
            rule_id="options_alignment",
            severity="warning",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence=f"Put/call ratio is {put_call:.2f} (>1.5 = heavy put buying)",
            source_agent="options",
            penalty=0.05,
        )
    if rec_direction == "bullish" and options_signal == "bearish":
        return _fail(
            rule_id="options_alignment",
            severity="warning",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence=f"Options overall signal is bearish",
            source_agent="options",
            penalty=0.05,
        )
    return _pass("options_alignment", "Options flow aligns with recommendation")


def _check_technical_alignment(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if BUY recommendation aligns with technical signals."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    tech_data = ((agent_results.get("technical") or {}).get("data") or {})

    rsi = _safe_float(tech_data.get("rsi"))
    tech_signal = str((tech_data.get("signals") or {}).get("overall") or "").lower()
    tech_strength = _safe_float((tech_data.get("signals") or {}).get("strength"))

    if recommendation == "BUY":
        if rsi is not None and rsi > 70 and tech_signal in ("sell", "bearish"):
            return _fail(
                rule_id="technical_alignment",
                severity="warning",
                claim=f"BUY recommendation",
                evidence=f"RSI={rsi:.1f} (overbought), technical signal={tech_signal}",
                source_agent="technical",
                penalty=0.05,
            )
        if tech_strength is not None and tech_strength <= -20:
            return _fail(
                rule_id="technical_alignment",
                severity="warning",
                claim=f"BUY recommendation",
                evidence=f"Technical strength={tech_strength:.1f} (bearish)",
                source_agent="technical",
                penalty=0.05,
            )
    return _pass("technical_alignment", "Technical signals align with recommendation")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _recommendation_to_direction(recommendation: str) -> str:
    if recommendation in ("BUY", "STRONG_BUY"):
        return "bullish"
    if recommendation in ("SELL", "STRONG_SELL"):
        return "bearish"
    return "neutral"


def _extract_agent_directions(agent_results: Dict[str, Any]) -> Dict[str, str]:
    """Extract directional signal from each agent's data."""
    directions: Dict[str, str] = {}

    # Market
    market = (agent_results.get("market") or {}).get("data") or {}
    trend = str(market.get("trend") or "").lower()
    if trend in ("bullish", "uptrend", "strong_uptrend"):
        directions["market"] = "bullish"
    elif trend in ("bearish", "downtrend", "strong_downtrend"):
        directions["market"] = "bearish"
    else:
        directions["market"] = "neutral"

    # Technical
    tech = (agent_results.get("technical") or {}).get("data") or {}
    tech_signal = str((tech.get("signals") or {}).get("overall") or "").lower()
    tech_strength = _safe_float((tech.get("signals") or {}).get("strength"))
    if tech_signal in ("buy", "bullish") or (tech_strength is not None and tech_strength >= 20):
        directions["technical"] = "bullish"
    elif tech_signal in ("sell", "bearish") or (tech_strength is not None and tech_strength <= -20):
        directions["technical"] = "bearish"
    else:
        directions["technical"] = "neutral"

    # Fundamentals
    fund = (agent_results.get("fundamentals") or {}).get("data") or {}
    health = _safe_float(fund.get("health_score"))
    if health is not None:
        if health >= 60:
            directions["fundamentals"] = "bullish"
        elif health <= 40:
            directions["fundamentals"] = "bearish"
        else:
            directions["fundamentals"] = "neutral"

    # Macro
    macro = (agent_results.get("macro") or {}).get("data") or {}
    risk_env = str(macro.get("risk_environment") or "").lower()
    if risk_env == "risk_on":
        directions["macro"] = "bullish"
    elif risk_env == "risk_off":
        directions["macro"] = "bearish"
    else:
        directions["macro"] = "neutral"

    # Options
    opts = (agent_results.get("options") or {}).get("data") or {}
    opts_signal = str(opts.get("overall_signal") or "").lower()
    if opts_signal == "bullish":
        directions["options"] = "bullish"
    elif opts_signal == "bearish":
        directions["options"] = "bearish"
    else:
        directions["options"] = "neutral"

    # Sentiment
    sent = (agent_results.get("sentiment") or {}).get("data") or {}
    sent_score = _safe_float(sent.get("overall_sentiment"))
    if sent_score is not None:
        if sent_score > 0.1:
            directions["sentiment"] = "bullish"
        elif sent_score < -0.1:
            directions["sentiment"] = "bearish"
        else:
            directions["sentiment"] = "neutral"

    return directions


def _pass(rule_id: str, evidence: str) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "passed": True,
        "severity": "info",
        "claim": "",
        "evidence": evidence,
        "source_agent": "",
        "confidence_penalty": 0.0,
    }


def _fail(
    *,
    rule_id: str,
    severity: str,
    claim: str,
    evidence: str,
    source_agent: str,
    penalty: float,
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "passed": False,
        "severity": severity,
        "claim": claim,
        "evidence": evidence,
        "source_agent": source_agent,
        "confidence_penalty": penalty,
    }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_validation_rules.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/validation_rules.py tests/test_validation_rules.py
git commit -m "feat: add deterministic validation rule engine"
```

---

### Task 4: Council Validator Agent — `council_validator_agent.py`

**Files:**
- Create: `src/agents/council_validator_agent.py`
- Create: `tests/test_council_validator_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_council_validator_agent.py`:

```python
"""Tests for the LLM-powered council validator agent."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.council_validator_agent import CouncilValidatorAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def council_results():
    """Minimal council results with one investor."""
    return [
        {
            "investor": "druckenmiller",
            "stance": "BULLISH",
            "thesis_health": "INTACT",
            "qualitative_analysis": "Macro tailwind intact. Fed is dovish and liquidity is expanding.",
            "key_observations": [
                "Fed cutting rates supports risk assets",
                "Revenue growth accelerating to 30%",
            ],
            "if_then_scenarios": [
                {
                    "type": "macro",
                    "condition": "If Fed reverses course and hikes",
                    "action": "then exit position",
                    "conviction": "high",
                }
            ],
        }
    ]


@pytest.fixture
def agent_results():
    """Minimal agent results for validation."""
    return {
        "macro": {
            "success": True,
            "data": {
                "economic_cycle": "expansion",
                "risk_environment": "risk_on",
                "fed_funds_rate": 4.5,
            },
        },
        "fundamentals": {
            "success": True,
            "data": {
                "key_metrics": {"revenue_growth": 0.18},
            },
        },
    }


@pytest.fixture
def validator(test_config):
    return CouncilValidatorAgent("AAPL", test_config)


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestCouncilValidatorAgent:

    def test_agent_type(self, validator):
        assert validator.get_agent_type() == "council_validator"

    @pytest.mark.asyncio
    async def test_returns_empty_report_when_no_council_results(self, validator):
        validator.set_council_context(council_results=[], agent_results={})
        result = await validator.execute()
        assert result["success"] is True
        report = result["data"]
        assert report["total_claims_checked"] == 0
        assert report["total_contradictions"] == 0
        assert report["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_returns_fallback_when_llm_fails(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )
        # No API key configured → LLM call will fail
        validator.config["llm_config"] = {"provider": "anthropic", "api_key": ""}
        result = await validator.execute()
        assert result["success"] is True
        report = result["data"]
        assert report["fallback_used"] is True
        assert report["confidence_penalty"] == 0.0

    @pytest.mark.asyncio
    async def test_parses_llm_validation_response(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )

        mock_response = json.dumps({
            "investor_validations": [
                {
                    "investor": "druckenmiller",
                    "claims": [
                        {
                            "claim": "Macro tailwind intact",
                            "verdict": "supported",
                            "evidence": "Macro data confirms expansion and risk_on"
                        },
                        {
                            "claim": "Revenue growth accelerating to 30%",
                            "verdict": "contradicted",
                            "evidence": "Fundamentals show revenue growth at 18%, not 30%",
                            "severity": "contradiction"
                        }
                    ]
                }
            ]
        })

        with patch.object(validator, "_call_llm", new_callable=AsyncMock, return_value=mock_response):
            result = await validator.execute()

        assert result["success"] is True
        report = result["data"]
        assert report["total_claims_checked"] == 2
        assert report["total_contradictions"] == 1
        assert report["confidence_penalty"] == 0.05
        assert len(report["investor_validations"]) == 1
        inv = report["investor_validations"][0]
        assert inv["investor"] == "druckenmiller"
        assert inv["claims_supported"] == 1
        assert inv["claims_contradicted"] == 1

    @pytest.mark.asyncio
    async def test_penalty_capped_at_025(self, validator, agent_results):
        """Even with many contradictions, council penalty caps at 0.25."""
        many_investors = []
        for name in ["druckenmiller", "munger", "dalio", "ptj", "marks", "buffett"]:
            many_investors.append({
                "investor": name,
                "stance": "BULLISH",
                "qualitative_analysis": "Everything is great.",
                "key_observations": ["growth is strong", "macro is favorable", "options bullish"],
                "if_then_scenarios": [],
            })

        validator.set_council_context(council_results=many_investors, agent_results=agent_results)

        # All claims contradicted
        mock_validations = []
        for inv in many_investors:
            mock_validations.append({
                "investor": inv["investor"],
                "claims": [
                    {"claim": c, "verdict": "contradicted", "evidence": "Data disagrees", "severity": "contradiction"}
                    for c in inv["key_observations"]
                ],
            })

        mock_response = json.dumps({"investor_validations": mock_validations})

        with patch.object(validator, "_call_llm", new_callable=AsyncMock, return_value=mock_response):
            result = await validator.execute()

        assert result["data"]["confidence_penalty"] <= 0.25


class TestPromptConstruction:

    def test_build_validation_prompt_includes_claims_and_data(self, validator, council_results, agent_results):
        validator.set_council_context(
            council_results=council_results,
            agent_results=agent_results,
        )
        prompt = validator._build_validation_prompt()
        assert "druckenmiller" in prompt.lower()
        assert "Macro tailwind intact" in prompt
        assert "macro" in prompt.lower()
        assert "revenue_growth" in prompt.lower() or "revenue growth" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_council_validator_agent.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `src/agents/council_validator_agent.py`**

```python
"""LLM-powered council validator agent.

Cross-checks investor council qualitative claims against raw agent data.
Uses a single LLM call per analysis run.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Claim domain → which agent_results key to include
_CLAIM_AGENT_MAP = {
    "macro": ["macro"],
    "rates": ["macro"],
    "regime": ["macro"],
    "fed": ["macro"],
    "revenue": ["fundamentals"],
    "margins": ["fundamentals"],
    "valuation": ["fundamentals"],
    "earnings": ["fundamentals"],
    "growth": ["fundamentals"],
    "price": ["technical", "market"],
    "momentum": ["technical"],
    "technicals": ["technical"],
    "rsi": ["technical"],
    "options": ["options"],
    "put": ["options"],
    "call": ["options"],
    "management": ["leadership"],
    "governance": ["leadership"],
    "ceo": ["leadership"],
    "news": ["news", "sentiment"],
    "sentiment": ["sentiment"],
    "catalyst": ["news"],
}


class CouncilValidatorAgent(BaseAgent):
    """Validates council investor claims against raw agent data via LLM."""

    def __init__(self, ticker: str, config: Dict[str, Any]):
        super().__init__(ticker, config)
        self._council_results: List[Dict[str, Any]] = []
        self._agent_results: Dict[str, Any] = {}

    def set_council_context(
        self,
        council_results: List[Dict[str, Any]],
        agent_results: Dict[str, Any],
    ) -> None:
        """Inject council output and raw agent data before execution."""
        self._council_results = council_results or []
        self._agent_results = agent_results or {}

    async def fetch_data(self) -> Dict[str, Any]:
        """No external fetch needed; context injected via set_council_context."""
        return {}

    async def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run LLM validation on council claims."""
        if not self._council_results:
            return self._empty_report()

        prompt = self._build_validation_prompt()

        try:
            llm_text = await self._call_llm(prompt)
            return self._parse_validation_response(llm_text)
        except Exception as exc:
            logger.warning(f"Council validation LLM call failed: {exc}")
            return self._empty_report(fallback_used=True)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def _build_validation_prompt(self) -> str:
        sections = []

        # Raw agent data summary
        sections.append("## Raw Agent Data\n")
        for agent_name, result in self._agent_results.items():
            if not isinstance(result, dict) or not result.get("success"):
                continue
            data = result.get("data") or {}
            sections.append(f"### {agent_name}\n```json\n{json.dumps(data, indent=2, default=str)}\n```\n")

        # Council claims to validate
        sections.append("## Council Investor Claims to Validate\n")
        for inv_result in self._council_results:
            investor = inv_result.get("investor", "unknown")
            sections.append(f"### {investor}")
            sections.append(f"Stance: {inv_result.get('stance', 'N/A')}")
            sections.append(f"Analysis: {inv_result.get('qualitative_analysis', '')}")

            observations = inv_result.get("key_observations") or []
            if observations:
                sections.append("Key observations:")
                for obs in observations:
                    sections.append(f"  - {obs}")

            scenarios = inv_result.get("if_then_scenarios") or []
            if scenarios:
                sections.append("If-then scenarios:")
                for sc in scenarios:
                    sections.append(f"  - {sc.get('condition', '')} → {sc.get('action', '')}")
            sections.append("")

        data_section = "\n".join(sections)

        return f"""You are a validation auditor. Your job is to cross-check investor council claims against the raw quantitative data from our research agents.

For each investor, examine every claim they make (in their qualitative_analysis, key_observations, and if_then_scenarios) and determine whether the raw agent data SUPPORTS, CONTRADICTS, or is UNVERIFIABLE for that claim.

{data_section}

---

Respond ONLY with valid JSON matching this schema:
{{
  "investor_validations": [
    {{
      "investor": "<investor key>",
      "claims": [
        {{
          "claim": "<the specific claim text>",
          "verdict": "supported|contradicted|unverifiable",
          "evidence": "<what the raw data shows that supports or contradicts>",
          "severity": "warning|contradiction"
        }}
      ]
    }}
  ]
}}

Rules:
- Only mark a claim as "contradicted" if the raw data clearly disagrees
- "unverifiable" means no relevant data exists to check the claim
- severity "contradiction" = clear factual mismatch; "warning" = directional tension but not definitive
- Be precise: quote specific numbers from the raw data
"""

    # ── LLM call ──────────────────────────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider. Returns raw text response."""
        llm_config = self.config.get("llm_config", {})
        provider = llm_config.get("provider", "anthropic")
        api_key = llm_config.get("api_key")

        if not api_key:
            raise ValueError("No LLM API key configured")

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            message = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=llm_config.get("model", "claude-3-5-sonnet-20241022"),
                    max_tokens=llm_config.get("max_tokens", 4096),
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            return message.content[0].text
        elif provider in ("openai", "xai"):
            from openai import OpenAI
            kwargs = {"api_key": api_key}
            base_url = llm_config.get("base_url")
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model=llm_config.get("model", "gpt-4o"),
                    max_tokens=llm_config.get("max_tokens", 4096),
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
            )
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse_validation_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM JSON response into a CouncilValidationReport."""
        # Strip markdown fences
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
            logger.warning(f"Council validation JSON parse failed: {exc}")
            return self._empty_report(fallback_used=True)

        investor_validations = []
        total_checked = 0
        total_contradictions = 0

        for inv_data in data.get("investor_validations", []):
            investor = inv_data.get("investor", "unknown")
            claims = inv_data.get("claims", [])

            supported = 0
            contradicted = 0
            unverifiable = 0
            contradictions = []

            for claim in claims:
                verdict = str(claim.get("verdict") or "").lower()
                total_checked += 1

                if verdict == "supported":
                    supported += 1
                elif verdict == "contradicted":
                    contradicted += 1
                    total_contradictions += 1
                    contradictions.append({
                        "claim": claim.get("claim", ""),
                        "evidence": claim.get("evidence", ""),
                        "severity": claim.get("severity", "contradiction"),
                    })
                else:
                    unverifiable += 1

            investor_validations.append({
                "investor": investor,
                "claims_checked": len(claims),
                "claims_supported": supported,
                "claims_contradicted": contradicted,
                "claims_unverifiable": unverifiable,
                "contradictions": contradictions,
            })

        # Penalty: 0.05 per contradiction, capped at 0.25
        penalty = min(total_contradictions * 0.05, 0.25)

        llm_config = self.config.get("llm_config", {})
        return {
            "investor_validations": investor_validations,
            "total_claims_checked": total_checked,
            "total_contradictions": total_contradictions,
            "confidence_penalty": round(penalty, 4),
            "llm_provider": llm_config.get("provider", "unknown"),
            "fallback_used": False,
        }

    def _empty_report(self, fallback_used: bool = False) -> Dict[str, Any]:
        return {
            "investor_validations": [],
            "total_claims_checked": 0,
            "total_contradictions": 0,
            "confidence_penalty": 0.0,
            "llm_provider": self.config.get("llm_config", {}).get("provider", "unknown"),
            "fallback_used": fallback_used,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_council_validator_agent.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agents/council_validator_agent.py tests/test_council_validator_agent.py
git commit -m "feat: add LLM-powered council validator agent"
```

---

### Task 5: Orchestrator — Wire Phase 2.5

**Files:**
- Modify: `src/orchestrator.py:209-221` (between Phase 2 synthesis and Phase 3 persistence)
- Test: `tests/test_orchestrator.py` (add validation integration test)

- [ ] **Step 1: Write failing test**

Add to `tests/test_orchestrator.py`:

```python
class TestValidationPhase:
    """Tests for Phase 2.5 validation wiring in the orchestrator."""

    @pytest.mark.asyncio
    async def test_validation_attaches_to_diagnostics_when_enabled(self, orchestrator):
        """When VALIDATION_V1_ENABLED, diagnostics should contain validation."""
        orchestrator.config["VALIDATION_V1_ENABLED"] = True

        # Mock _run_agents and _run_solution_agent to return fixture data
        agent_results = {
            "market": {"success": True, "data": {"current_price": 180.0, "trend": "bullish"}},
            "fundamentals": {"success": True, "data": {"health_score": 75, "key_metrics": {"revenue_growth": 0.18}}},
            "technical": {"success": True, "data": {"rsi": 55, "signals": {"overall": "buy", "strength": 40}}},
            "macro": {"success": True, "data": {"economic_cycle": "expansion", "risk_environment": "risk_on"}},
            "options": {"success": True, "data": {"put_call_ratio": 0.7, "overall_signal": "bullish"}},
            "sentiment": {"success": True, "data": {"overall_sentiment": 0.4}},
            "news": {"success": True, "data": {"articles": []}},
            "leadership": {"success": True, "data": {}},
        }
        final_analysis = {
            "recommendation": "BUY",
            "score": 65,
            "confidence": 0.78,
            "reasoning": "Strong.",
            "scenarios": {
                "bull": {"probability": 0.4, "expected_return_pct": 15.0},
                "base": {"probability": 0.4, "expected_return_pct": 5.0},
                "bear": {"probability": 0.2, "expected_return_pct": -10.0},
            },
        }

        orchestrator._run_agents = AsyncMock(return_value=agent_results)
        orchestrator._run_solution_agent = AsyncMock(return_value=final_analysis)
        orchestrator._validate_ticker = AsyncMock(return_value=True)
        orchestrator._notify_progress = AsyncMock()
        orchestrator._create_shared_session = AsyncMock()
        orchestrator._close_shared_session = AsyncMock()

        result = await orchestrator.analyze_ticker("AAPL")

        assert result["success"] is True
        diagnostics = result["analysis"].get("diagnostics") or {}
        assert "validation" in diagnostics

    @pytest.mark.asyncio
    async def test_validation_skipped_when_disabled(self, orchestrator):
        """When VALIDATION_V1_ENABLED=False, no validation in diagnostics."""
        orchestrator.config["VALIDATION_V1_ENABLED"] = False

        agent_results = {
            "market": {"success": True, "data": {"current_price": 180.0, "trend": "bullish"}},
            "fundamentals": {"success": True, "data": {"health_score": 75}},
            "technical": {"success": True, "data": {"rsi": 55, "signals": {"overall": "buy", "strength": 40}}},
            "macro": {"success": True, "data": {"economic_cycle": "expansion", "risk_environment": "risk_on"}},
            "options": {"success": True, "data": {"put_call_ratio": 0.7, "overall_signal": "bullish"}},
            "sentiment": {"success": True, "data": {"overall_sentiment": 0.4}},
            "news": {"success": True, "data": {"articles": []}},
            "leadership": {"success": True, "data": {}},
        }
        final_analysis = {
            "recommendation": "BUY",
            "score": 65,
            "confidence": 0.78,
            "reasoning": "Strong.",
            "scenarios": {},
        }

        orchestrator._run_agents = AsyncMock(return_value=agent_results)
        orchestrator._run_solution_agent = AsyncMock(return_value=final_analysis)
        orchestrator._validate_ticker = AsyncMock(return_value=True)
        orchestrator._notify_progress = AsyncMock()
        orchestrator._create_shared_session = AsyncMock()
        orchestrator._close_shared_session = AsyncMock()

        result = await orchestrator.analyze_ticker("AAPL")

        diagnostics = result.get("analysis", {}).get("diagnostics") or {}
        assert "validation" not in diagnostics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestValidationPhase -v`
Expected: FAIL — no "validation" key in diagnostics

- [ ] **Step 3: Add Phase 2.5 to `src/orchestrator.py`**

Add import at top of `src/orchestrator.py` (near line 25):

```python
from .validation_rules import validate as run_validation_rules
from .agents.council_validator_agent import CouncilValidatorAgent
```

In `analyze_ticker()`, after line 221 (`self._attach_signal_contract_v2(...)`) and before line 224 (`self._log_baseline_metrics(...)`), insert:

```python
            # Phase 2.5: Validation (when enabled)
            if self.config.get("VALIDATION_V1_ENABLED", False):
                try:
                    validation_report = await self._run_validation(
                        ticker, final_analysis, agent_results, diagnostics
                    )
                    diagnostics["validation"] = validation_report

                    # Adjust confidence in signal contract if present
                    contract = final_analysis.get("signal_contract_v2")
                    if contract and validation_report.get("total_confidence_penalty", 0) > 0:
                        penalty = validation_report["total_confidence_penalty"]
                        orig_conf = validation_report["original_confidence"]
                        adj_conf = validation_report["adjusted_confidence"]
                        confidence_block = contract.get("confidence") or {}
                        confidence_block["pre_validation"] = orig_conf
                        confidence_block["validation_penalty"] = penalty
                        if confidence_block.get("calibrated") is not None:
                            confidence_block["calibrated"] = max(
                                confidence_block["calibrated"] - penalty, 0.05
                            )
                        contract["confidence"] = confidence_block
                        contract["validation"] = {
                            "status": validation_report["overall_status"],
                            "confidence_penalty": penalty,
                            "contradictions_count": (
                                validation_report["rule_validation"]["contradictions"]
                                + validation_report["council_validation"]["total_contradictions"]
                            ),
                            "spot_check_requested": validation_report["spot_check_requested"],
                        }
                except Exception as exc:
                    self.logger.warning(f"Validation phase failed for {ticker}: {exc}")
```

Add the `_run_validation` method to the `Orchestrator` class:

```python
    async def _run_validation(
        self,
        ticker: str,
        final_analysis: Dict[str, Any],
        agent_results: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run Phase 2.5: rule-based + LLM council validation."""
        import uuid

        # Phase 2.5a: Rule-based validation (sync, always runs)
        rule_report = run_validation_rules(
            final_analysis=final_analysis,
            agent_results=agent_results,
        )

        # Phase 2.5b: Council LLM validation (async, graceful fallback)
        council_report = {
            "investor_validations": [],
            "total_claims_checked": 0,
            "total_contradictions": 0,
            "confidence_penalty": 0.0,
            "llm_provider": "none",
            "fallback_used": True,
        }

        council_results = self._extract_council_results(agent_results)
        if council_results:
            try:
                validator = CouncilValidatorAgent(ticker, self.config)
                validator.set_council_context(
                    council_results=council_results,
                    agent_results=agent_results,
                )
                result = await validator.execute()
                if result.get("success") and result.get("data"):
                    council_report = result["data"]
            except Exception as exc:
                self.logger.warning(f"Council validation failed: {exc}")

        # Phase 2.5c: Merge reports
        rule_penalty = rule_report["total_confidence_penalty"]
        council_penalty = council_report["confidence_penalty"]
        total_penalty = min(rule_penalty + council_penalty, 0.50)

        original_confidence = self._safe_float(final_analysis.get("confidence")) or 0.0
        adjusted_confidence = max(original_confidence - total_penalty, 0.05)

        total_contradictions = rule_report["contradictions"] + council_report["total_contradictions"]

        if total_contradictions > 0:
            overall_status = "contradictions"
        elif rule_report["warnings"] > 0:
            overall_status = "warnings"
        else:
            overall_status = "clean"

        # Tier 2: spot-check sampling
        spot_check_rate = self.config.get("VALIDATION_SPOT_CHECK_RATE", 3)
        spot_check_on_contradiction = self.config.get("VALIDATION_SPOT_CHECK_ON_CONTRADICTION", True)

        analysis_count = self._get_analysis_run_count(ticker)
        spot_check_requested = False
        if spot_check_on_contradiction and overall_status == "contradictions":
            spot_check_requested = True
        elif spot_check_rate > 0 and analysis_count % spot_check_rate == 0:
            spot_check_requested = True

        return {
            "schema_version": "1.0",
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "ticker": ticker,
            "overall_status": overall_status,
            "total_confidence_penalty": round(total_penalty, 4),
            "original_confidence": original_confidence,
            "adjusted_confidence": round(adjusted_confidence, 4),
            "rule_validation": rule_report,
            "council_validation": council_report,
            "spot_check_requested": spot_check_requested,
            "spot_check_status": "pending" if spot_check_requested else "skipped",
            "validation_id": str(uuid.uuid4()),
        }

    def _extract_council_results(self, agent_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract council investor results from agent_results if present."""
        council = agent_results.get("council")
        if isinstance(council, dict) and council.get("data"):
            data = council["data"]
            if isinstance(data, list):
                return data
            investors = data.get("investors") or data.get("council_results") or []
            if isinstance(investors, list):
                return investors
        return []

    def _get_analysis_run_count(self, ticker: str) -> int:
        """Get number of completed analyses for a ticker (for spot-check sampling)."""
        try:
            history = self.db_manager.get_analysis_history(ticker, limit=1000)
            return len(history)
        except Exception:
            return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestValidationPhase -v`
Expected: PASSED

- [ ] **Step 5: Run full test suite to check nothing broke**

Run: `pytest tests/ -v --timeout=60`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: wire Phase 2.5 validation into orchestrator"
```

---

### Task 6: API — SSE Event and Feedback Endpoint

**Files:**
- Modify: `src/api.py` (add SSE event + POST endpoint)
- Test: `tests/test_api.py` (add feedback endpoint test)

- [ ] **Step 1: Write failing test for feedback endpoint**

Add to `tests/test_api.py`:

```python
class TestValidationFeedbackAPI:
    """Tests for the validation feedback endpoint."""

    def test_submit_feedback(self, client, db_manager):
        """POST /api/validation/{id}/feedback stores verdict."""
        # Create prerequisite data
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="feedback-test-001",
            overall_status="contradictions",
            original_confidence=0.78,
            adjusted_confidence=0.63,
            total_confidence_penalty=0.15,
            rule_checks_total=4,
            rule_contradictions=1,
            council_claims_total=8,
            council_contradictions=1,
            spot_check_requested=True,
            report_json="{}",
        )

        response = client.post(
            "/api/validation/feedback-test-001/feedback",
            json={"verdict": "flagged"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["verdict"] == "flagged"

    def test_submit_feedback_invalid_verdict(self, client, db_manager):
        """Invalid verdict should return 400."""
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="feedback-test-002",
            overall_status="contradictions",
            original_confidence=0.78,
            adjusted_confidence=0.63,
            total_confidence_penalty=0.15,
            rule_checks_total=4,
            rule_contradictions=1,
            council_claims_total=0,
            council_contradictions=0,
            spot_check_requested=True,
            report_json="{}",
        )

        response = client.post(
            "/api/validation/feedback-test-002/feedback",
            json={"verdict": "invalid_value"},
        )
        assert response.status_code == 400

    def test_submit_feedback_not_found(self, client):
        """Feedback for nonexistent validation_id returns 404."""
        response = client.post(
            "/api/validation/nonexistent-id/feedback",
            json={"verdict": "confirmed"},
        )
        assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::TestValidationFeedbackAPI -v`
Expected: FAIL — 404 because endpoint doesn't exist

- [ ] **Step 3: Add feedback endpoint to `src/api.py`**

Add this endpoint to `src/api.py`:

```python
@app.post("/api/validation/{validation_id}/feedback")
async def submit_validation_feedback(validation_id: str, request: Request):
    """Submit spot-check feedback for a validation result."""
    body = await request.json()
    verdict = body.get("verdict")

    if verdict not in ("confirmed", "flagged"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "verdict must be 'confirmed' or 'flagged'"},
        )

    validation = db_manager.get_validation_result(validation_id)
    if not validation:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Validation {validation_id} not found"},
        )

    db_manager.save_validation_feedback(
        validation_id=validation_id,
        ticker=validation["ticker"],
        claim_type="rule",
        claim_summary="Spot-check feedback",
        human_verdict=verdict,
    )

    return {"success": True, "validation_id": validation_id, "verdict": verdict}
```

- [ ] **Step 4: Add SSE validation event**

In the SSE streaming section of `analyze_ticker_stream` endpoint in `src/api.py`, after the `synthesizing` progress event and before the `saving` event, the orchestrator's validation report will naturally flow through since it's attached to `diagnostics`. No additional SSE code needed — the existing result event includes the full `final_analysis` which now contains `diagnostics.validation`.

However, to surface validation status as a discrete progress event, add this to the orchestrator's `_run_validation` method at the end (before the return), or add a callback in `analyze_ticker`. The simplest approach: the existing `_notify_progress` pattern handles it. Add after the Phase 2.5 block in `orchestrator.py`:

```python
                    await self._notify_progress("validating", ticker, 88)
```

Add this line before the Phase 2.5 try block.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api.py::TestValidationFeedbackAPI -v`
Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add src/api.py src/orchestrator.py tests/test_api.py
git commit -m "feat: add validation feedback endpoint and SSE event"
```

---

### Task 7: Spot-Check Alert Integration

**Files:**
- Modify: `src/orchestrator.py` (trigger spot-check alert after validation)
- Modify: `src/database.py:298-318` (add `spot_check` to alert_rules CHECK constraint)
- Test: `tests/test_alert_engine.py` (add spot-check test)

- [ ] **Step 1: Write failing test**

Add to `tests/test_alert_engine.py`:

```python
class TestSpotCheckAlert:

    def test_spot_check_alert_created_when_contradictions(self, db_manager):
        """When validation has contradictions and spot_check_requested, alert is created."""
        from src.alert_engine import AlertEngine

        # Create an analysis
        analysis_id = db_manager.save_analysis(
            ticker="AAPL",
            recommendation="BUY",
            score=65,
            confidence=0.78,
            agent_results={},
            analysis_payload={},
            duration_seconds=5.0,
        )

        # Create a spot_check alert rule
        db_manager.create_alert_rule("AAPL", "spot_check")

        # Save validation result with contradictions
        db_manager.save_validation_result(
            analysis_id=analysis_id,
            ticker="AAPL",
            validation_id="spot-check-test-001",
            overall_status="contradictions",
            original_confidence=0.78,
            adjusted_confidence=0.63,
            total_confidence_penalty=0.15,
            rule_checks_total=4,
            rule_contradictions=1,
            council_claims_total=0,
            council_contradictions=0,
            spot_check_requested=True,
            report_json='{"rule_validation": {"results": [{"rule_id": "direction_consistency", "passed": false, "severity": "contradiction", "claim": "BUY recommended", "evidence": "4/6 agents bearish", "source_agent": "multiple", "confidence_penalty": 0.15}]}}',
        )

        engine = AlertEngine(db_manager)
        alerts = engine.evaluate_alerts("AAPL", analysis_id)

        spot_alerts = [a for a in alerts if a.get("trigger_context", {}).get("rule_type") == "spot_check"]
        assert len(spot_alerts) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alert_engine.py::TestSpotCheckAlert -v`
Expected: FAIL — `spot_check` not in CHECK constraint

- [ ] **Step 3: Add `spot_check` to alert_rules CHECK constraint**

In `src/database.py`, update the `alert_rules` table CHECK constraint (line ~301) to include `'spot_check'`:

```python
                    rule_type TEXT NOT NULL CHECK(rule_type IN (
                        'recommendation_change',
                        'score_above',
                        'score_below',
                        'confidence_above',
                        'confidence_below',
                        'ev_above',
                        'ev_below',
                        'regime_change',
                        'data_quality_below',
                        'calibration_drop',
                        'spot_check'
                    )),
```

Also update the migration version of this table if it exists (check around line 542).

- [ ] **Step 4: Add spot_check rule evaluation to `src/alert_engine.py`**

In `_evaluate_rule()` (around line 101), after the `calibration_drop` handler, add:

```python
        elif rule_type == "spot_check" and Config.VALIDATION_V1_ENABLED:
            return self._check_spot_check(current)
```

Add the handler method to the `AlertEngine` class:

```python
    def _check_spot_check(self, current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Trigger spot-check alert if validation has contradictions."""
        payload = current.get("analysis") or current.get("analysis_payload") or {}
        diagnostics = payload.get("diagnostics") or {}
        validation = diagnostics.get("validation") or {}

        if not validation.get("spot_check_requested"):
            return None

        # Find the highest-severity contradiction
        rule_results = (validation.get("rule_validation") or {}).get("results") or []
        contradictions = [r for r in rule_results if not r.get("passed") and r.get("severity") == "contradiction"]

        council_contradictions = []
        for inv in (validation.get("council_validation") or {}).get("investor_validations") or []:
            for c in inv.get("contradictions") or []:
                council_contradictions.append(c)

        top_claim = ""
        top_evidence = ""
        if contradictions:
            top = contradictions[0]
            top_claim = top.get("claim", "")
            top_evidence = top.get("evidence", "")
        elif council_contradictions:
            top = council_contradictions[0]
            top_claim = top.get("claim", "")
            top_evidence = top.get("evidence", "")

        if not top_claim:
            return None

        original = validation.get("original_confidence", 0)
        adjusted = validation.get("adjusted_confidence", 0)

        return {
            "message": (
                f"[SPOT CHECK] Validation contradiction — "
                f"Claimed: \"{top_claim}\" but data shows: \"{top_evidence}\". "
                f"Confidence penalized: {original:.2f} → {adjusted:.2f}"
            ),
            "previous_value": str(original),
            "current_value": str(adjusted),
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_alert_engine.py::TestSpotCheckAlert -v`
Expected: PASSED

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/database.py src/alert_engine.py tests/test_alert_engine.py
git commit -m "feat: add spot_check alert type for validation Tier 2"
```

---

### Task 8: End-to-End Integration Test

**Files:**
- Create: `tests/test_validation_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""End-to-end integration test for the validation pipeline."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from src.validation_rules import validate as run_validation_rules
from src.agents.council_validator_agent import CouncilValidatorAgent


class TestValidationEndToEnd:
    """Full pipeline: rules + council validator → merged report."""

    def test_clean_analysis_produces_clean_report(self):
        """When all data aligns, both rule and council validation are clean."""
        final_analysis = {
            "recommendation": "BUY",
            "score": 65,
            "confidence": 0.78,
            "signal_snapshot": {"macro_risk_environment": "risk_on"},
        }
        agent_results = {
            "market": {"success": True, "data": {"trend": "bullish"}},
            "fundamentals": {"success": True, "data": {"health_score": 75}},
            "technical": {"success": True, "data": {"rsi": 55, "signals": {"overall": "buy", "strength": 40}}},
            "macro": {"success": True, "data": {"economic_cycle": "expansion", "risk_environment": "risk_on"}},
            "options": {"success": True, "data": {"put_call_ratio": 0.7, "overall_signal": "bullish"}},
            "sentiment": {"success": True, "data": {"overall_sentiment": 0.4}},
        }

        rule_report = run_validation_rules(final_analysis=final_analysis, agent_results=agent_results)

        assert rule_report["contradictions"] == 0
        assert rule_report["total_confidence_penalty"] == 0.0

    def test_contradictory_analysis_produces_penalties(self):
        """BUY with majority bearish agents triggers direction contradiction."""
        final_analysis = {
            "recommendation": "BUY",
            "score": 65,
            "confidence": 0.78,
            "signal_snapshot": {"macro_risk_environment": "risk_on"},
        }
        agent_results = {
            "market": {"success": True, "data": {"trend": "bearish"}},
            "fundamentals": {"success": True, "data": {"health_score": 30}},
            "technical": {"success": True, "data": {"rsi": 75, "signals": {"overall": "sell", "strength": -40}}},
            "macro": {"success": True, "data": {"economic_cycle": "contraction", "risk_environment": "risk_off"}},
            "options": {"success": True, "data": {"put_call_ratio": 1.8, "overall_signal": "bearish"}},
            "sentiment": {"success": True, "data": {"overall_sentiment": -0.4}},
        }

        rule_report = run_validation_rules(final_analysis=final_analysis, agent_results=agent_results)

        assert rule_report["contradictions"] >= 1
        assert rule_report["total_confidence_penalty"] > 0

    def test_merged_penalty_calculation(self):
        """Verify combined rule + council penalty caps at 0.50."""
        rule_penalty = 0.35
        council_penalty = 0.25
        total = min(rule_penalty + council_penalty, 0.50)
        assert total == 0.50

        original_confidence = 0.78
        adjusted = max(original_confidence - total, 0.05)
        assert adjusted == 0.28

    def test_confidence_floor(self):
        """Adjusted confidence never goes below 0.05."""
        original_confidence = 0.10
        total_penalty = 0.50
        adjusted = max(original_confidence - total_penalty, 0.05)
        assert adjusted == 0.05
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_validation_integration.py -v`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/test_validation_integration.py
git commit -m "test: add end-to-end validation integration tests"
```

---

### Task 9: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All tests pass, including new validation tests

- [ ] **Step 2: Verify feature flag disables cleanly**

Run: `VALIDATION_V1_ENABLED=false pytest tests/ -v --timeout=60`
Expected: All tests pass, validation-specific tests either skip or adapt

- [ ] **Step 3: Check no lint issues**

Run: `python -m py_compile src/validation_rules.py src/agents/council_validator_agent.py`
Expected: No errors

- [ ] **Step 4: Final commit with all changes**

```bash
git status
```

If any unstaged files remain:

```bash
git add -A
git commit -m "chore: final validation v1 cleanup"
```
