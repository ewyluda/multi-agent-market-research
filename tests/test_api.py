"""Tests for FastAPI API endpoints."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api import app, db_manager


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


class TestHealthCheck:
    """Tests for GET /health."""

    def test_health_check_returns_200(self, client):
        """GET /health returns 200 with status fields."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database_connected" in data
        assert "config_valid" in data
        assert "timestamp" in data


class TestRootEndpoint:
    """Tests for GET /."""

    def test_root_returns_api_info(self, client):
        """GET / returns API name and endpoint list."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        assert "analyze" in data["endpoints"]
        assert "stream" in data["endpoints"]
        assert "health" in data["endpoints"]


class TestAnalyzeTicker:
    """Tests for POST /api/analyze/{ticker}."""

    def test_invalid_ticker_returns_400(self, client):
        """POST /api/analyze/123 returns 400 for invalid ticker format."""
        response = client.post("/api/analyze/123")
        assert response.status_code == 400
        assert "Invalid ticker" in response.json()["detail"]

    def test_special_chars_ticker_returns_400(self, client):
        """POST /api/analyze/AA-PL returns 400 (special chars not allowed)."""
        response = client.post("/api/analyze/AA-PL")
        assert response.status_code == 400

    def test_too_long_ticker_returns_400(self, client):
        """POST /api/analyze/TOOLONG returns 400."""
        response = client.post("/api/analyze/TOOLONG")
        assert response.status_code == 400

    def test_invalid_agent_name_returns_400(self, client):
        """POST /api/analyze/AAPL?agents=invalid returns 400."""
        response = client.post("/api/analyze/AAPL?agents=invalid_agent")
        assert response.status_code == 400
        assert "Invalid agent names" in response.json()["detail"]

    def test_mixed_valid_invalid_agents_returns_400(self, client):
        """POST with mix of valid/invalid agent names returns 400."""
        response = client.post("/api/analyze/AAPL?agents=market,bogus")
        assert response.status_code == 400

    @patch("src.api.Orchestrator")
    def test_successful_analysis(self, MockOrch, client):
        """POST /api/analyze/AAPL returns 200 on success."""
        instance = MockOrch.return_value
        instance.analyze_ticker = AsyncMock(
            return_value={
                "success": True,
                "ticker": "AAPL",
                "analysis_id": 1,
                "analysis": {
                    "recommendation": "BUY",
                    "score": 50,
                    "confidence": 0.7,
                    "analysis_schema_version": "v2",
                    "signal_contract_v2": {
                        "schema_version": "2.0",
                        "instrument_type": "US_EQUITY",
                        "recommendation": "BUY",
                        "expected_return_pct": {"1d": 1.0, "7d": 7.0, "30d": 30.0},
                        "downside_risk_pct": {"1d": 0.5, "7d": 3.5, "30d": 15.0},
                        "hit_rate": {"1d": 0.6, "7d": 0.6, "30d": 0.6},
                        "ev_score_7d": 2.8,
                        "confidence": {"raw": 0.7, "calibrated": 0.68, "uncertainty_band_pct": 12.0},
                        "risk": {
                            "risk_reward_ratio_7d": 2.0,
                            "max_drawdown_est_pct_7d": 3.5,
                            "data_quality_score": 82.0,
                            "conflict_score": 10.0,
                            "regime_label": "risk_on",
                        },
                        "liquidity": {
                            "avg_dollar_volume_20d": 100000000.0,
                            "est_spread_bps": 12.0,
                            "capacity_usd": 2000000.0,
                        },
                        "execution_plan": {
                            "entry_zone": {"low": 100.0, "high": 102.0, "reference": 101.0},
                            "stop_loss": 96.0,
                            "targets": [108.0, 112.0],
                            "invalidation_conditions": ["Breaks support"],
                            "max_holding_days": 30,
                        },
                        "rationale_summary": "Deterministic summary",
                        "evidence": [],
                    },
                    "ev_score_7d": 2.8,
                    "confidence_calibrated": 0.68,
                    "data_quality_score": 82.0,
                    "regime_label": "risk_on",
                    "rationale_summary": "Deterministic summary",
                    "reasoning": "Strong fundamentals.",
                    "risks": ["Valuation"],
                    "opportunities": ["AI growth"],
                    "summary": "Buy on dips.",
                    "price_targets": None,
                    "position_size": None,
                    "time_horizon": None,
                    "scenarios": {
                        "bull": {"probability": 0.4, "expected_return_pct": 12.0, "thesis": "Upside"},
                        "base": {"probability": 0.4, "expected_return_pct": 4.0, "thesis": "Base"},
                        "bear": {"probability": 0.2, "expected_return_pct": -8.0, "thesis": "Downside"},
                    },
                    "scenario_summary": "Bull 40%; Base 40%; Bear 20%.",
                    "diagnostics": {
                        "disagreement": {"bullish_count": 2, "bearish_count": 1, "neutral_count": 1, "is_conflicted": False},
                        "data_quality": {"agent_success_rate": 1.0, "failed_agents": [], "quality_level": "good", "warnings": []},
                    },
                    "diagnostics_summary": "Signals aligned. Data quality good.",
                },
                "agent_results": {},
                "duration_seconds": 10.0,
            }
        )

        response = client.post("/api/analyze/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ticker"] == "AAPL"
        assert data["analysis"]["recommendation"] == "BUY"
        assert data["analysis"]["analysis_schema_version"] == "v2"
        assert data["analysis"]["signal_contract_v2"]["schema_version"] == "2.0"
        assert data["analysis"]["ev_score_7d"] == 2.8
        assert data["analysis"]["confidence_calibrated"] == 0.68
        assert "scenarios" in data["analysis"]
        assert "diagnostics" in data["analysis"]


class TestGetLatestAnalysis:
    """Tests for GET /api/analysis/{ticker}/latest."""

    def test_not_found_returns_404(self, client):
        """GET /api/analysis/ZZZZ/latest returns 404 when no data exists."""
        response = client.get("/api/analysis/ZZZZ/latest")
        assert response.status_code == 404


class TestGetAnalysisHistory:
    """Tests for GET /api/analysis/{ticker}/history."""

    def test_limit_too_low_returns_400(self, client):
        """GET /api/analysis/AAPL/history?limit=0 returns 400."""
        response = client.get("/api/analysis/AAPL/history?limit=0")
        assert response.status_code == 400

    def test_limit_too_high_returns_400(self, client):
        """GET /api/analysis/AAPL/history?limit=101 returns 400."""
        response = client.get("/api/analysis/AAPL/history?limit=101")
        assert response.status_code == 400

    def test_valid_limit(self, client):
        """GET /api/analysis/AAPL/history?limit=10 returns 200."""
        response = client.get("/api/analysis/AAPL/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "analyses" in data
        assert "total_count" in data

    def test_history_exposes_decision_and_change_fields(self, client):
        """History response includes decision_card/change_summary when present."""
        ticker = "ZZPH1"
        aid = db_manager.insert_analysis(
            ticker=ticker,
            recommendation="BUY",
            confidence_score=0.74,
            overall_sentiment_score=0.2,
            solution_agent_reasoning="Test reasoning.",
            duration_seconds=4.1,
            score=55,
            decision_card={"action": "buy", "targets": [120]},
            change_summary={"summary": "Recommendation changed", "material_changes": [{"type": "recommendation_change"}]},
            analysis_payload={"recommendation": "BUY", "score": 55, "confidence": 0.74},
        )
        try:
            response = client.get(f"/api/analysis/{ticker}/history?limit=1")
            assert response.status_code == 200
            item = response.json()["analyses"][0]
            assert item["score"] == 55
            assert item["decision_card"]["action"] == "buy"
            assert item["change_summary"]["summary"] == "Recommendation changed"
        finally:
            db_manager.delete_analysis(aid)


class TestExportCSV:
    """Tests for GET /api/analysis/{ticker}/export/csv."""

    def test_export_not_found_returns_404(self, client):
        """GET /api/analysis/ZZZZ/export/csv returns 404 when no data exists."""
        response = client.get("/api/analysis/ZZZZ/export/csv")
        assert response.status_code == 404


class TestExportPDF:
    """Tests for GET /api/analysis/{ticker}/export/pdf."""

    def test_pdf_export_not_found_returns_404(self, client):
        """GET /api/analysis/ZZZZ/export/pdf returns 404 when no data exists."""
        response = client.get("/api/analysis/ZZZZ/export/pdf")
        assert response.status_code == 404


class TestSSEStream:
    """Tests for GET /api/analyze/{ticker}/stream."""

    def test_invalid_ticker_returns_400(self, client):
        """GET /api/analyze/123/stream returns 400."""
        response = client.get("/api/analyze/123/stream")
        assert response.status_code == 400

    def test_invalid_agents_returns_400(self, client):
        """GET /api/analyze/AAPL/stream?agents=fake returns 400."""
        response = client.get("/api/analyze/AAPL/stream?agents=fake_agent")
        assert response.status_code == 400


class TestScheduleAPI:
    """Tests for schedule CRUD endpoints."""

    def test_create_schedule(self, client):
        """POST /api/schedules with valid body returns 200."""
        # Use a unique alpha-only ticker unlikely to already have a schedule
        import random
        import string
        ticker = "Z" + "".join(random.choices(string.ascii_uppercase, k=4))
        response = client.post(
            "/api/schedules",
            json={"ticker": ticker, "interval_minutes": 60},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == ticker
        assert data["interval_minutes"] == 60
        assert data["enabled"] is True
        assert "id" in data

        # Clean up: delete the schedule we just created
        client.delete(f"/api/schedules/{data['id']}")

    def test_get_schedules(self, client):
        """GET /api/schedules returns a list."""
        response = client.get("/api/schedules")
        assert response.status_code == 200
        data = response.json()
        assert "schedules" in data
        assert "total_count" in data

    def test_delete_schedule_not_found(self, client):
        """DELETE /api/schedules/999 returns 404."""
        response = client.delete("/api/schedules/999")
        assert response.status_code == 404

    def test_schedule_runs_endpoint_includes_catalyst_fields(self, client):
        """GET /api/schedules/{id}/runs includes run_reason and catalyst metadata fields."""
        import random
        import string

        ticker = "Y" + "".join(random.choices(string.ascii_uppercase, k=4))
        create_resp = client.post(
            "/api/schedules",
            json={"ticker": ticker, "interval_minutes": 60},
        )
        assert create_resp.status_code == 200
        schedule = create_resp.json()
        schedule_id = schedule["id"]

        db_manager.insert_schedule_run(
            schedule_id=schedule_id,
            analysis_id=None,
            started_at="2025-02-15T10:00:00",
            completed_at="2025-02-15T10:01:00",
            success=True,
            run_reason="catalyst_day",
            catalyst_event_type="cpi",
            catalyst_event_date="2025-02-15",
        )

        try:
            runs_resp = client.get(f"/api/schedules/{schedule_id}/runs")
            assert runs_resp.status_code == 200
            runs = runs_resp.json()["runs"]
            assert len(runs) >= 1
            first = runs[0]
            assert "run_reason" in first
            assert "catalyst_event_type" in first
            assert "catalyst_event_date" in first
            assert first["run_reason"] == "catalyst_day"
            assert first["catalyst_event_type"] == "cpi"
        finally:
            client.delete(f"/api/schedules/{schedule_id}")


class TestWatchlistAnalyzeAgents:
    """Tests for watchlist analyze agent filtering."""

    def test_watchlist_analyze_rejects_invalid_agents(self, client):
        import random
        import string

        wl_name = "WL" + "".join(random.choices(string.ascii_uppercase, k=6))
        create_resp = client.post("/api/watchlists", json={"name": wl_name})
        assert create_resp.status_code == 200
        watchlist_id = create_resp.json()["id"]

        try:
            add_resp = client.post(f"/api/watchlists/{watchlist_id}/tickers", json={"ticker": "AAPL"})
            assert add_resp.status_code == 200

            bad_resp = client.post(f"/api/watchlists/{watchlist_id}/analyze?agents=market,bogus_agent")
            assert bad_resp.status_code == 400
            assert "Invalid agent names" in bad_resp.json()["detail"]
        finally:
            client.delete(f"/api/watchlists/{watchlist_id}")


class TestPortfolioMacroCalibrationAPI:
    """Tests for portfolio, macro-event, and calibration endpoints."""

    def test_portfolio_profile_and_holdings_crud(self, client):
        import random
        import string

        portfolio_resp = client.get("/api/portfolio")
        assert portfolio_resp.status_code == 200
        assert "profile" in portfolio_resp.json()
        assert "snapshot" in portfolio_resp.json()

        update_resp = client.put(
            "/api/portfolio/profile",
            json={"name": "Primary Test", "max_position_pct": 0.11},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Primary Test"
        assert update_resp.json()["max_position_pct"] == 0.11

        ticker = "P" + "".join(random.choices(string.ascii_uppercase, k=4))
        create_resp = client.post(
            "/api/portfolio/holdings",
            json={
                "ticker": ticker,
                "shares": 10,
                "avg_cost": 100,
                "market_value": 1000,
                "sector": "Technology",
            },
        )
        assert create_resp.status_code == 200
        holding = create_resp.json()
        holding_id = holding["id"]
        assert holding["ticker"] == ticker

        list_resp = client.get("/api/portfolio/holdings")
        assert list_resp.status_code == 200
        assert any(h["id"] == holding_id for h in list_resp.json()["holdings"])

        patch_resp = client.put(
            f"/api/portfolio/holdings/{holding_id}",
            json={"market_value": 1250},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["market_value"] == 1250

        delete_resp = client.delete(f"/api/portfolio/holdings/{holding_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

    def test_macro_events_endpoint_shape(self, client):
        response = client.get("/api/macro-events?from=2026-01-01&to=2026-12-31")
        assert response.status_code == 200
        payload = response.json()
        assert "events" in payload
        assert "total_count" in payload
        assert isinstance(payload["events"], list)

    def test_calibration_endpoints_return_expected_schema(self, client):
        aid = db_manager.insert_analysis(
            ticker="CLBT",
            recommendation="BUY",
            confidence_score=0.7,
            overall_sentiment_score=0.2,
            solution_agent_reasoning="Calibration endpoint test",
            duration_seconds=2.0,
            score=40,
        )
        try:
            db_manager.create_outcome_rows_for_analysis(
                analysis_id=aid,
                ticker="CLBT",
                baseline_price=100.0,
                confidence=0.7,
                predicted_up_probability=0.65,
            )
            db_manager.upsert_calibration_snapshot(
                as_of_date="2026-02-15",
                horizon_days=1,
                sample_size=5,
                directional_accuracy=0.6,
                avg_realized_return_pct=1.0,
                mean_confidence=0.62,
                brier_score=0.21,
            )

            summary_resp = client.get("/api/calibration/summary?window_days=365")
            assert summary_resp.status_code == 200
            summary = summary_resp.json()
            assert "horizons" in summary
            assert "1d" in summary["horizons"]

            ticker_resp = client.get("/api/calibration/ticker/CLBT?limit=10")
            assert ticker_resp.status_code == 200
            ticker_payload = ticker_resp.json()
            assert ticker_payload["ticker"] == "CLBT"
            assert "outcomes" in ticker_payload
            assert ticker_payload["total_count"] >= 1
        finally:
            db_manager.delete_analysis(aid)


class TestRolloutStatusAPI:
    """Tests for Phase 7 rollout status endpoint."""

    def test_rollout_status_endpoint_returns_gate_payload(self, client):
        response = client.get("/api/rollout/phase7/status?window_hours=24")
        assert response.status_code == 200
        payload = response.json()

        assert "generated_at" in payload
        assert payload["window_hours"] == 24
        assert "since_timestamp" in payload

        assert "metrics" in payload
        assert "scheduled_runs" in payload["metrics"]
        assert "scheduled_analyses" in payload["metrics"]
        assert "all_analyses" in payload["metrics"]
        assert "reliability_bins" in payload["metrics"]
        assert "alert_rules" in payload["metrics"]

        assert "gates" in payload
        assert "stage_a" in payload["gates"]
        assert "stage_b" in payload["gates"]
        assert "stage_c" in payload["gates"]
        assert "stage_d" in payload["gates"]

        assert "feature_flags" in payload
        assert "SIGNAL_CONTRACT_V2_ENABLED" in payload["feature_flags"]
        assert "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED" in payload["feature_flags"]


class TestPortfolioRiskSummary:
    """Tests for GET /api/portfolio/risk-summary."""

    def test_risk_summary_empty_portfolio(self, client):
        """Returns sensible defaults for empty portfolio."""
        response = client.get("/api/portfolio/risk-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio_beta"] == 0.0
        assert data["total_market_value"] == 0.0


class TestAlertAPI:
    """Tests for alert CRUD and notification endpoints."""

    def test_create_alert_rule(self, client):
        """POST /api/alerts with valid body returns 200."""
        response = client.post(
            "/api/alerts",
            json={"ticker": "AAPL", "rule_type": "recommendation_change"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["rule_type"] == "recommendation_change"
        assert data["enabled"] is True
        assert "id" in data

        # Clean up
        client.delete(f"/api/alerts/{data['id']}")

    def test_get_alert_rules(self, client):
        """GET /api/alerts returns a list of rules."""
        response = client.get("/api/alerts")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data

    def test_delete_alert_rule(self, client):
        """DELETE /api/alerts/{id} removes the rule."""
        # Create a rule first
        create_resp = client.post(
            "/api/alerts",
            json={"ticker": "TSLA", "rule_type": "score_above", "threshold": 50},
        )
        rule_id = create_resp.json()["id"]

        # Delete it
        del_resp = client.delete(f"/api/alerts/{rule_id}")
        assert del_resp.status_code == 200

        # Verify it's gone
        get_resp = client.get(f"/api/alerts/{rule_id}")
        assert get_resp.status_code == 404

    def test_get_notifications_empty(self, client):
        """GET /api/alerts/notifications returns empty list when no notifications."""
        response = client.get("/api/alerts/notifications")
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data

    def test_get_unacknowledged_count_zero(self, client):
        """GET /api/alerts/notifications/count returns count."""
        response = client.get("/api/alerts/notifications/count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] >= 0
