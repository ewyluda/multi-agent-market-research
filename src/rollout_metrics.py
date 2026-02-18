"""Phase 7 rollout gate metrics and status helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from .database import DatabaseManager
from .signal_contract import validate_signal_contract_v2


LEGACY_ALERT_RULE_TYPES: Set[str] = {
    "recommendation_change",
    "score_above",
    "score_below",
    "confidence_above",
    "confidence_below",
}
V2_ALERT_RULE_TYPES: Set[str] = {
    "ev_above",
    "ev_below",
    "regime_change",
    "data_quality_below",
    "calibration_drop",
}
ALL_ALERT_RULE_TYPES: Set[str] = LEGACY_ALERT_RULE_TYPES.union(V2_ALERT_RULE_TYPES)


def _safe_json_dict(value: Any) -> Optional[Dict[str, Any]]:
    """Best-effort conversion to dict for JSON-serialized DB fields."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _safe_ratio(numerator: int, denominator: int) -> Optional[float]:
    """Return ratio or None when denominator is zero."""
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _is_parseable_portfolio_action_v2(payload: Any) -> bool:
    """Validate minimal optimizer action contract used for rollout gating."""
    if not isinstance(payload, dict):
        return False

    if str(payload.get("recommended_action") or "").strip() not in {"hold", "add", "trim", "exit"}:
        return False

    try:
        float(payload.get("target_delta_pct"))
    except (TypeError, ValueError):
        return False

    if not isinstance(payload.get("constraint_trace"), list):
        return False

    return True


def _load_analysis_rows(
    db_manager: DatabaseManager,
    *,
    since_timestamp: str,
    scheduled_only: bool,
) -> List[Dict[str, Any]]:
    """Load analysis rows for rollout window."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        if scheduled_only:
            cursor.execute(
                """
                SELECT DISTINCT
                    a.id,
                    a.analysis_schema_version,
                    a.signal_contract_v2,
                    a.analysis_payload,
                    a.ev_score_7d,
                    a.confidence_calibrated,
                    a.data_quality_score,
                    a.regime_label
                FROM analyses a
                INNER JOIN schedule_runs sr ON sr.analysis_id = a.id
                WHERE sr.started_at >= ?
                  AND COALESCE(sr.success, 0) = 1
                ORDER BY a.id DESC
                """,
                (since_timestamp,),
            )
        else:
            cursor.execute(
                """
                SELECT
                    id,
                    analysis_schema_version,
                    signal_contract_v2,
                    analysis_payload,
                    ev_score_7d,
                    confidence_calibrated,
                    data_quality_score,
                    regime_label
                FROM analyses
                WHERE timestamp >= ?
                ORDER BY id DESC
                """,
                (since_timestamp,),
            )
        return [dict(row) for row in cursor.fetchall()]


def _build_analysis_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build analysis coverage metrics for rollout evaluation."""
    total = len(rows)
    schema_v2_count = 0
    signal_contract_present_count = 0
    signal_contract_valid_count = 0
    portfolio_action_v2_parseable_count = 0
    ev_score_non_null_count = 0
    confidence_calibrated_non_null_count = 0
    data_quality_non_null_count = 0
    regime_label_non_null_count = 0

    for row in rows:
        if str(row.get("analysis_schema_version") or "").lower() == "v2":
            schema_v2_count += 1

        signal_contract = _safe_json_dict(row.get("signal_contract_v2"))
        if isinstance(signal_contract, dict):
            signal_contract_present_count += 1
            is_valid, _ = validate_signal_contract_v2(signal_contract)
            if is_valid:
                signal_contract_valid_count += 1

        payload = _safe_json_dict(row.get("analysis_payload")) or {}
        if _is_parseable_portfolio_action_v2(payload.get("portfolio_action_v2")):
            portfolio_action_v2_parseable_count += 1

        if row.get("ev_score_7d") is not None:
            ev_score_non_null_count += 1
        if row.get("confidence_calibrated") is not None:
            confidence_calibrated_non_null_count += 1
        if row.get("data_quality_score") is not None:
            data_quality_non_null_count += 1
        if str(row.get("regime_label") or "").strip():
            regime_label_non_null_count += 1

    portfolio_target = max(schema_v2_count, 1)
    return {
        "total": total,
        "schema_v2_count": schema_v2_count,
        "signal_contract_present_count": signal_contract_present_count,
        "signal_contract_valid_count": signal_contract_valid_count,
        "signal_contract_valid_coverage": _safe_ratio(signal_contract_valid_count, total),
        "portfolio_action_v2_parseable_count": portfolio_action_v2_parseable_count,
        "portfolio_action_v2_coverage_on_v2": _safe_ratio(portfolio_action_v2_parseable_count, portfolio_target),
        "ev_score_non_null_count": ev_score_non_null_count,
        "confidence_calibrated_non_null_count": confidence_calibrated_non_null_count,
        "data_quality_non_null_count": data_quality_non_null_count,
        "regime_label_non_null_count": regime_label_non_null_count,
    }


