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
                    "reasoning": "Strong fundamentals.",
                    "risks": ["Valuation"],
                    "opportunities": ["AI growth"],
                    "summary": "Buy on dips.",
                    "price_targets": None,
                    "position_size": None,
                    "time_horizon": None,
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
