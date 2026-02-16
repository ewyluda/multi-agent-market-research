# Quant PM Upgrade Implementation Plan

Date: 2026-02-16  
Owner: Engineering  
Scope: US equities only (phase 1-3)

## Completion Snapshot

### Completed
- Phases 0-6 implementation completed in codebase.
- Canonical interface additions implemented and documented.
- Database/migration updates implemented with idempotent guards.
- Scheduled-run rollout override flags implemented in config/scheduler:
  - `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED`
  - `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED`
  - `SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED`
  - `SCHEDULED_ALERTS_V2_ENABLED`
- Phase 7 rollout gate monitoring implemented:
  - `src/rollout_metrics.py` (Stage A/B gate calculations from DB state)
  - `GET /api/rollout/phase7/status?window_hours=` (metrics + gate payload + flag posture)
- Phase 7 canary automation implemented:
  - `src/rollout_canary.py` (`python -m src.rollout_canary --stage preflight|stage_a|stage_b|stage_c|stage_d|all`)
  - Covers preflight health/status/flag posture, Stage A/B gate checks, Stage B alert CRUD checks,
    Stage C watchlist SSE + speedup checks, and Stage D PM-critical API checks
- Local rollout validation runs completed:
  - Stage C (4 tickers, default agents): passed, speedup `1.758x` (watchlist `98.13s` vs sequential `172.53s`)
  - Stage C low-pressure mode (`--stage-c-agents market,technical`): passed, speedup `2.979x`
  - Stage D (with frontend availability check): passed
- 180-day `signal_contract_v2` backfill utility implemented (`src/backfill_signal_contract.py`).
- Backfill execution completed on local DB with audit report:
  - `docs/reports/signal-contract-backfill-report.md`
  - `scanned=28`, `eligible=28`, `updated=28`, `hard_failures=0`
- Backfill idempotency verified (dry-run rerun produced `eligible=0`, `skipped_existing_valid=28`).
- Watchlist analyze endpoint now supports optional agent subset filtering (`POST /api/watchlists/{watchlist_id}/analyze?agents=`) to reduce API load during canary/ops runs.
- Test suite passing: `214 passed`.

### Remaining (Operational Phase 7 Closeout)
- Production rollout execution via staged feature-flag enablement (Preflight, Stages A-D).
- Stage gate validation execution and rollback monitoring during each rollout stage.
- Production-scale Stage C benchmark on 20-ticker set with target `>=2x` speedup.
- Post-rollout deprecation execution:
  - Release N+1 deprecation readiness items.
  - Release N+2 removal readiness and legacy-path cleanup.
- Final acceptance sign-off after rollout gates are met in production.

## Locked Decisions
1. Delivery mode: phased hardening.
2. Instrument scope: US equities only.
3. Reasoning policy: no chain-of-thought in UI or DB by default.

## Feature Flags (Phase Gating)
Implemented in `src/config.py` and `.env.example`:
- `SIGNAL_CONTRACT_V2_ENABLED=false`
- `COT_PERSISTENCE_ENABLED=false`
- `PORTFOLIO_OPTIMIZER_V2_ENABLED=false`
- `CALIBRATION_ECONOMICS_ENABLED=false`
- `ALERTS_V2_ENABLED=false`
- `WATCHLIST_RANKING_ENABLED=false`
- `UI_PM_DASHBOARD_ENABLED=false`
- Scheduled-run rollout overrides:
  - `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED=false`
  - `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED=false`
  - `SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED=false`
  - `SCHEDULED_ALERTS_V2_ENABLED=false`

## Delivery Status

### Phase 0: Foundation and guardrails
Status: Completed
- Added all feature flags with safe defaults.
- Added schema/version plumbing (`analysis_schema_version`) in API/models/DB.
- Added baseline orchestrator metrics logging (latency, success rate, freshness).

### Phase 1: Signal Contract V2 + CoT removal defaults
Status: Completed
- Added deterministic signal contract module: `src/signal_contract.py`.
- Added signal contract build/validation in orchestrator behind `SIGNAL_CONTRACT_V2_ENABLED`.
- Added `rationale_summary` support and CoT persistence guard via `COT_PERSISTENCE_ENABLED`.
- Added response payload compatibility while introducing canonical `signal_contract_v2`.
- Frontend summary moved to action/risk/evidence style cards; chain-of-thought display removed from active flow.

