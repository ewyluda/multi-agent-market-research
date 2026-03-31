# Thesis Health Monitor + Synthesis View — Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Phases:** Investor Council Phase 3 (Thesis Health Monitor) + Phase 4 (Synthesis View)

---

## Problem

The investor council produces per-investor stances, thesis health assessments, and if-then scenarios — but nothing tracks thesis health over time or synthesizes the council's collective output into a unified actionable view. Health indicators on thesis cards have `baseline_value` and `current_value` fields that are never populated. The user must manually scan N investor cards to extract the "so what."

## Solution

Two features wired into existing infrastructure:

1. **Thesis Health Monitor (Phase 3)** — runs during every standard analysis for tickers with thesis cards. Compares fresh agent data against auto-snapshotted baselines. Produces a `ThesisHealthReport`. Fires `thesis_health_change` alerts on degradation.

2. **Synthesis View (Phase 4)** — runs after every council convene. Two tiers: deterministic consensus aggregation (always) + optional LLM narrative (one extra call). Rendered at the top of the Council tab.

---

## Architecture

### Execution Flow

```
Standard Analysis Run (existing)
  └─ Phase 2.6: Thesis Health Check (new, after Phase 2.5 validation)
       ├─ Load thesis card + health indicators for ticker
       ├─ Snapshot current values from fresh agent data
       ├─ Compare against baselines → compute drift
       ├─ Determine health status per indicator
       ├─ Produce ThesisHealthReport
       ├─ Auto-snapshot baselines where missing → write back to thesis card
       ├─ Save to thesis_health_snapshots table
       └─ Attach to final_analysis["thesis_health"]

Council Convene (existing POST /api/analyze/{ticker}/council)
  └─ After investor agents complete:
       ├─ Tier 1: Deterministic consensus — always runs, no LLM
       ├─ Tier 2: LLM synthesis narrative — optional, one call, graceful fallback
       └─ Return CouncilSynthesis in response + persist to DB
```

### Module Structure

```
src/
├── thesis_health.py                    # Pure functions, drift detection, health rollup
├── council_synthesis.py                # Pure functions, deterministic consensus aggregation
├── agents/
│   └── council_synthesis_agent.py      # LLM-powered synthesis narrative
```

---

## Module 1: Thesis Health Monitor (`thesis_health.py`)

Pure functions. No classes, no state, no LLM calls. Same pattern as `validation_rules.py`.

### Health Indicator → Agent Data Mapping

Each health indicator has a `proxy_signal` field. The monitor maps these to agent result paths:

| proxy_signal pattern | Source path |
|---|---|
| `price`, `current_price` | `agent_results["market"]["data"]["current_price"]` |
| `rsi` | `agent_results["technical"]["data"]["rsi"]` |
| `macd`, `signal_strength` | `agent_results["technical"]["data"]["signals"]["strength"]` |
| `revenue_growth`, `margins`, `health_score` | `agent_results["fundamentals"]["data"][key]` |
| `put_call_ratio` | `agent_results["options"]["data"]["put_call_ratio"]` |
| `overall_sentiment` | `agent_results["sentiment"]["data"]["overall_sentiment"]` |
| `risk_environment` | `agent_results["macro"]["data"]["risk_environment"]` |
| `yield_curve`, `yield_curve_slope` | `agent_results["macro"]["data"]["yield_curve_slope"]` |

Mapping function: `resolve_indicator_value(proxy_signal, agent_results) -> Optional[str]`

Unknown proxy_signals return None and the indicator is skipped (not an error).

### Baseline Auto-Snapshot

When a thesis card has a health indicator with `baseline_value == None`, the monitor:
1. Resolves the current value from agent data
2. Writes it as `baseline_value` on the thesis card via `db_manager.upsert_thesis_card()`
3. Counts as `baselines_updated` in the report

This runs once per indicator — subsequent runs compare against the stored baseline.

### Drift Detection

For numeric indicators, compute relative change: `drift_pct = abs(current - baseline) / abs(baseline) * 100`

For string indicators (e.g., `risk_environment`), compare equality: changed = `breached`, unchanged = `stable`.

| Condition | Status |
|---|---|
| Numeric within 10% of baseline | `stable` |
| Numeric 10–25% drift | `drifting` |
| Numeric >25% drift | `breached` |
| String unchanged | `stable` |
| String changed | `breached` |

### Aggregate Health

Roll up individual indicator statuses:

| Condition | Overall Health |
|---|---|
| All stable | `INTACT` |
| Any drifting, none breached | `WATCHING` |
| 1 breached | `DETERIORATING` |
| 2+ breached OR load-bearing assumption indicator breached | `BROKEN` |

The load-bearing assumption indicator is identified by checking if any indicator's `name` matches (case-insensitive contains) the thesis card's `load_bearing_assumption` field.

### Output

```python
ThesisHealthReport = {
    "ticker": str,
    "overall_health": "INTACT|WATCHING|DETERIORATING|BROKEN",
    "previous_health": str | None,   # From last snapshot, for change detection
    "health_changed": bool,
    "indicators": [
        {
            "name": str,
            "proxy_signal": str,
            "baseline_value": str,
            "current_value": str,
            "drift_pct": float | None,  # None for string indicators
            "status": "stable|drifting|breached",
        }
    ],
    "baselines_updated": int,         # Count of newly auto-snapshotted baselines
}
```

