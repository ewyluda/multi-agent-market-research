"""Tests for rollout canary runner."""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from src.rollout_canary import RolloutCanaryRunner


class _FakeResponse:
    """Minimal fake requests response object for canary tests."""

    def __init__(self, status_code: int, payload: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = str(self._payload)

    def json(self) -> Dict[str, Any]:
        return self._payload


def _session_with_responses(responses: List[_FakeResponse]) -> MagicMock:
    session = MagicMock()
    session.request.side_effect = responses
    return session


def test_preflight_canary_passes_with_expected_flags():
    rollout_payload = {
        "generated_at": "2026-02-16T00:00:00Z",
        "metrics": {},
        "gates": {},
        "feature_flags": {
            "SIGNAL_CONTRACT_V2_ENABLED": False,
            "CALIBRATION_ECONOMICS_ENABLED": False,
            "PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "ALERTS_V2_ENABLED": False,
            "WATCHLIST_RANKING_ENABLED": False,
            "UI_PM_DASHBOARD_ENABLED": False,
            "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": False,
            "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": False,
            "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "SCHEDULED_ALERTS_V2_ENABLED": False,
        },
    }
    session = _session_with_responses(
        [
            _FakeResponse(200, {"status": "healthy", "database_connected": True, "config_valid": True}),
            _FakeResponse(200, rollout_payload),
        ]
    )
    runner = RolloutCanaryRunner(base_url="http://test.local", session=session)

    summary = runner.run(stage="preflight")

    assert summary["passed"] is True
    assert summary["failed_checks"] == 0
    assert summary["runs"][0]["stage"] == "preflight"


def test_stage_a_canary_fails_when_gate_or_flags_fail():
    rollout_payload = {
        "generated_at": "2026-02-16T00:00:00Z",
        "metrics": {},
        "gates": {"stage_a": {"passed": False}},
        "feature_flags": {
            "SIGNAL_CONTRACT_V2_ENABLED": False,
            "CALIBRATION_ECONOMICS_ENABLED": False,
            "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": False,  # should be true in Stage A
            "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
            "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "SCHEDULED_ALERTS_V2_ENABLED": False,
        },
    }
    session = _session_with_responses(
        [
            _FakeResponse(200, rollout_payload),
            _FakeResponse(200, {"horizon_days": 1, "bins": []}),
            _FakeResponse(200, {"horizon_days": 7, "bins": []}),
            _FakeResponse(200, {"horizon_days": 30, "bins": []}),
        ]
    )
    runner = RolloutCanaryRunner(base_url="http://test.local", session=session)

    summary = runner.run(stage="stage_a")

    assert summary["passed"] is False
    stage = summary["runs"][0]
    assert stage["stage"] == "stage_a"
    assert stage["failed_checks"] >= 2


def test_stage_b_canary_passes_with_alert_crud():
    rollout_payload = {
        "generated_at": "2026-02-16T00:00:00Z",
        "metrics": {},
        "gates": {"stage_b": {"passed": True}},
        "feature_flags": {
            "PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
            "ALERTS_V2_ENABLED": True,
        },
    }
    session = _session_with_responses(
        [
            _FakeResponse(200, rollout_payload),
            _FakeResponse(200, {"id": 101, "rule_type": "ev_above"}),
            _FakeResponse(200, {"id": 101, "rule_type": "ev_above"}),
            _FakeResponse(200, {"id": 102, "rule_type": "recommendation_change"}),
            _FakeResponse(200, {"success": True, "deleted_id": 101}),
            _FakeResponse(200, {"success": True, "deleted_id": 102}),
        ]
    )
    runner = RolloutCanaryRunner(base_url="http://test.local", session=session)

    summary = runner.run(stage="stage_b")

    assert summary["passed"] is True
    stage = summary["runs"][0]
    assert stage["stage"] == "stage_b"
    assert stage["failed_checks"] == 0


def test_stage_c_canary_passes_with_speedup_and_done_payload():
    runner = RolloutCanaryRunner(base_url="http://test.local", session=MagicMock())
    rollout_check = runner._build_check(
        name="rollout_status_endpoint",
        passed=True,
        detail="ok",
    )
    runner._get_rollout_status = MagicMock(
        return_value=(
            rollout_check,
            {"feature_flags": {"WATCHLIST_RANKING_ENABLED": True}},
        )
    )
    runner._create_watchlist = MagicMock(return_value=(True, {"id": 77, "_http_status": 200}))
    runner._add_ticker_to_watchlist = MagicMock(return_value=(True, {"_http_status": 200}))
    runner._run_watchlist_sse_analyze = MagicMock(
        return_value={
            "ok": True,
            "http_status": 200,
            "event_counts": {"result": 2, "done": 1},
            "elapsed_seconds": 10.0,
            "done_payload": {"opportunities": []},
        }
    )
    runner._run_sequential_analyses = MagicMock(
        return_value={
            "ok": True,
            "elapsed_seconds": 25.0,
            "success_count": 2,
            "failure_count": 0,
        }
    )
    runner._delete_watchlist = MagicMock(return_value=(True, {"_http_status": 200}))

    summary = runner.run(
        stage="stage_c",
        stage_c_tickers=["AAPL", "MSFT"],
        stage_c_required_speedup=2.0,
    )

    assert summary["passed"] is True
    stage = summary["runs"][0]
    assert stage["stage"] == "stage_c"
    assert stage["failed_checks"] == 0


def test_stage_d_canary_passes_with_pm_api_checks():
    runner = RolloutCanaryRunner(base_url="http://test.local", session=MagicMock())
    rollout_check = runner._build_check(
        name="rollout_status_endpoint",
        passed=True,
        detail="ok",
    )
    runner._get_rollout_status = MagicMock(
        return_value=(
            rollout_check,
            {"feature_flags": {"UI_PM_DASHBOARD_ENABLED": True}},
        )
    )

    called_paths: List[str] = []

    def _request_json_side_effect(method: str, path: str, **kwargs):
        called_paths.append(path)
        if path == "/api/analysis/tickers":
            return True, {"_http_status": 200, "tickers": [{"ticker": "AMZN"}]}
        if path.endswith("/latest"):
            return False, {"_http_status": 404}
        return True, {"_http_status": 200}

    runner._request_json = MagicMock(side_effect=_request_json_side_effect)

    summary = runner.run(stage="stage_d", stage_d_ticker="AAPL")

    assert summary["passed"] is True
    stage = summary["runs"][0]
    assert stage["stage"] == "stage_d"
    assert stage["failed_checks"] == 0
    assert "/api/analysis/AMZN/history/detailed" in called_paths
