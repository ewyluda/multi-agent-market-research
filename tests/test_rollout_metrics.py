"""Tests for Phase 7 rollout metrics and gate evaluation helpers."""

from datetime import datetime

from src.database import DatabaseManager
from src.rollout_metrics import compute_phase7_rollout_status


def _valid_signal_contract() -> dict:
    return {
        "schema_version": "2.0",
        "instrument_type": "US_EQUITY",
        "recommendation": "BUY",
        "confidence": {
            "raw": 0.72,
            "calibrated": 0.69,
            "uncertainty_band_pct": 12.0,
        },
        "evidence": [],
    }


def _valid_portfolio_action_v2() -> dict:
    return {
        "recommended_action": "add",
        "target_delta_pct": 0.01,
        "constraint_trace": [],
    }


def _insert_v2_analysis(db: DatabaseManager, ticker: str) -> int:
    return db.insert_analysis(
        ticker=ticker,
        recommendation="BUY",
        confidence_score=0.72,
        overall_sentiment_score=0.15,
        solution_agent_reasoning="v2 test analysis",
        duration_seconds=1.2,
        score=60,
        analysis_payload={"portfolio_action_v2": _valid_portfolio_action_v2()},
        analysis_schema_version="v2",
        signal_contract_v2=_valid_signal_contract(),
        ev_score_7d=2.5,
        confidence_calibrated=0.69,
        data_quality_score=82.0,
        regime_label="risk_on",
        rationale_summary="Concise summary",
    )


def test_rollout_status_passes_stage_a_and_stage_b_with_valid_data(tmp_path):
    db = DatabaseManager(str(tmp_path / "rollout_valid.db"))
    schedule = db.create_schedule("AAPL", 60)
    now = datetime.utcnow().isoformat()

    for idx in range(5):
        analysis_id = _insert_v2_analysis(db, ticker=f"T{idx}")
        db.insert_schedule_run(
            schedule_id=schedule["id"],
            analysis_id=analysis_id,
            started_at=now,
            completed_at=now,
            success=True,
            run_reason="scheduled",
        )

    db.replace_confidence_reliability_bins(
        as_of_date=datetime.utcnow().date().isoformat(),
        horizon_days=7,
        bins=[
            {
                "bin_index": 0,
                "bin_lower": 0.0,
                "bin_upper": 0.2,
                "sample_size": 10,
                "empirical_hit_rate": 0.6,
            }
        ],
    )

    status = compute_phase7_rollout_status(db_manager=db, window_hours=24)

    assert status["gates"]["stage_a"]["passed"] is True
    assert status["gates"]["stage_b"]["passed"] is True
    assert status["metrics"]["scheduled_runs"]["success_rate"] == 1.0
    assert status["metrics"]["scheduled_analyses"]["signal_contract_valid_count"] == 5
    assert status["metrics"]["all_analyses"]["portfolio_action_v2_parseable_count"] == 5


def test_rollout_status_fails_stage_a_when_gates_miss(tmp_path):
    db = DatabaseManager(str(tmp_path / "rollout_fail.db"))
    schedule = db.create_schedule("MSFT", 60)
    now = datetime.utcnow().isoformat()

    analysis_id = db.insert_analysis(
        ticker="FAIL",
        recommendation="HOLD",
        confidence_score=0.5,
        overall_sentiment_score=0.0,
        solution_agent_reasoning="legacy test analysis",
        duration_seconds=0.9,
        score=5,
        analysis_payload={"portfolio_action_v2": {"recommended_action": "add"}},
        analysis_schema_version="v1",
    )

    db.insert_schedule_run(
        schedule_id=schedule["id"],
        analysis_id=analysis_id,
        started_at=now,
        completed_at=now,
        success=True,
        run_reason="scheduled",
    )
    db.insert_schedule_run(
        schedule_id=schedule["id"],
        analysis_id=None,
        started_at=now,
        completed_at=now,
        success=False,
        run_reason="scheduled",
        error="intentional failure",
    )

    status = compute_phase7_rollout_status(db_manager=db, window_hours=24)
    checks = {check["name"]: check for check in status["gates"]["stage_a"]["checks"]}

    assert status["gates"]["stage_a"]["passed"] is False
    assert checks["scheduled_run_success_rate"]["passed"] is False
    assert checks["signal_contract_v2_coverage_scheduled"]["passed"] is False
    assert checks["reliability_non_empty_horizons"]["passed"] is False