### Public API

```python
def evaluate_thesis_health(
    *,
    thesis_card: Dict[str, Any],
    agent_results: Dict[str, Any],
    previous_health: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate thesis health for a ticker. Returns ThesisHealthReport."""
```

---

## Module 2: Synthesis View

### Tier 1: Deterministic Consensus (`council_synthesis.py`)

Pure functions. No LLM. Aggregates council results into structured summary.

```python
def build_consensus(council_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build deterministic consensus from council investor results."""
```

#### Output

```python
CouncilConsensus = {
    "stance_distribution": {
        "bullish": int,
        "cautious": int,
        "bearish": int,
        "pass": int,
    },
    "majority_stance": str,           # Plurality winner
    "conviction_strength": float,     # 0.0–1.0, fraction aligned with majority
    "thesis_health_consensus": str,   # Mode of investor thesis_health values
    "disagreements": [
        {
            "investor": str,
            "investor_name": str,
            "flag": str,
        }
    ],
    "top_scenarios": [                # Top 3 if-then scenarios, high conviction first
        {
            "investor": str,
            "type": str,
            "condition": str,
            "action": str,
            "conviction": str,
        }
    ],
}
```

#### Logic

- `majority_stance`: count stances, pick plurality. Ties broken by: bullish > cautious > bearish > pass.
- `conviction_strength`: count of majority stance / total investors (excluding PASS).
- `thesis_health_consensus`: mode of thesis_health values across investors. UNKNOWN excluded from mode calculation.
- `disagreements`: all investors where `disagreement_flag` is non-empty.
- `top_scenarios`: collect all if-then scenarios, sort by conviction (high > medium > low), take top 3. Deduplicate by condition text similarity (exact match after lowercasing).

### Tier 2: LLM Synthesis Narrative (`council_synthesis_agent.py`)

Inherits `BaseAgent`. Single LLM call. Same provider cascade as other agents (Claude → OpenAI → xAI).

#### Process

1. Build prompt with: council results summary, thesis health report (if available), signal contract v2 summary, validation report summary
2. Single LLM call requesting structured JSON
3. Parse response
4. Graceful fallback on failure

#### Output

```python
SynthesisNarrative = {
    "narrative": str,                # ~200 word unified interpretation
    "position_implication": str,     # One-line: "Hold with tighter stop" / "Add on weakness"
    "watch_item": str,               # Single most important thing to monitor
    "llm_provider": str,
    "fallback_used": bool,
}
```

#### Graceful Degradation

If all LLM providers fail, returns empty narrative with `fallback_used: True`. The deterministic consensus (Tier 1) always renders. The system never blocks on LLM availability.

### Combined Output

```python
CouncilSynthesis = {
    "consensus": CouncilConsensus,    # Tier 1 — always present
    "narrative": SynthesisNarrative,  # Tier 2 — may be empty on fallback
}
```

---

## Database Schema

### New Table: `thesis_health_snapshots`

```sql
CREATE TABLE thesis_health_snapshots (
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
);

CREATE INDEX idx_thesis_health_ticker ON thesis_health_snapshots(ticker, created_at DESC);
CREATE INDEX idx_thesis_health_analysis ON thesis_health_snapshots(analysis_id);
```

### New Table: `council_synthesis`

```sql
CREATE TABLE council_synthesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    analysis_id INTEGER,
    consensus_json TEXT NOT NULL,
    narrative_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE INDEX idx_council_synthesis_ticker ON council_synthesis(ticker, created_at DESC);
```

---

## Orchestrator Integration (Phase 2.6)

In `analyze_ticker()`, after Phase 2.5 (validation) and before `_log_baseline_metrics()`:

```python
# Phase 2.6: Thesis Health Check
thesis_health_report = None
if self.config.get("THESIS_HEALTH_ENABLED", True):
    thesis_card = self.db_manager.get_thesis_card(ticker)
    if thesis_card and thesis_card.get("health_indicators"):
        try:
            previous_snapshot = self.db_manager.get_latest_thesis_health(ticker)
            previous_health = previous_snapshot.get("overall_health") if previous_snapshot else None

            thesis_health_report = evaluate_thesis_health(
                thesis_card=thesis_card,
                agent_results=agent_results,
                previous_health=previous_health,
            )

            # Auto-snapshot baselines — write resolved values back to thesis card
            if thesis_health_report.get("baselines_updated", 0) > 0:
                for ind in thesis_health_report["indicators"]:
                    for tc_ind in thesis_card.get("health_indicators", []):
                        if tc_ind["proxy_signal"] == ind["proxy_signal"] and not tc_ind.get("baseline_value"):
                            tc_ind["baseline_value"] = ind["current_value"]
                self.db_manager.upsert_thesis_card(ticker, thesis_card)

            final_analysis["thesis_health"] = thesis_health_report
        except Exception as exc:
            self.logger.warning(f"Thesis health check failed (non-blocking): {exc}")
```

