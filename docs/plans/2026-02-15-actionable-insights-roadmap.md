# Actionable Insights Roadmap

**Date**: 2026-02-15  
**Status**: Implemented in codebase (operational rollout hardening in progress)

## Current Completion Status

- Phases 1-3 feature scope has been implemented in the application and documented in
  `docs/plans/2026-02-16-quant-pm-upgrade-implementation-plan.md`.
- Remaining work is operational:
  - staged production rollout gate execution and monitoring,
  - production-scale Stage C benchmark validation,
  - deprecation-window completion across releases N+1 and N+2.

## Goal

Increase decision quality by turning analysis output into explicit trade plans, tracking what changed, and measuring whether prior calls were correct.

## Success Criteria

1. Every analysis result includes a machine-readable decision block.
2. Users can see meaningful deltas between the latest and previous run.
3. Alerts include suggested next actions, not just threshold breaches.
4. Signal quality is measurable over time (1d/1w/1m outcomes).
5. Portfolio context is used to rank opportunities by fit and risk impact.

## Roadmap (Priority Order)

### Phase 1: Decision Output + Deltas + Actionable Alerts (MVP)

### 1) Decision Card

**Outcome**: Each ticker analysis includes:
- `action` (`buy`/`hold`/`avoid`)
- `entry_zone`
- `stop_loss`
- `targets`
- `time_horizon`
- `confidence`
- `invalidation_conditions`
- `position_sizing_hint`

**Backend**
- Update synthesis schema in `src/agents/solution_agent.py`.
- Persist decision data in `src/database.py`.
- Include decision fields in latest/history endpoints in `src/api.py`.

**Frontend**
- Render decision card in analysis overview (`frontend/src/components/AnalysisTabs.jsx` and/or `frontend/src/components/Summary.jsx`).

**Acceptance**
- Decision payload exists for new analyses.
- UI shows full card with fallbacks for missing fields.

### 2) What Changed Since Last Run

**Outcome**: Show only high-signal deltas (trend, valuation, options skew, sentiment regime, macro regime).

**Backend**
- Add delta computation in `src/orchestrator.py` after synthesis.
- Store concise delta summary in `src/database.py`.
- Expose delta section via existing analysis endpoints in `src/api.py`.

**Frontend**
- Add a "Changes" panel in `frontend/src/components/AnalysisTabs.jsx`.

**Acceptance**
- Latest analysis includes diff vs previous analysis (if available).
- No noisy low-impact diffs.

### 3) Playbook Alerts

**Outcome**: Alerts include trigger reason + suggested next action.

**Backend**
- Extend rule evaluation payloads in `src/alert_engine.py`.
- Store `trigger_context`, `change_summary`, `suggested_action` in `src/database.py`.
- Return enriched alert payloads via `/api/alerts*` in `src/api.py`.

**Frontend**
- Display enriched alert cards in `frontend/src/components/AlertPanel.jsx`.

**Acceptance**
- Alert includes why it fired and what to do next.
- Existing acknowledge/unacknowledged workflows remain intact.

### Phase 2: Event-Aware and Portfolio-Aware Intelligence

### 4) Catalyst-Aware Scheduling

**Outcome**: Auto-run around major catalysts (earnings, FOMC, CPI, company events).

**Backend**
- Add catalyst-aware triggers in `src/scheduler.py`.
- Track run reason (`scheduled`, `catalyst_pre`, `catalyst_post`) in `src/database.py`.

**Acceptance**
- Jobs are scheduled and labeled by catalyst type.
- Existing manual and recurring schedules continue to work.

### 5) Portfolio-Aware Recommendations

**Outcome**: Recommendations reflect fit with portfolio constraints.

**Backend**
- Add portfolio holdings/risk profile storage in `src/database.py`.
- Compute fit score in synthesis path (`src/orchestrator.py` + `src/agents/solution_agent.py`) using concentration, sector overlap, beta/correlation, and risk budget effects.

**Frontend**
- Add portfolio fit section in overview/recommendation area.

**Acceptance**
- Same ticker can produce different ranking depending on portfolio state.

### Phase 3: Quality Calibration and Risk Framing

### 6) Signal Scorecard + Outcome Tracking

**Outcome**: Confidence is calibrated using realized outcomes at 1d/1w/1m.

**Backend**
- Add periodic evaluation job in `src/scheduler.py`.
- Store realized performance per signal in `src/database.py`.
- Surface calibration stats in `/api/analysis/*` endpoints in `src/api.py`.

**Frontend**
- Add confidence calibration visuals to history views.

**Acceptance**
- Historical signal accuracy and calibration are queryable and visible.

### 7) Scenario and Stress Outputs

**Outcome**: Each analysis includes bull/base/bear scenarios with probabilities and expected return/risk.

**Backend**
- Extend synthesis output in `src/agents/solution_agent.py` with scenario block using macro/options context.

**Frontend**
- Add scenario table/chart in analysis tabs.

**Acceptance**
- Scenario probabilities sum to 1.0 (within tolerance).

### 8) Disagreement + Data Quality Flags

**Outcome**: Users see when agents conflict or data is stale/low-confidence.

**Backend**
- Require confidence + recency metadata from data agents.
- Add conflict and data-quality summary in `src/orchestrator.py`.

**Frontend**
- Add warning badges and expandable diagnostics.

**Acceptance**
- Analyses with conflicting signals are explicitly flagged.
- Stale data warnings appear when source freshness thresholds are breached.

## Cross-Cutting Technical Notes

1. Keep SSE event names unchanged: `progress`, `result`, `error` (and `done` for watchlist stream).
2. Preserve `data_source` provenance in every new payload section.
3. Keep orchestrator dependency behavior intact (sentiment depends on news context).
4. For schema updates in `src/database.py`, use explicit manual migration steps and guard for existing DBs.

## Recommended Execution Sequence

1. Implement Decision Card schema + storage.
2. Implement Delta engine.
3. Upgrade Alert payloads.
4. Add Catalyst scheduling.
5. Add Portfolio-aware scoring.
6. Add Scorecard/calibration.
7. Add Scenario outputs.
8. Add Disagreement/data-quality diagnostics.