def _load_schedule_run_metrics(db_manager: DatabaseManager, *, since_timestamp: str) -> Dict[str, Any]:
    """Load schedule-run success metrics for rollout window."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_runs,
                SUM(CASE WHEN COALESCE(success, 0) = 1 THEN 1 ELSE 0 END) AS success_runs
            FROM schedule_runs
            WHERE started_at >= ?
            """,
            (since_timestamp,),
        )
        row = dict(cursor.fetchone() or {})
        total_runs = int(row.get("total_runs") or 0)
        success_runs = int(row.get("success_runs") or 0)
        return {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "success_rate": _safe_ratio(success_runs, total_runs),
        }


def _load_reliability_metrics(db_manager: DatabaseManager) -> Dict[str, Any]:
    """Load confidence reliability-bin coverage by horizon."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT horizon_days, COUNT(*) AS bin_count, MAX(as_of_date) AS as_of_date
            FROM confidence_reliability_bins
            GROUP BY horizon_days
            ORDER BY horizon_days ASC
            """
        )
        rows = [dict(row) for row in cursor.fetchall()]

    horizons: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(int(row.get("horizon_days") or 0))
        horizons[key] = {
            "bin_count": int(row.get("bin_count") or 0),
            "as_of_date": row.get("as_of_date"),
        }

    non_empty_horizon_count = sum(1 for item in horizons.values() if int(item.get("bin_count") or 0) > 0)
    return {
        "horizons": horizons,
        "non_empty_horizon_count": non_empty_horizon_count,
    }


def _load_alert_rule_metrics(db_manager: DatabaseManager) -> Dict[str, Any]:
    """Load alert rule type distribution and schema-integrity checks."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT rule_type, COUNT(*) AS row_count
            FROM alert_rules
            GROUP BY rule_type
            ORDER BY rule_type ASC
            """
        )
        rows = [dict(row) for row in cursor.fetchall()]

    by_type = {str(row.get("rule_type")): int(row.get("row_count") or 0) for row in rows}
    unknown_types = sorted([rule_type for rule_type in by_type if rule_type not in ALL_ALERT_RULE_TYPES])
    legacy_count = sum(by_type.get(rule_type, 0) for rule_type in LEGACY_ALERT_RULE_TYPES)
    v2_count = sum(by_type.get(rule_type, 0) for rule_type in V2_ALERT_RULE_TYPES)

    return {
        "by_type": by_type,
        "legacy_count": int(legacy_count),
        "v2_count": int(v2_count),
        "unknown_type_count": len(unknown_types),
        "unknown_types": unknown_types,
    }


def _check(name: str, passed: bool, actual: Any, threshold: Optional[str], detail: str) -> Dict[str, Any]:
    """Return a normalized gate-check payload."""
    return {
        "name": name,
        "passed": bool(passed),
        "actual": actual,
        "threshold": threshold,
        "detail": detail,
    }


