# Two-Tier Validation Agent — Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Source:** [AI Exoskeleton Hypothesis](../../../01_Projects/Multi-Agent-Market-Research/Research/) framework

---

## Problem

The multi-agent pipeline produces claims at two levels — the solution agent synthesizes raw data into recommendations, and the investor council interprets data through qualitative frameworks. Neither layer is validated against the underlying data. LLM hallucination during synthesis or council analysis can produce recommendations backed by claims that contradict the raw agent outputs.

The exoskeleton principle says AI wraps Eric's judgment. If the AI layer introduces contradictions between its claims and its own data, the exoskeleton is unreliable.

## Solution

A two-tier validation system:

- **Tier 1:** Automated cross-validation of claims against raw agent data, split into a deterministic rule engine (data-to-synthesis) and an LLM-powered validator (council-to-data)
- **Tier 2:** Human spot-checks on a configurable sample of runs, surfaced through the existing alert pipeline

Contradictions penalize confidence scores rather than blocking recommendations. Eric always sees the final output — validation informs, it doesn't gate.

---

## Architecture

### Module Structure

```
src/
├── validation_rules.py              # Pure functions, deterministic claim checks
├── agents/
│   └── council_validator_agent.py   # LLM-powered council qualitative validation
```

### Execution Flow (Phase 2.5 in Orchestrator)

```
Phase 2: SolutionAgent → final_analysis
    │
Phase 2.5a: validation_rules.validate(final_analysis, agent_results)
    │         → RuleValidationReport (sync, deterministic, always runs)
    │
Phase 2.5b: CouncilValidatorAgent.execute(council_results, agent_results)
    │         → CouncilValidationReport (async, LLM call, graceful fallback)
    │
Phase 2.5c: Merge reports → ValidationReport
    │         → Adjust confidence based on contradiction count/severity
    │         → Attach to signal_contract_v2["validation"]
    │         → Optionally trigger Tier 2 spot-check alert
    │
Phase 3: Diagnostics, persistence, SSE streaming (existing)
```

If the LLM is unavailable, Phase 2.5b returns an empty report and the system proceeds with rule-based validation only.

---

## Module 1: Rule Engine (`validation_rules.py`)

Pure functions. No classes, no state, no LLM calls. Each rule checks one specific claim type against raw agent data.

### Rule Categories

| Category | What it checks | Example |
|---|---|---|
| Direction consistency | Solution's recommendation direction vs. agent signal directions | Solution says BUY but 4/6 agents signal bearish |
| Numeric claim accuracy | Structured fields in final_analysis (score, price targets, scenario probabilities) vs. raw agent metrics | Entry price target $50 but fundamentals show fair value estimate of $35 |
| Regime consistency | Macro regime label in signal contract vs. macro agent output | Contract says "risk_on" but macro agent shows yield curve inverting |
| Technical alignment | Price targets vs. technical levels | Entry zone above all resistance levels with RSI > 70 |
| Options alignment | Options signal vs. recommendation direction | BUY recommendation but put/call ratio > 1.5 with unusual put volume |

### Output Per Rule

```python
RuleResult = {
    "rule_id": str,              # e.g. "direction_consistency"
    "passed": bool,
    "severity": "info|warning|contradiction",
    "claim": str,                # What the synthesis claimed
    "evidence": str,             # What the raw data shows
    "source_agent": str,         # Which agent's data was checked
    "confidence_penalty": float  # 0.0 to 0.15 per contradiction
}
```

### Aggregate Output

```python
RuleValidationReport = {
    "total_rules_checked": int,
    "passed": int,
    "warnings": int,
    "contradictions": int,
    "results": List[RuleResult],
    "total_confidence_penalty": float  # Sum of individual penalties, capped at 0.40
}
```

### Severity Weights

| Severity | Penalty | Trigger |
|---|---|---|
| `info` | 0.00 | Minor rounding differences, non-material discrepancies |
| `warning` | 0.05 | Directional mismatch in one non-critical factor |
| `contradiction` | 0.10–0.15 | Solution claims growth accelerating, data shows deceleration |

---

## Module 2: Council Validator Agent (`council_validator_agent.py`)