### Phase 2: Calibration economics and reliability
Status: Completed (flagged rollout)
- Scheduler computes and persists net return, drawdown proxy, utility when `CALIBRATION_ECONOMICS_ENABLED=true`.
- Added reliability bin persistence and lookup (`confidence_reliability_bins`).
- Added calibration reliability endpoint: `GET /api/calibration/reliability?horizon_days=1|7|30`.

### Phase 3: Portfolio optimizer v2
Status: Completed (flagged rollout)
- Added constrained 1-D optimizer in `src/portfolio_engine.py`.
- Preserved legacy `portfolio_action`; added `portfolio_action_v2` trace payload.
- Orchestrator keeps v2 payload behind `PORTFOLIO_OPTIMIZER_V2_ENABLED` while legacy remains stable.

### Phase 4: Alerts v2
Status: Completed (flagged rollout)
- Alert rules expanded to `ev_above`, `ev_below`, `regime_change`, `data_quality_below`, `calibration_drop`.
- Added table rebuild migration guard for `alert_rules` constraint expansion.
- Alert engine supports v2 triggers and playbook-style suggested actions.
- API validation for v2 rule types gated by `ALERTS_V2_ENABLED`.

### Phase 5: Watchlist ranking + bounded parallelism
Status: Completed
- Watchlist SSE analysis now uses bounded concurrency (4 workers).
- Added ranked opportunity endpoint:
  - `GET /api/watchlists/{watchlist_id}/opportunities?limit=&min_quality=&min_ev=`
- SSE `done` event includes opportunities when `WATCHLIST_RANKING_ENABLED=true`.

### Phase 6: PM workflow UI consolidation
Status: Completed (initial consolidation)
- Analysis tabs reduced to `Overview`, `Risk`, `Opportunities`, `Diagnostics`.
- Recommendation panel prefers `signal_contract_v2` and supports optimizer v2 action display.
- Watchlist UI includes ranked opportunities table.
- Alert UI supports new rule types and playbook action cards.
- History UI includes calibration reliability bins and net-return trend view.

### Phase 7: Hardening, backfill, rollout
Status: In progress (backfill complete; production rollout and deprecation execution pending)
- Hardening baseline done through full backend test pass.
- Remaining operational tasks are captured in the runbook below.
- Backfill utility implemented and executed:
  - command: `python -m src.backfill_signal_contract --db-path market_research.db --days 180 --batch-size 200 --checkpoint-file /tmp/signal_contract_backfill_checkpoint_v2.json --report-path docs/reports/signal-contract-backfill-report.md`
  - result: `scanned=28`, `eligible=28`, `updated=28`, `hard_failures=0`

## Canonical Interface Additions (Expanded Contract)
1. `POST /api/analyze/{ticker}`:
- Always returns legacy compatibility keys (`recommendation`, `score`, `confidence`, `decision_card`, `change_summary`, `portfolio_action`).
- When `SIGNAL_CONTRACT_V2_ENABLED=true`, include:
  - `analysis.analysis_schema_version="v2"`
  - `analysis.signal_contract_v2`
  - `analysis.ev_score_7d`
  - `analysis.confidence_calibrated`
  - `analysis.data_quality_score`
  - `analysis.regime_label`
  - `analysis.rationale_summary`