def _evaluate_stage_a(
    *,
    scheduled_run_metrics: Dict[str, Any],
    scheduled_analysis_metrics: Dict[str, Any],
    reliability_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate Stage A gates."""
    success_rate = scheduled_run_metrics.get("success_rate")
    signal_coverage = scheduled_analysis_metrics.get("signal_contract_valid_coverage")
    reliability_horizons = int(reliability_metrics.get("non_empty_horizon_count") or 0)

    checks = [
        _check(
            "scheduled_run_success_rate",
            (success_rate is not None) and (success_rate >= 0.99),
            round(float(success_rate), 4) if success_rate is not None else None,
            ">= 0.99",
            "Scheduled run success rate in the selected window.",
        ),
        _check(
            "signal_contract_v2_coverage_scheduled",
            (signal_coverage is not None) and (signal_coverage >= 0.98),
            round(float(signal_coverage), 4) if signal_coverage is not None else None,
            ">= 0.98",
            "Coverage of valid signal_contract_v2 on successful scheduled analyses.",
        ),
        _check(
            "reliability_non_empty_horizons",
            reliability_horizons >= 1,
            reliability_horizons,
            ">= 1",
            "At least one reliability horizon has non-empty bins.",
        ),
    ]
    manual_checks = [
        "Confirm no schema regressions in external clients consuming legacy response keys.",
    ]
    passed = all(bool(item["passed"]) for item in checks)
    return {"passed": passed, "checks": checks, "manual_checks": manual_checks}


def _evaluate_stage_b(
    *,
    all_analysis_metrics: Dict[str, Any],
    alert_rule_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate Stage B gates."""
    portfolio_coverage = all_analysis_metrics.get("portfolio_action_v2_coverage_on_v2")
    unknown_type_count = int(alert_rule_metrics.get("unknown_type_count") or 0)

    checks = [
        _check(
            "portfolio_action_v2_coverage_on_v2",
            (portfolio_coverage is not None) and (portfolio_coverage >= 0.98),
            round(float(portfolio_coverage), 4) if portfolio_coverage is not None else None,
            ">= 0.98",
            "Coverage of parseable portfolio_action_v2 payloads for v2 analyses.",
        ),
        _check(
            "alert_rule_type_integrity",
            unknown_type_count == 0,
            unknown_type_count,
            "== 0",
            "Alert rules table contains only supported legacy/v2 rule types.",
        ),
    ]
    manual_checks = [
        "Run internal API canary to verify v2 alert create/read paths.",
        "Run internal API canary to verify legacy alert create/read compatibility.",
    ]
    passed = all(bool(item["passed"]) for item in checks)
    return {"passed": passed, "checks": checks, "manual_checks": manual_checks}


def compute_phase7_rollout_status(
    *,
    db_manager: DatabaseManager,
    window_hours: int = 72,
) -> Dict[str, Any]:
    """Compute Phase 7 rollout metrics and stage gate status."""
    bounded_hours = max(1, int(window_hours))
    now = datetime.now(timezone.utc)
    since_timestamp = (now - timedelta(hours=bounded_hours)).isoformat()

    scheduled_run_metrics = _load_schedule_run_metrics(db_manager, since_timestamp=since_timestamp)
    scheduled_analysis_rows = _load_analysis_rows(
        db_manager,
        since_timestamp=since_timestamp,
        scheduled_only=True,
    )
    all_analysis_rows = _load_analysis_rows(
        db_manager,
        since_timestamp=since_timestamp,
        scheduled_only=False,
    )
    scheduled_analysis_metrics = _build_analysis_metrics(scheduled_analysis_rows)
    all_analysis_metrics = _build_analysis_metrics(all_analysis_rows)
    reliability_metrics = _load_reliability_metrics(db_manager)
    alert_rule_metrics = _load_alert_rule_metrics(db_manager)

    return {
        "generated_at": now.isoformat(),
        "window_hours": bounded_hours,
        "since_timestamp": since_timestamp,
        "metrics": {
            "scheduled_runs": scheduled_run_metrics,
            "scheduled_analyses": scheduled_analysis_metrics,
            "all_analyses": all_analysis_metrics,
            "reliability_bins": reliability_metrics,
            "alert_rules": alert_rule_metrics,
        },
        "gates": {
            "stage_a": _evaluate_stage_a(
                scheduled_run_metrics=scheduled_run_metrics,
                scheduled_analysis_metrics=scheduled_analysis_metrics,
                reliability_metrics=reliability_metrics,
            ),
            "stage_b": _evaluate_stage_b(
                all_analysis_metrics=all_analysis_metrics,
                alert_rule_metrics=alert_rule_metrics,
            ),
            "stage_c": {
                "passed": False,
                "checks": [],
                "manual_checks": [
                    "Run watchlist SSE canary and verify `done` includes opportunities.",
                    "Benchmark 20-ticker watchlist runtime and confirm >=2x gain vs sequential baseline.",
                ],
            },
            "stage_d": {
                "passed": False,
                "checks": [],
                "manual_checks": [
                    "Run PM dashboard UI canary and verify v2-first rendering with legacy fallback.",
                    "Verify no blocking regressions in history, watchlist, alerts, and portfolio panels.",
                ],
            },
        },
    }