After persistence (when `analysis_id` is available), save the snapshot to DB.

## Council API Integration

In the existing `POST /api/analyze/{ticker}/council` handler, after all investor agents complete:

```python
# Build synthesis
from src.council_synthesis import build_consensus

consensus = build_consensus(investor_results)

# Optional LLM narrative
narrative = {"narrative": "", "position_implication": "", "watch_item": "", "fallback_used": True}
try:
    synth_agent = CouncilSynthesisAgent(ticker, config)
    synth_agent.set_synthesis_context(
        council_results=investor_results,
        thesis_health=thesis_health_report,
        signal_contract=final_analysis.get("signal_contract_v2"),
        validation=final_analysis.get("validation"),
    )
    synth_result = await asyncio.wait_for(synth_agent.execute(), timeout=timeout)
    if synth_result.get("success") and synth_result.get("data"):
        narrative = synth_result["data"]
except Exception:
    pass  # Graceful fallback — consensus still returned

synthesis = {"consensus": consensus, "narrative": narrative}

# Persist
db_manager.save_council_synthesis(ticker, analysis_id, synthesis)

# Attach to response
response["synthesis"] = synthesis
```

---

## Alert Type: `thesis_health_change`

Added to alert_rules CHECK constraint alongside `spot_check`.

### Dispatch in AlertEngine

```python
elif rule_type == "thesis_health_change":
    return self._check_thesis_health_change(current, previous)
```

### Check Logic

Fires when `final_analysis["thesis_health"]["health_changed"]` is True and overall health degraded (not improved). Degradation order: INTACT > WATCHING > DETERIORATING > BROKEN.

### Alert Format

```
[THESIS HEALTH] NVDA — INTACT → WATCHING
revenue_growth drifted 18% from baseline (32% → 26%)
signal_strength drifted 22% from baseline (45 → 35)
```

---

## Frontend Changes

### Council Tab Layout (after council run, top to bottom)

1. **SynthesisCard** (new component within CouncilPanel.jsx)
   - Stance distribution as horizontal bar (green/amber/red segments) with counts
   - Majority stance badge + conviction strength percentage
   - Thesis health status badge (from `analysis.thesis_health` or council consensus)
   - Disagreement callouts (if any flagged)
   - Top 3 if-then scenarios in compact format
   - LLM narrative paragraph (if available), styled like ResearchContent
   - `position_implication` highlighted one-liner
   - `watch_item` subtle callout

2. **HealthIndicatorStrip** (new component within CouncilPanel.jsx)
   - Compact horizontal row of pills below synthesis card
   - One pill per indicator: name + current value + status dot (green=stable, amber=drifting, red=breached)
   - Only renders when ticker has thesis card with health indicators
   - Click to expand: baseline value, drift %, trend direction

3. **Existing content** (unchanged)
   - Thesis card form (collapsible)
   - Individual investor cards grid
   - Playbook section
   - Disagreement banner

No new tabs. No changes to other components.

---

## Feature Flags

```python
THESIS_HEALTH_ENABLED = os.getenv("THESIS_HEALTH_ENABLED", "true").lower() == "true"
```

When disabled, Phase 2.6 is skipped. LLM synthesis is opt-in by nature (only runs during council convene).

---

## Files Changed

| File | Change |
|---|---|
| `src/thesis_health.py` | **New** — health indicator mapping, drift detection, aggregate health |
| `src/council_synthesis.py` | **New** — deterministic consensus builder |
| `src/agents/council_synthesis_agent.py` | **New** — LLM synthesis narrative agent |
| `src/orchestrator.py` | **Modified** — Phase 2.6 thesis health check wiring |
| `src/database.py` | **Modified** — thesis_health_snapshots + council_synthesis tables, CRUD methods |
| `src/alert_engine.py` | **Modified** — thesis_health_change rule type |
| `src/api.py` | **Modified** — attach synthesis to council response |
| `src/config.py` | **Modified** — THESIS_HEALTH_ENABLED flag |
| `frontend/src/components/CouncilPanel.jsx` | **Modified** — SynthesisCard + HealthIndicatorStrip components |

---

## Testing Strategy

- **thesis_health.py** — Unit tests with fixture agent_results and thesis cards. Test each drift category, aggregate rollup, baseline auto-snapshot, load-bearing assumption detection, string vs numeric indicators.
- **council_synthesis.py** — Unit tests for consensus building. Test stance distribution, majority calculation, tie-breaking, disagreement extraction, scenario deduplication and ranking.
- **council_synthesis_agent.py** — Unit tests with mocked LLM responses. Test prompt construction, response parsing, graceful degradation.
- **Orchestrator Phase 2.6** — Test wiring with thesis card present/absent, baseline snapshot write-back, DB persistence.
- **Alert engine** — Test thesis_health_change fires on degradation, silent on improvement or no change.
- **API** — Test synthesis attached to council response. Test with/without LLM narrative.
- **Frontend** — Manual verification: SynthesisCard renders with consensus data, HealthIndicatorStrip shows indicator pills, both degrade gracefully when data is missing.