2. `GET /api/analyze/{ticker}/stream` SSE:
- Event names remain unchanged: `progress`, `result`, `error`.
- `result` payload mirrors analyze response and includes v2 fields when enabled.
3. `GET /api/analysis/{ticker}/latest`:
- Same v2 behavior and compatibility model as `POST /api/analyze/{ticker}`.
4. `GET /api/analysis/{ticker}/history/detailed`:
- Supports and returns v2 filter/result fields: `ev_score_7d`, `confidence_calibrated`, `data_quality_score`, `regime_label`.
- Legacy fields remain present for compatibility.
5. `POST /api/watchlists/{watchlist_id}/analyze` SSE:
- Event names remain unchanged: `result`, `error`, `done`.
- Supports optional `agents` query filter using the same valid agent set as single-ticker analyze.
- `done` includes ranked `opportunities` only when `WATCHLIST_RANKING_ENABLED=true`.
6. `GET /api/watchlists/{watchlist_id}/opportunities?limit=&min_quality=&min_ev=`:
- Returns latest ranked opportunities without re-running analysis.
7. `GET /api/calibration/reliability?horizon_days=1|7|30`:
- Returns bin metadata, empirical hit rates, sample sizes, and as-of date.
8. `POST /api/alerts` and `GET /api/alerts`:
- Preserve existing legacy rule types.
- Accept/return v2 rule types only when `ALERTS_V2_ENABLED=true`:
  - `ev_above`, `ev_below`, `regime_change`, `data_quality_below`, `calibration_drop`
9. Typed interface alignment (`src/models.py`):
- `FinalAnalysis` keeps legacy fields and optional v2 fields.
- `AnalysisResponse.analysis_schema_version` remains top-level optional compatibility field.
10. Rollout operations endpoint (additive/internal):
- `GET /api/rollout/phase7/status?window_hours=` returns computed Stage A/B gate status,
  supporting metrics, and current feature-flag posture.

## Database and Migration Updates (Expanded)
Idempotent migration guards remain implemented in `src/database.py`.

1. `analyses` table:
- Required columns: `analysis_schema_version`, `signal_contract_v2`, `ev_score_7d`, `confidence_calibrated`, `data_quality_score`, `regime_label`, `rationale_summary`.
- Legacy payload columns are preserved unchanged for compatibility.
2. `analysis_outcomes` table:
- Required columns: `transaction_cost_bps`, `slippage_bps`, `realized_return_net_pct`, `max_drawdown_pct`, `utility_score`.
3. `calibration_snapshots` table:
- Required columns: `mean_net_return_pct`, `mean_drawdown_pct`, `utility_mean`.
4. `confidence_reliability_bins` table:
- Unique key: `(as_of_date, horizon_days, bin_index)`.
- Index retained: `(horizon_days, as_of_date DESC, bin_index ASC)`.
5. `portfolio_profile` table:
- Required columns: `target_portfolio_beta`, `max_turnover_pct`, `default_transaction_cost_bps`.
6. `portfolio_holdings` behavior:
- Keep `market_value` storage.
- API accepts omitted `market_value` and computes mark-to-market server-side when possible.
7. `alert_rules` migration:
- Idempotent rebuild guard retained.
- Legacy rule rows are preserved during rebuild.
8. Migration behavior constraints:
- Manual/idempotent guard strategy only.
- No destructive migration steps.
- Safe across fresh, legacy, and already-migrated SQLite databases.

## Phase 7 Rollout Runbook

Current rollout execution status:
- Preflight (Day 0): Completed in local/dev environment on 2026-02-16 with full canary pass (`12/12` checks).
- Stage A (Days 1-3): In progress (scheduler-only rollout flags enabled; gate still blocked by insufficient scheduled-run window metrics and empty reliability bins).
- Stage B (Days 4-5): Not started in production.
- Stage C (Day 6): Not started in production.
- Stage D (Day 7): Not started in production.

### Preflight (Day 0)
- Deploy code + DB migrations with all new flags `false`.
- Run scripted preflight canary:
  - `python -m src.rollout_canary --base-url http://<env-host>:8000 --stage preflight`
- Validate:
  - `/health` returns healthy response.
  - `/api/rollout/phase7/status?window_hours=24` returns metrics/gates payload and expected flag posture.
  - migration columns/tables/indexes exist.
  - baseline log line emitted by orchestrator: `baseline_metrics ticker=... latency_s=... agent_success_rate=...`.
- Confirm CoT policy:
  - New analyses persist concise rationale only when `COT_PERSISTENCE_ENABLED=false`.

### Stage A (Days 1-3, scheduled runs only)
- Enable:
  - `SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED=true`
  - `SCHEDULED_CALIBRATION_ECONOMICS_ENABLED=true`