Inherits `BaseAgent`. Single LLM call per analysis run. Uses the same provider cascade as `sentiment_agent.py` (Claude → OpenAI → xAI).

### Process

1. **Extract claims** — Parse each council investor's `qualitative_analysis`, `key_observations`, and `if_then_scenarios` into discrete checkable statements
2. **Build verification prompt** — Pair each claim with relevant raw agent data using the claim-to-agent mapping
3. **Single LLM call** — One structured prompt with all claim-data pairs, up to 200K token context. Requests per-claim validation assessment.
4. **Parse response** — Extract per-claim verdicts with supporting evidence

### Claim-to-Agent Mapping

| Claim domain | Validated against |
|---|---|
| Macro / rates / regime | `agent_results["macro"]` |
| Revenue / margins / valuation | `agent_results["fundamentals"]` |
| Price action / momentum / technicals | `agent_results["technical"]` |
| Options flow / positioning | `agent_results["options"]` |
| Management / governance / leadership | `agent_results["leadership"]` |
| News / catalysts / sentiment | `agent_results["news"]` + `agent_results["sentiment"]` |

### Output

```python
CouncilValidationReport = {
    "investor_validations": [
        {
            "investor": str,             # e.g. "druckenmiller"
            "claims_checked": int,
            "claims_supported": int,
            "claims_contradicted": int,
            "claims_unverifiable": int,  # No matching data to check against
            "contradictions": [
                {
                    "claim": str,        # What the investor claimed
                    "evidence": str,     # What the raw data shows
                    "severity": "warning|contradiction"
                }
            ]
        }
    ],
    "total_claims_checked": int,
    "total_contradictions": int,
    "confidence_penalty": float,  # 0.05 per council contradiction, capped at 0.25
    "llm_provider": str,
    "fallback_used": bool
}
```

### Council Severity Weights

| Severity | Penalty |
|---|---|
| `warning` | 0.03 |
| `contradiction` | 0.05 |

### Graceful Degradation

If all LLM providers fail, returns an empty report with `fallback_used: True` and zero penalty. Rule-based validation still applies. The system never blocks on LLM availability.

---

## Confidence Penalty Model

```python
# Rule-based penalties (data-to-synthesis)
rule_penalty = sum(r["confidence_penalty"] for r in rule_results if not r["passed"])
rule_penalty = min(rule_penalty, 0.40)

# Council penalties (council-to-data)
council_penalty = council_report["confidence_penalty"]  # Already capped at 0.25

# Combined — capped at 0.50 total
total_penalty = min(rule_penalty + council_penalty, 0.50)

# Applied to signal contract
adjusted_confidence = max(confidence_raw - total_penalty, 0.05)  # Floor at 5%
```

The 0.50 cap prevents validation from zeroing out confidence. The 0.05 floor ensures every analysis retains a baseline for Eric to evaluate. Penalty weights are initial values — calibrated over time via Tier 2 feedback.

---

## Merged Validation Report

```python
ValidationReport = {
    "schema_version": "1.0",
    "timestamp": str,
    "ticker": str,

    # Summary
    "overall_status": "clean|warnings|contradictions",
    "total_confidence_penalty": float,
    "original_confidence": float,
    "adjusted_confidence": float,

    # Tier 1a — Rule-based
    "rule_validation": RuleValidationReport,

    # Tier 1b — Council LLM-based
    "council_validation": CouncilValidationReport,

    # Tier 2 — Spot-check
    "spot_check_requested": bool,
    "spot_check_status": "pending|confirmed|flagged|skipped",

    # For calibration tracking
    "validation_id": str  # UUID, links to spot-check feedback
}
```

### Attachment Points

```python
# Signal contract v2:
signal_contract_v2["validation"] = {
    "status": "clean|warnings|contradictions",
    "confidence_penalty": float,
    "contradictions_count": int,
    "spot_check_requested": bool
}

# Diagnostics (extends existing):
diagnostics["validation"] = validation_report  # Full report
```

---

## Tier 2: Spot-Check via Alert Pipeline

### Sampling Configuration

