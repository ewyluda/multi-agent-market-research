"""Phase 7 rollout canary runner for preflight and staged promotion checks."""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_WINDOW_HOURS = 72
DEFAULT_STAGE_C_REQUIRED_SPEEDUP = 1.5
DEFAULT_ANALYZE_TIMEOUT_SECONDS = 240
DEFAULT_STAGE_C_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "JPM",
]


@dataclass
class CanaryCheck:
    """Single canary check result."""

    name: str
    passed: bool
    detail: str
    actual: Any = None
    expected: Any = None


class RolloutCanaryRunner:
    """Runs rollout canary checks against a live API base URL."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.timeout_seconds = int(max(1, timeout_seconds))
        self.session = session or requests.Session()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        expected_status: int = 200,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Execute request and return parsed JSON payload with status metadata."""
        url = f"{self.base_url}{path}"
        request_timeout = int(max(1, timeout_seconds or self.timeout_seconds))
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_body,
                timeout=request_timeout,
            )
        except Exception as exc:
            return False, {
                "error": f"request_failed: {exc}",
                "url": url,
            }

        payload: Dict[str, Any]
        try:
            parsed = response.json()
            payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            payload = {"raw": response.text}

        payload["_http_status"] = int(response.status_code)
        payload["_url"] = url

        if int(response.status_code) != int(expected_status):
            return False, payload
        return True, payload

    def _random_ticker(self, prefix: str = "Z") -> str:
        """Generate a random 5-char ticker string for canary artifacts."""
        suffix = "".join(random.choices(string.ascii_uppercase, k=4))
        return f"{prefix[:1].upper()}{suffix}"

    def _build_check(
        self,
        *,
        name: str,
        passed: bool,
        detail: str,
        actual: Any = None,
        expected: Any = None,
    ) -> CanaryCheck:
        return CanaryCheck(
            name=name,
            passed=bool(passed),
            detail=detail,
            actual=actual,
            expected=expected,
        )

    def _create_watchlist(self, *, name: str) -> Tuple[bool, Dict[str, Any]]:
        """Create watchlist artifact for canary runs."""
        return self._request_json(
            "POST",
            "/api/watchlists",
            expected_status=200,
            json_body={"name": name},
        )

    def _add_ticker_to_watchlist(self, *, watchlist_id: int, ticker: str) -> Tuple[bool, Dict[str, Any]]:
        """Add ticker to watchlist artifact."""
        return self._request_json(
            "POST",
            f"/api/watchlists/{int(watchlist_id)}/tickers",
            expected_status=200,
            json_body={"ticker": str(ticker).upper()},
        )

    def _delete_watchlist(self, *, watchlist_id: int) -> Tuple[bool, Dict[str, Any]]:
        """Delete watchlist artifact."""
        return self._request_json(
            "DELETE",
            f"/api/watchlists/{int(watchlist_id)}",
            expected_status=200,
        )

    def _run_watchlist_sse_analyze(
        self,
        *,
        watchlist_id: int,
        agents: Optional[Sequence[str]] = None,
        max_wait_seconds: int = 900,
    ) -> Dict[str, Any]:
        """Execute watchlist SSE analysis and capture event counts + done payload."""
        url = f"{self.base_url}/api/watchlists/{int(watchlist_id)}/analyze"
        params: Optional[Dict[str, Any]] = None
        if agents:
            normalized = [str(item).strip().lower() for item in agents if str(item).strip()]
            if normalized:
                params = {"agents": ",".join(normalized)}
        event_counts: Dict[str, int] = {}
        errors: List[Any] = []
        done_payload: Optional[Dict[str, Any]] = None

        started = time.perf_counter()
        try:
            response = self.session.request(
                method="POST",
                url=url,
                params=params,
                stream=True,
                timeout=max(30, int(max_wait_seconds)),
            )
        except Exception as exc:
            return {
                "ok": False,
                "http_status": None,
                "error": f"request_failed: {exc}",
                "event_counts": event_counts,
                "done_payload": None,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
            }

        http_status = int(response.status_code)
        if http_status != 200:
            raw = ""
            try:
                raw = response.text
            except Exception:
                raw = ""
            return {
                "ok": False,
                "http_status": http_status,
                "error": f"unexpected_status: {http_status}",
                "raw": raw[:400],
                "event_counts": event_counts,
                "done_payload": None,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
            }

        current_event = "message"
        current_data_lines: List[str] = []

        def _flush_event() -> Optional[Tuple[str, Any]]:
            if not current_data_lines:
                return None
            data_blob = "\n".join(current_data_lines)
            try:
                payload = json.loads(data_blob)
            except json.JSONDecodeError:
                payload = {"raw": data_blob}
            return current_event, payload

        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = str(raw_line)
                if line == "":
                    parsed = _flush_event()
                    current_data_lines = []
                    if not parsed:
                        current_event = "message"
                        continue
                    event_name, payload = parsed
                    event_counts[event_name] = int(event_counts.get(event_name, 0)) + 1
                    if event_name == "error":
                        errors.append(payload)
                    if event_name == "done":
                        done_payload = payload if isinstance(payload, dict) else {"value": payload}
                        break
                    current_event = "message"
                    continue

                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    current_event = line.partition(":")[2].strip() or "message"
                    continue
                if line.startswith("data:"):
                    current_data_lines.append(line.partition(":")[2].lstrip())
                    continue
        finally:
            try:
                response.close()
            except Exception:
                pass

        elapsed = round(time.perf_counter() - started, 4)
        return {
            "ok": done_payload is not None,
            "http_status": http_status,
            "error_count": len(errors),
            "errors": errors[:10],
            "event_counts": event_counts,
            "done_payload": done_payload,
            "elapsed_seconds": elapsed,
        }

    def _run_sequential_analyses(
        self,
        *,
        tickers: Sequence[str],
        agents: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Run sequential baseline analyses for Stage C speedup check."""
        started = time.perf_counter()
        success_count = 0
        failures: List[Dict[str, Any]] = []
        params: Optional[Dict[str, Any]] = None
        if agents:
            normalized = [str(item).strip().lower() for item in agents if str(item).strip()]
            if normalized:
                params = {"agents": ",".join(normalized)}

        for ticker in tickers:
            ok, payload = self._request_json(
                "POST",
                f"/api/analyze/{str(ticker).upper()}",
                expected_status=200,
                params=params,
                timeout_seconds=DEFAULT_ANALYZE_TIMEOUT_SECONDS,
            )
            if ok and bool(payload.get("success")):
                success_count += 1
            else:
                failures.append(
                    {
                        "ticker": str(ticker).upper(),
                        "http_status": payload.get("_http_status"),
                        "error": payload.get("detail") or payload.get("error") or payload.get("raw"),
                    }
                )

        elapsed = round(time.perf_counter() - started, 4)
        return {
            "ok": len(failures) == 0,
            "elapsed_seconds": elapsed,
            "success_count": success_count,
            "failure_count": len(failures),
            "failures": failures[:10],
        }

    def _get_rollout_status(self, *, window_hours: int) -> Tuple[CanaryCheck, Dict[str, Any]]:
        ok, payload = self._request_json(
            "GET",
            "/api/rollout/phase7/status",
            params={"window_hours": int(max(1, window_hours))},
        )
        required_keys = {"metrics", "gates", "feature_flags", "generated_at"}
        has_keys = required_keys.issubset(set(payload.keys()))
        passed = bool(ok and has_keys)
        check = self._build_check(
            name="rollout_status_endpoint",
            passed=passed,
            detail="Rollout status endpoint is reachable and returns required keys.",
            actual={"http_status": payload.get("_http_status"), "keys": sorted(list(payload.keys()))[:12]},
            expected={"http_status": 200, "keys_include": sorted(required_keys)},
        )
        return check, payload

    def run_preflight(self, *, strict_flag_posture: bool = True) -> Dict[str, Any]:
        """Run Day-0 preflight checks."""
        checks: List[CanaryCheck] = []

        health_ok, health_payload = self._request_json("GET", "/health")
        health_status = str(health_payload.get("status") or "").lower()
        health_passed = bool(
            health_ok
            and health_status == "healthy"
            and bool(health_payload.get("database_connected"))
            and bool(health_payload.get("config_valid"))
        )
        checks.append(
            self._build_check(
                name="health_endpoint",
                passed=health_passed,
                detail="Service health, DB connectivity, and config validity are healthy.",
                actual={
                    "http_status": health_payload.get("_http_status"),
                    "status": health_payload.get("status"),
                    "database_connected": health_payload.get("database_connected"),
                    "config_valid": health_payload.get("config_valid"),
                },
                expected={
                    "http_status": 200,
                    "status": "healthy",
                    "database_connected": True,
                    "config_valid": True,
                },
            )
        )

        rollout_check, rollout_payload = self._get_rollout_status(window_hours=24)
        checks.append(rollout_check)

        if strict_flag_posture:
            flags = rollout_payload.get("feature_flags") or {}
            expected_false = [
                "SIGNAL_CONTRACT_V2_ENABLED",
                "CALIBRATION_ECONOMICS_ENABLED",
                "PORTFOLIO_OPTIMIZER_V2_ENABLED",
                "ALERTS_V2_ENABLED",
                "WATCHLIST_RANKING_ENABLED",
                "UI_PM_DASHBOARD_ENABLED",
                "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED",
                "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED",
                "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED",
                "SCHEDULED_ALERTS_V2_ENABLED",
            ]
            for key in expected_false:
                actual = bool(flags.get(key))
                checks.append(
                    self._build_check(
                        name=f"flag_preflight_{key.lower()}",
                        passed=(actual is False),
                        detail=f"Preflight expected `{key}=false`.",
                        actual=actual,
                        expected=False,
                    )
                )

        return self._summarize(stage="preflight", checks=checks)

    def run_stage_a(self, *, window_hours: int = DEFAULT_WINDOW_HOURS) -> Dict[str, Any]:
        """Run Stage A checks (scheduled-only signal/calibration rollout)."""
        checks: List[CanaryCheck] = []

        rollout_check, rollout_payload = self._get_rollout_status(window_hours=window_hours)
        checks.append(rollout_check)

        stage_a = (rollout_payload.get("gates") or {}).get("stage_a") or {}
        checks.append(
            self._build_check(
                name="stage_a_gate_status",
                passed=bool(stage_a.get("passed")),
                detail="Stage A computed gate status from rollout metrics endpoint.",
                actual=stage_a.get("passed"),
                expected=True,
            )
        )

        flags = rollout_payload.get("feature_flags") or {}
        expected_flags = {
            "SIGNAL_CONTRACT_V2_ENABLED": False,
            "CALIBRATION_ECONOMICS_ENABLED": False,
            "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": True,
            "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
            "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "SCHEDULED_ALERTS_V2_ENABLED": False,
        }
        for key, expected in expected_flags.items():
            actual = bool(flags.get(key))
            checks.append(
                self._build_check(
                    name=f"flag_stage_a_{key.lower()}",
                    passed=(actual is expected),
                    detail=f"Stage A expected `{key}={str(expected).lower()}`.",
                    actual=actual,
                    expected=expected,
                )
            )

        non_empty_horizons: List[int] = []
        for horizon in (1, 7, 30):
            ok, payload = self._request_json(
                "GET",
                "/api/calibration/reliability",
                params={"horizon_days": horizon},
            )
            bins = payload.get("bins") if isinstance(payload, dict) else []
            if bool(ok) and isinstance(bins, list) and len(bins) > 0:
                non_empty_horizons.append(horizon)

        checks.append(
            self._build_check(
                name="stage_a_reliability_non_empty",
                passed=(len(non_empty_horizons) >= 1),
                detail="At least one reliability horizon returns non-empty bins.",
                actual=non_empty_horizons,
                expected=">=1 non-empty horizon from [1,7,30]",
            )
        )

        return self._summarize(stage="stage_a", checks=checks)

    def run_stage_b(self, *, window_hours: int = DEFAULT_WINDOW_HOURS) -> Dict[str, Any]:
        """Run Stage B checks (optimizer/alerts internal rollout)."""
        checks: List[CanaryCheck] = []
        cleanup_rule_ids: List[int] = []

        rollout_check, rollout_payload = self._get_rollout_status(window_hours=window_hours)
        checks.append(rollout_check)

        stage_b = (rollout_payload.get("gates") or {}).get("stage_b") or {}
        checks.append(
            self._build_check(
                name="stage_b_gate_status",
                passed=bool(stage_b.get("passed")),
                detail="Stage B computed gate status from rollout metrics endpoint.",
                actual=stage_b.get("passed"),
                expected=True,
            )
        )

        flags = rollout_payload.get("feature_flags") or {}
        expected_flags = {
            "PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
            "ALERTS_V2_ENABLED": True,
        }
        for key, expected in expected_flags.items():
            actual = bool(flags.get(key))
            checks.append(
                self._build_check(
                    name=f"flag_stage_b_{key.lower()}",
                    passed=(actual is expected),
                    detail=f"Stage B expected `{key}={str(expected).lower()}`.",
                    actual=actual,
                    expected=expected,
                )
            )

        # v2 alert CRUD canary
        v2_ticker = self._random_ticker(prefix="Q")
        ok, payload = self._request_json(
            "POST",
            "/api/alerts",
            expected_status=200,
            json_body={"ticker": v2_ticker, "rule_type": "ev_above", "threshold": 0.1},
        )
        rule_id = payload.get("id")
        if ok and isinstance(rule_id, int):
            cleanup_rule_ids.append(rule_id)
        checks.append(
            self._build_check(
                name="stage_b_alert_v2_create",
                passed=bool(ok and isinstance(rule_id, int)),
                detail="Create v2 alert rule (`ev_above`) succeeds.",
                actual={"http_status": payload.get("_http_status"), "id": rule_id},
                expected={"http_status": 200, "id": "int"},
            )
        )

        if isinstance(rule_id, int):
            ok_get, get_payload = self._request_json("GET", f"/api/alerts/{rule_id}")
            checks.append(
                self._build_check(
                    name="stage_b_alert_v2_get",
                    passed=bool(ok_get and get_payload.get("rule_type") == "ev_above"),
                    detail="Read-back v2 alert rule succeeds.",
                    actual={"http_status": get_payload.get("_http_status"), "rule_type": get_payload.get("rule_type")},
                    expected={"http_status": 200, "rule_type": "ev_above"},
                )
            )

        # Legacy alert rule should still work unchanged.
        legacy_ticker = self._random_ticker(prefix="L")
        ok_legacy, legacy_payload = self._request_json(
            "POST",
            "/api/alerts",
            expected_status=200,
            json_body={"ticker": legacy_ticker, "rule_type": "recommendation_change"},
        )
        legacy_rule_id = legacy_payload.get("id")
        if ok_legacy and isinstance(legacy_rule_id, int):
            cleanup_rule_ids.append(legacy_rule_id)
        checks.append(
            self._build_check(
                name="stage_b_alert_legacy_create",
                passed=bool(ok_legacy and isinstance(legacy_rule_id, int)),
                detail="Create legacy alert rule (`recommendation_change`) still succeeds.",
                actual={"http_status": legacy_payload.get("_http_status"), "id": legacy_rule_id},
                expected={"http_status": 200, "id": "int"},
            )
        )

        # Cleanup created rules; cleanup failures are surfaced but do not invalidate the gate by default.
        for created_rule_id in cleanup_rule_ids:
            ok_del, del_payload = self._request_json(
                "DELETE",
                f"/api/alerts/{created_rule_id}",
                expected_status=200,
            )
            checks.append(
                self._build_check(
                    name=f"stage_b_cleanup_alert_{created_rule_id}",
                    passed=bool(ok_del),
                    detail="Cleanup alert rule artifact.",
                    actual={"http_status": del_payload.get("_http_status"), "deleted_id": del_payload.get("deleted_id")},
                    expected={"http_status": 200},
                )
            )

        return self._summarize(stage="stage_b", checks=checks)

    def run_stage_c(
        self,
        *,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        tickers: Optional[Sequence[str]] = None,
        agents: Optional[Sequence[str]] = None,
        run_benchmark: bool = True,
        required_speedup: float = DEFAULT_STAGE_C_REQUIRED_SPEEDUP,
    ) -> Dict[str, Any]:
        """Run Stage C checks (watchlist ranking + bounded concurrency behavior)."""
        checks: List[CanaryCheck] = []
        cleanup_watchlist_id: Optional[int] = None

        stage_tickers = [str(item).upper() for item in (tickers or DEFAULT_STAGE_C_TICKERS) if str(item).strip()]
        if not stage_tickers:
            stage_tickers = list(DEFAULT_STAGE_C_TICKERS)
        stage_agents = [str(item).strip().lower() for item in (agents or []) if str(item).strip()]
        if stage_agents:
            valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options"}
            stage_agents = [agent for agent in stage_agents if agent in valid_agents]

        rollout_check, rollout_payload = self._get_rollout_status(window_hours=window_hours)
        checks.append(rollout_check)

        flags = rollout_payload.get("feature_flags") or {}
        watchlist_flag = bool(flags.get("WATCHLIST_RANKING_ENABLED"))
        checks.append(
            self._build_check(
                name="flag_stage_c_watchlist_ranking_enabled",
                passed=(watchlist_flag is True),
                detail="Stage C expected `WATCHLIST_RANKING_ENABLED=true`.",
                actual=watchlist_flag,
                expected=True,
            )
        )

        wl_name = f"canary-stage-c-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._random_ticker('C')}"
        ok_create, create_payload = self._create_watchlist(name=wl_name)
        watchlist_id = create_payload.get("id")
        if ok_create and isinstance(watchlist_id, int):
            cleanup_watchlist_id = watchlist_id
        checks.append(
            self._build_check(
                name="stage_c_create_watchlist",
                passed=bool(ok_create and isinstance(watchlist_id, int)),
                detail="Create temporary watchlist for Stage C canary.",
                actual={"http_status": create_payload.get("_http_status"), "id": watchlist_id},
                expected={"http_status": 200, "id": "int"},
            )
        )

        add_success_count = 0
        if isinstance(watchlist_id, int):
            for ticker in stage_tickers:
                ok_add, add_payload = self._add_ticker_to_watchlist(watchlist_id=watchlist_id, ticker=ticker)
                if ok_add:
                    add_success_count += 1
                checks.append(
                    self._build_check(
                        name=f"stage_c_add_ticker_{ticker}",
                        passed=bool(ok_add),
                        detail="Add ticker to Stage C watchlist artifact.",
                        actual={"http_status": add_payload.get("_http_status"), "ticker": ticker},
                        expected={"http_status": 200},
                    )
                )

        sse_result: Dict[str, Any] = {}
        if isinstance(watchlist_id, int):
            sse_result = self._run_watchlist_sse_analyze(
                watchlist_id=watchlist_id,
                agents=stage_agents,
            )
            done_payload = sse_result.get("done_payload") if isinstance(sse_result, dict) else None
            opportunities = (done_payload or {}).get("opportunities") if isinstance(done_payload, dict) else None
            checks.append(
                self._build_check(
                    name="stage_c_watchlist_done_event",
                    passed=bool(sse_result.get("ok")),
                    detail="Watchlist SSE emits `done` event.",
                    actual={
                        "http_status": sse_result.get("http_status"),
                        "event_counts": sse_result.get("event_counts"),
                        "elapsed_seconds": sse_result.get("elapsed_seconds"),
                    },
                    expected={"http_status": 200, "done_event": True},
                )
            )
            checks.append(
                self._build_check(
                    name="stage_c_watchlist_done_opportunities",
                    passed=isinstance(opportunities, list),
                    detail="Watchlist `done` payload includes `opportunities` array.",
                    actual={"opportunities_type": type(opportunities).__name__, "count": len(opportunities or [])},
                    expected={"opportunities_type": "list"},
                )
            )

        if run_benchmark and isinstance(watchlist_id, int):
            sequential = self._run_sequential_analyses(
                tickers=stage_tickers,
                agents=stage_agents,
            )
            watchlist_elapsed = float(sse_result.get("elapsed_seconds") or 0.0)
            sequential_elapsed = float(sequential.get("elapsed_seconds") or 0.0)
            speedup = None
            if watchlist_elapsed > 0:
                speedup = sequential_elapsed / watchlist_elapsed
            checks.append(
                self._build_check(
                    name="stage_c_sequential_baseline_success",
                    passed=bool(sequential.get("ok")),
                    detail="Sequential baseline analyses completed without hard failures.",
                    actual={
                        "elapsed_seconds": sequential_elapsed,
                        "success_count": sequential.get("success_count"),
                        "failure_count": sequential.get("failure_count"),
                    },
                    expected={"failure_count": 0},
                )
            )
            checks.append(
                self._build_check(
                    name="stage_c_speedup_ratio",
                    passed=((speedup is not None) and (speedup >= float(required_speedup))),
                    detail="Watchlist runtime speedup versus sequential baseline.",
                    actual={
                        "speedup": round(float(speedup), 4) if speedup is not None else None,
                        "watchlist_elapsed_seconds": watchlist_elapsed,
                        "sequential_elapsed_seconds": sequential_elapsed,
                        "ticker_count": len(stage_tickers),
                    },
                    expected={">= speedup": float(required_speedup)},
                )
            )
        else:
            checks.append(
                self._build_check(
                    name="stage_c_speedup_ratio",
                    passed=False,
                    detail="Speedup benchmark skipped; rerun with benchmark enabled for promotion gate.",
                    actual={"run_benchmark": run_benchmark},
                    expected={"run_benchmark": True},
                )
            )

        if isinstance(cleanup_watchlist_id, int):
            ok_del, del_payload = self._delete_watchlist(watchlist_id=cleanup_watchlist_id)
            checks.append(
                self._build_check(
                    name=f"stage_c_cleanup_watchlist_{cleanup_watchlist_id}",
                    passed=bool(ok_del),
                    detail="Cleanup watchlist artifact.",
                    actual={"http_status": del_payload.get("_http_status")},
                    expected={"http_status": 200},
                )
            )

        return self._summarize(stage="stage_c", checks=checks)

    def run_stage_d(
        self,
        *,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        frontend_url: Optional[str] = None,
        analysis_ticker: str = "AAPL",
    ) -> Dict[str, Any]:
        """Run Stage D checks (PM dashboard critical path backend dependencies)."""
        checks: List[CanaryCheck] = []

        rollout_check, rollout_payload = self._get_rollout_status(window_hours=window_hours)
        checks.append(rollout_check)

        flags = rollout_payload.get("feature_flags") or {}
        ui_flag = bool(flags.get("UI_PM_DASHBOARD_ENABLED"))
        checks.append(
            self._build_check(
                name="flag_stage_d_ui_pm_dashboard_enabled",
                passed=(ui_flag is True),
                detail="Stage D expected `UI_PM_DASHBOARD_ENABLED=true`.",
                actual=ui_flag,
                expected=True,
            )
        )

        endpoint_checks = [
            ("stage_d_api_watchlists", "GET", "/api/watchlists"),
            ("stage_d_api_alerts", "GET", "/api/alerts"),
            ("stage_d_api_portfolio", "GET", "/api/portfolio"),
            ("stage_d_api_analysis_tickers", "GET", "/api/analysis/tickers"),
            ("stage_d_api_calibration_summary", "GET", "/api/calibration/summary?window_days=180"),
        ]
        for name, method, path in endpoint_checks:
            ok, payload = self._request_json(method, path, expected_status=200)
            checks.append(
                self._build_check(
                    name=name,
                    passed=bool(ok),
                    detail="PM-critical API endpoint responds successfully.",
                    actual={"http_status": payload.get("_http_status")},
                    expected={"http_status": 200},
                )
            )

        ticker_for_history = str(analysis_ticker or "AAPL").upper()
        ok_tickers, tickers_payload = self._request_json("GET", "/api/analysis/tickers", expected_status=200)
        if ok_tickers:
            tickers = tickers_payload.get("tickers") or []
            if isinstance(tickers, list) and tickers:
                first = tickers[0]
                if isinstance(first, str):
                    ticker_for_history = first.upper()
                elif isinstance(first, dict):
                    ticker_value = first.get("ticker") or first.get("TICKER")
                    if ticker_value:
                        ticker_for_history = str(ticker_value).upper()

        ok_hist, hist_payload = self._request_json(
            "GET",
            f"/api/analysis/{ticker_for_history}/history/detailed",
            params={"limit": 1},
            expected_status=200,
        )
        checks.append(
            self._build_check(
                name="stage_d_api_history_detailed",
                passed=bool(ok_hist),
                detail="History detailed endpoint available for PM dashboard history view.",
                actual={"http_status": hist_payload.get("_http_status"), "ticker": ticker_for_history},
                expected={"http_status": 200},
            )
        )

        ok_latest, latest_payload = self._request_json(
            "GET",
            f"/api/analysis/{ticker_for_history}/latest",
            expected_status=200,
        )
        latest_status = int(latest_payload.get("_http_status") or 0)
        checks.append(
            self._build_check(
                name="stage_d_api_latest_route",
                passed=bool(ok_latest or latest_status == 404),
                detail="Latest-analysis route reachable (200 with data or 404 when no data).",
                actual={"http_status": latest_status, "ticker": ticker_for_history},
                expected={"http_status": "200_or_404"},
            )
        )

        if frontend_url:
            url = str(frontend_url).rstrip("/")
            try:
                response = self.session.request(
                    method="GET",
                    url=url,
                    timeout=self.timeout_seconds,
                )
                status_code = int(response.status_code)
                body = response.text or ""
                ui_ok = (status_code == 200) and ("<html" in body.lower() or "id=\"root\"" in body.lower())
                checks.append(
                    self._build_check(
                        name="stage_d_frontend_reachable",
                        passed=ui_ok,
                        detail="Frontend URL reachable and serving HTML shell.",
                        actual={"http_status": status_code},
                        expected={"http_status": 200},
                    )
                )
            except Exception as exc:
                checks.append(
                    self._build_check(
                        name="stage_d_frontend_reachable",
                        passed=False,
                        detail="Frontend URL reachable and serving HTML shell.",
                        actual={"error": str(exc)},
                        expected={"http_status": 200},
                    )
                )

        return self._summarize(stage="stage_d", checks=checks)

    def run(
        self,
        *,
        stage: str,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        strict_flag_posture: bool = True,
        stage_c_tickers: Optional[Sequence[str]] = None,
        stage_c_agents: Optional[Sequence[str]] = None,
        stage_c_run_benchmark: bool = True,
        stage_c_required_speedup: float = DEFAULT_STAGE_C_REQUIRED_SPEEDUP,
        frontend_url: Optional[str] = None,
        stage_d_ticker: str = "AAPL",
    ) -> Dict[str, Any]:
        """Run selected stage canaries and return an aggregate summary."""
        stage_name = str(stage or "").strip().lower()
        if stage_name not in {"preflight", "stage_a", "stage_b", "stage_c", "stage_d", "all"}:
            raise ValueError("stage must be one of: preflight, stage_a, stage_b, stage_c, stage_d, all")

        runs: List[Dict[str, Any]] = []
        if stage_name in {"preflight", "all"}:
            runs.append(self.run_preflight(strict_flag_posture=strict_flag_posture))
        if stage_name in {"stage_a", "all"}:
            runs.append(self.run_stage_a(window_hours=window_hours))
        if stage_name in {"stage_b", "all"}:
            runs.append(self.run_stage_b(window_hours=window_hours))
        if stage_name in {"stage_c", "all"}:
            runs.append(
                self.run_stage_c(
                    window_hours=window_hours,
                    tickers=stage_c_tickers,
                    agents=stage_c_agents,
                    run_benchmark=stage_c_run_benchmark,
                    required_speedup=stage_c_required_speedup,
                )
            )
        if stage_name in {"stage_d", "all"}:
            runs.append(
                self.run_stage_d(
                    window_hours=window_hours,
                    frontend_url=frontend_url,
                    analysis_ticker=stage_d_ticker,
                )
            )

        all_checks: List[Dict[str, Any]] = []
        for run in runs:
            all_checks.extend(run.get("checks", []))

        passed_count = sum(1 for check in all_checks if bool(check.get("passed")))
        failed_count = len(all_checks) - passed_count
        aggregate_passed = failed_count == 0

        return {
            "base_url": self.base_url,
            "requested_stage": stage_name,
            "window_hours": int(max(1, window_hours)),
            "stage_c_tickers": [str(item).upper() for item in (stage_c_tickers or DEFAULT_STAGE_C_TICKERS)],
            "stage_c_agents": [str(item).strip().lower() for item in (stage_c_agents or []) if str(item).strip()],
            "stage_c_run_benchmark": bool(stage_c_run_benchmark),
            "stage_c_required_speedup": float(stage_c_required_speedup),
            "frontend_url": frontend_url,
            "stage_d_ticker": str(stage_d_ticker or "AAPL").upper(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "passed": aggregate_passed,
            "passed_checks": passed_count,
            "failed_checks": failed_count,
            "runs": runs,
        }

    def _summarize(self, *, stage: str, checks: Sequence[CanaryCheck]) -> Dict[str, Any]:
        """Build summary payload for one stage run."""
        rendered_checks = [asdict(check) for check in checks]
        failed = [item for item in rendered_checks if not bool(item.get("passed"))]
        return {
            "stage": stage,
            "passed": len(failed) == 0,
            "total_checks": len(rendered_checks),
            "failed_checks": len(failed),
            "checks": rendered_checks,
        }


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI arg parser for canary runner."""
    parser = argparse.ArgumentParser(description="Phase 7 rollout canary runner")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--stage",
        default="all",
        choices=["preflight", "stage_a", "stage_b", "stage_c", "stage_d", "all"],
        help="Canary stage to run (default: all)",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=DEFAULT_WINDOW_HOURS,
        help="Rollout metrics lookback window in hours (default: 72)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout per request in seconds (default: 20)",
    )
    parser.add_argument(
        "--no-strict-flag-posture",
        action="store_true",
        help="Do not enforce preflight all-flags-false posture.",
    )
    parser.add_argument(
        "--stage-c-tickers",
        default=",".join(DEFAULT_STAGE_C_TICKERS),
        help="Comma-separated tickers for Stage C watchlist benchmark (default: 8 liquid US equities).",
    )
    parser.add_argument(
        "--stage-c-agents",
        default="",
        help=(
            "Optional comma-separated agent subset for Stage C runs "
            "(e.g. market,technical). Empty means all agents."
        ),
    )
    parser.add_argument(
        "--stage-c-required-speedup",
        type=float,
        default=DEFAULT_STAGE_C_REQUIRED_SPEEDUP,
        help="Minimum Stage C speedup ratio versus sequential baseline (default: 1.5).",
    )
    parser.add_argument(
        "--stage-c-skip-benchmark",
        action="store_true",
        help="Skip Stage C sequential-vs-watchlist speedup benchmark.",
    )
    parser.add_argument(
        "--frontend-url",
        default=None,
        help="Optional frontend URL for Stage D availability check (e.g. http://localhost:5173).",
    )
    parser.add_argument(
        "--stage-d-ticker",
        default="AAPL",
        help="Fallback ticker for Stage D history/latest route checks (default: AAPL).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    runner = RolloutCanaryRunner(
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
    )
    stage_c_tickers = [part.strip().upper() for part in str(args.stage_c_tickers).split(",") if part.strip()]
    stage_c_agents = [part.strip().lower() for part in str(args.stage_c_agents).split(",") if part.strip()]
    summary = runner.run(
        stage=args.stage,
        window_hours=args.window_hours,
        strict_flag_posture=not bool(args.no_strict_flag_posture),
        stage_c_tickers=stage_c_tickers,
        stage_c_agents=stage_c_agents,
        stage_c_run_benchmark=not bool(args.stage_c_skip_benchmark),
        stage_c_required_speedup=float(args.stage_c_required_speedup),
        frontend_url=args.frontend_url,
        stage_d_ticker=str(args.stage_d_ticker or "AAPL"),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if bool(summary.get("passed")) else 1


if __name__ == "__main__":
    sys.exit(main())