- Keep global flags `SIGNAL_CONTRACT_V2_ENABLED=false` and `CALIBRATION_ECONOMICS_ENABLED=false` during Stage A.
- Keep all other new flags/overrides `false`.
- Promotion gates:
  - Canary command: `python -m src.rollout_canary --base-url http://<env-host>:8000 --stage stage_a --window-hours 72`
  - `GET /api/rollout/phase7/status?window_hours=72` reports Stage A gate checks passing.
  - API success rate `>=99%` for scheduled runs.
  - `signal_contract_v2` present on `>=98%` of scheduled analyses.
  - No schema regression for existing clients.
  - Reliability endpoint has non-empty bins for at least one horizon.
- Rollback triggers:
  - Contract validation failures `>2%`.
  - Any breaking payload compatibility issue.

Current checkpoint (2026-02-16):
- Stage A flag posture is correctly applied (`global=false`, `scheduled signal/calibration=true`).
- Gate blockers from `/api/rollout/phase7/status?window_hours=72`:
  - `scheduled_runs.total_runs=0` (no scheduled execution yet in window)
  - `reliability_bins.non_empty_horizon_count=0`
- Earliest natural reliability population from newly created 1d outcomes is the next trading day (for runs created on 2026-02-16, earliest due date is 2026-02-17).

### Stage B (Days 4-5, internal users)
- Enable:
  - `PORTFOLIO_OPTIMIZER_V2_ENABLED=true`
  - `ALERTS_V2_ENABLED=true`
- Promotion gates:
  - Canary command: `python -m src.rollout_canary --base-url http://<env-host>:8000 --stage stage_b --window-hours 72`
  - `GET /api/rollout/phase7/status?window_hours=72` reports Stage B gate checks passing.
  - `portfolio_action_v2` present + parseable on `>=98%` of v2 analyses.
  - v2 alert rule create/read succeeds.
  - Legacy alert workflows unchanged.
- Rollback triggers:
  - Missing required optimizer action fields `>2%`.
  - Valid legacy alert rules rejected by API.

### Stage C (Day 6)
- Enable:
  - `WATCHLIST_RANKING_ENABLED=true`
- Promotion gates:
  - Canary command: `python -m src.rollout_canary --base-url http://<env-host>:8000 --stage stage_c --window-hours 72 --stage-c-tickers <20 comma-separated tickers> --stage-c-agents market,technical --stage-c-required-speedup 2.0`
  - Watchlist SSE consistently emits `done` with `opportunities`.
  - 20-ticker watchlist runtime (concurrency 4) is `>=2x` faster than sequential baseline.
- Rollback triggers:
  - SSE instability/timeouts or ranking payload regressions.

### Stage D (Day 7)
- Enable:
  - `UI_PM_DASHBOARD_ENABLED=true`
- Promotion gates:
  - Canary command: `python -m src.rollout_canary --base-url http://<env-host>:8000 --stage stage_d --window-hours 72 --frontend-url http://<frontend-host>:5173`
  - PM tabs render with v2-first + legacy fallback behavior.
  - No blocking regressions in history/watchlist/alerts/portfolio flows.
- Rollback triggers:
  - Critical UI path broken for analyze/latest/history/watchlist/alerts.

### Post-stage steady state
- Keep legacy payload keys for two releases.
- Continue daily calibration/reliability monitoring.

## Backfill Procedure (180-day)

### Scope
- Backfill analyses from the last 180 days where:
  - `signal_contract_v2` is missing or invalid, or
  - `analysis_schema_version='v1'`.

### Implementation Path
- Utility: `src/backfill_signal_contract.py`
- Execution:
```bash
source venv/bin/activate
python -m src.backfill_signal_contract \
  --db-path market_research.db \
  --days 180 \
  --batch-size 200 \
  --checkpoint-file /tmp/signal_contract_backfill_checkpoint.json \
  --report-path docs/reports/signal-contract-backfill-report.md
```

### Backfill algorithm
1. Read eligible analysis rows in batches with checkpoint cursor (`last_processed_id`).
2. Resolve analysis payload and agent results for each row.
3. Reconstruct deterministic contract using existing builder path (`build_signal_contract_v2`).
4. Validate contract (`validate_signal_contract_v2`) before write.
5. Write additive v2 fields (`analysis_schema_version`, `signal_contract_v2`, `ev_score_7d`, `confidence_calibrated`, `data_quality_score`, `regime_label`, `rationale_summary`) without removing legacy keys.