```python
# In config.py
VALIDATION_SPOT_CHECK_RATE = 3              # 1-in-N runs trigger a spot-check
VALIDATION_SPOT_CHECK_ON_CONTRADICTION = True  # Always spot-check if contradictions found
```

### Triggers

1. **Random sampling** — every Nth analysis run, regardless of validation outcome
2. **Contradiction-triggered** — always request spot-check when `overall_status == "contradictions"`

### Alert Format

Picks the single highest-severity contradiction and formats as an alert:

```
[SPOT CHECK] HOOD — Council validation contradiction

Druckenmiller claimed: "macro tailwind intact for risk assets"
Macro agent data: yield curve -0.3%, unemployment 4.1→4.3%, Fed signaling pause

Confidence was penalized: 0.82 → 0.72

→ Confirm (claim is actually reasonable given context)
→ Flag (contradiction is real, penalty justified)
```

Alert rule type: `rule_type = "spot_check"` in existing alert rules table. Uses existing notification delivery.

### Feedback Loop

Spot-check responses stored in `validation_feedback` table. Over time this calibrates penalty weights — if 80% of "contradictions" get confirmed as reasonable, penalties are too aggressive and should be reduced.

---

## Database Schema

### New Table: `validation_results`

```sql
CREATE TABLE validation_results (
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
);

CREATE INDEX idx_validation_results_ticker ON validation_results(ticker);
CREATE INDEX idx_validation_results_status ON validation_results(overall_status);
CREATE INDEX idx_validation_results_analysis ON validation_results(analysis_id);
```

### New Table: `validation_feedback`

```sql
CREATE TABLE validation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK(claim_type IN ('rule', 'council')),
    claim_summary TEXT NOT NULL,
    human_verdict TEXT NOT NULL CHECK(human_verdict IN ('confirmed', 'flagged')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (validation_id) REFERENCES validation_results(validation_id)
);

CREATE INDEX idx_validation_feedback_validation ON validation_feedback(validation_id);
```

---

## SSE Streaming

New event type emitted during Phase 2.5, after validation completes:

```python
yield f"event: validation\ndata: {json.dumps({
    'stage': 'validation_complete',
    'status': report['overall_status'],
    'confidence_penalty': report['total_confidence_penalty'],
    'contradictions': report['rule_validation']['contradictions']
                     + report['council_validation']['total_contradictions'],
    'spot_check_requested': report['spot_check_requested']
})}\n\n"
```

Fits between existing `"synthesizing"` and `"saving"` progress events.

## API Endpoint

### Spot-Check Feedback

```
POST /api/validation/{validation_id}/feedback
Body: { "verdict": "confirmed|flagged" }
Response: { "success": true, "validation_id": str, "verdict": str }
```

Single new endpoint. Stores feedback and returns updated record.

---

## Files Changed

| File | Change |
|---|---|
| `src/validation_rules.py` | **New** — rule engine, pure functions |
| `src/agents/council_validator_agent.py` | **New** — LLM-powered council validator |
| `src/orchestrator.py` | **Modified** — Phase 2.5 wiring, merge reports, confidence adjustment |
| `src/database.py` | **Modified** — two new tables, CRUD for validation results + feedback |
| `src/api.py` | **Modified** — SSE validation event, feedback endpoint |
| `src/config.py` | **Modified** — spot-check rate config, feature flag |
| `src/signal_contract.py` | **Modified** — validation attachment to contract |

---

## Feature Flag

```python
# In config.py
ENABLE_VALIDATION_V1 = os.getenv("ENABLE_VALIDATION_V1", "true").lower() == "true"
```

When disabled, Phase 2.5 is skipped entirely. No performance impact on existing pipeline.

---

## Testing Strategy

- **validation_rules.py** — Unit tests with fixture agent_results. Test each rule category with passing and failing cases. Test penalty capping logic.
- **council_validator_agent.py** — Unit tests with mocked LLM responses. Test claim extraction, prompt construction, response parsing, graceful degradation.
- **Orchestrator integration** — Test Phase 2.5 wiring with real agent results. Verify confidence adjustment flows through to signal contract.
- **API** — Test SSE validation event emission. Test feedback endpoint CRUD.
- **End-to-end** — Run full analysis with validation enabled, verify report attaches to signal contract and database.