### Idempotency
- Rows with valid existing `signal_contract_v2` are skipped.
- Re-run safe via checkpoint cursor and existing-contract validation.

### Failure handling
- Missing reconstructable analysis context (payload + core fallbacks unavailable): skip and record reason.
- Missing agent results: skip and record reason.
- Validation/write failure: record and continue processing.

### Verification
- Report totals: `scanned`, `eligible`, `updated`, `skipped`, `failed`.
- Spot-check 20 random rows for schema validity + compatibility.
- Hard-failure target: `<1%` of eligible rows.

## Backfill Execution Checklist
- [x] Run dry-run (`--dry-run`) and inspect eligible/failure mix.
- [x] Execute write run with checkpoint + markdown report path.
- [x] Confirm report has `<1%` hard failures.
- [x] Manually spot-check 20 rows.
- [x] Archive report under `docs/reports/`.

## Backfill Audit Report Template
Use this template block for every production backfill run:

```markdown
# Signal Contract V2 Backfill Audit Report

- Started:
- Ended:
- Scope (days):
- Since timestamp:
- Batch size:
- Dry run:

## Summary
| Metric | Value |
| --- | ---: |
| Scanned | |
| Eligible | |
| Updated | |
| Skipped (existing valid) | |
| Skipped (missing payload) | |
| Skipped (missing agent results) | |
| Failed (validation) | |
| Failed (write) | |
| Hard failure rate | |

## Spot-check (20 rows)
| analysis_id | ticker | schema_version=v2 | signal_contract_v2 valid | legacy keys unchanged | notes |
| --- | --- | --- | --- | --- | --- |
```

## Legacy Deprecation Schedule (2 Releases)

### Release N
- Keep both v1 and v2 fields.
- Publish deprecation notice for legacy-only reasoning/UI paths and legacy-only consumer behavior.

### Release N+1
- Keep fallback paths.
- Emit warning telemetry/log marker for legacy reads.
- Validate `<10%` of requests rely exclusively on legacy fields.

### Release N+2
- Remove deprecated UI renderers and legacy-only paths.
- Keep compatibility keys only when external clients still require them; otherwise remove by explicit release note.

## Deprecation Readiness Checklist

### N+1 readiness
- [ ] Deprecation notice published in release notes. (pending)
- [ ] Legacy usage telemetry enabled. (pending)
- [ ] Client migration owners assigned. (pending)

### N+2 removal readiness
- [ ] Legacy-only usage < agreed threshold. (pending)
- [ ] External consumers confirmed migrated. (pending)
- [ ] Removal PR validated in staging with rollback option. (pending)

## Test and Validation
1. Contract/API tests:
- Validate v2 payload fields under enabled flags and legacy compatibility with flags off.
2. Migration tests:
- Validate idempotent initialization/migration on fresh and legacy DBs.
3. Backfill tests:
- Validate row selection, idempotent skip, and partial-failure continuation.
4. Scheduler/calibration tests:
- Validate net-return, drawdown, utility, and reliability bin persistence for 1d/7d/30d.
5. Alert tests:
- Validate v2 rule create/evaluate behavior and legacy parity.
6. Watchlist tests:
- Validate SSE `result/error/done` and ranking inclusion semantics.
7. UI tests:
- Validate PM tabs and v2-first + legacy fallback render paths.
8. Canary checks:
- Run synthetic analyze/watchlist/alerts/calibration flows at each rollout stage.

Current backend suite status:
- `214 passed`

## Acceptance Criteria
1. Phase 7 rollout completed with promotion gates satisfied and no compatibility regressions.
2. Canonical interface section is explicit enough for client implementation without ambiguity.
3. Database/migration section matches current `src/database.py` behavior.
4. 180-day backfill completes with auditable report and `<1%` hard failures.
5. Legacy deprecation timeline is published and tracked across two releases.

## Assumptions and Defaults
1. Backfill scope is fixed at 180 days.
2. Legacy deprecation occurs after two releases.
3. Rollout is phased and feature-flag driven.
4. US equities remain the only supported instrument in this rollout.
5. SSE event names and legacy response keys remain unchanged during compatibility window.
