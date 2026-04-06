"""Tests for agent API endpoints."""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_analysis_record(ticker="AAPL", **overrides):
    """Create a mock analysis record matching db_manager output."""
    base = {
        "id": 1,
        "ticker": ticker,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendation": "BUY",
        "confidence_score": 0.81,
        "overall_sentiment_score": 0.62,
        "score": 72.0,
        "ev_score_7d": 1.2,
        "confidence_calibrated": 0.74,
        "data_quality_score": 87.0,
        "regime_label": "risk_on",
        "rationale_summary": "Strong fundamentals.",
        "solution_agent_reasoning": "Growth metrics look solid.",
        "decision_card": None,
        "signal_contract_v2": None,
        "analysis": {
            "recommendation": "BUY",
            "score": 72,
            "confidence": 0.81,
            "reasoning": "Growth metrics look solid.",
            "risks": ["Risk 1", "Risk 2"],
            "opportunities": ["Opp 1"],
            "price_targets": {"entry": 185.0, "target": 210.0, "stop_loss": 175.0},
            "position_size": "MEDIUM",
            "time_horizon": "MEDIUM_TERM",
            "signal_contract_v2": None,
        },
        "agent_results": {
            "fundamentals": {
                "success": True,
                "data": {"health_score": 82, "summary": "Solid."},
                "duration_seconds": 2.5,
            },
            "sentiment": {
                "success": True,
                "data": {"overall_sentiment": 0.62, "summary": "Positive."},
                "duration_seconds": 3.1,
            },
        },
    }
    base.update(overrides)
    return base


class TestGetTickerSummary:
    @patch("src.routers.agent_api._get_db")
    def test_returns_summary(self, mock_db, client):
        mock_db.return_value.get_latest_analysis.return_value = {"id": 1, "ticker": "AAPL"}
        mock_db.return_value.get_analysis_with_agents.return_value = _mock_analysis_record()
        resp = client.get("/api/agent/AAPL/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["recommendation"] == "BUY"
        assert "data_age_minutes" in data

    @patch("src.routers.agent_api._get_db")
    def test_no_analysis_returns_error(self, mock_db, client):
        mock_db.return_value.get_latest_analysis.return_value = None
        resp = client.get("/api/agent/AAPL/summary")
        assert resp.status_code == 404
        data = resp.json()["detail"]
        assert data["error"] is True
        assert data["suggestion"] == "run_analysis"

    def test_invalid_ticker_returns_400(self, client):
        resp = client.get("/api/agent/123/summary")
        assert resp.status_code == 400


class TestGetTickerAnalysis:
    @patch("src.routers.agent_api._get_db")
    def test_standard_detail(self, mock_db, client):
        mock_db.return_value.get_latest_analysis.return_value = {"id": 1}
        mock_db.return_value.get_analysis_with_agents.return_value = _mock_analysis_record()
        resp = client.get("/api/agent/AAPL/analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data

    @patch("src.routers.agent_api._get_db")
    def test_section_filtering(self, mock_db, client):
        mock_db.return_value.get_latest_analysis.return_value = {"id": 1}
        mock_db.return_value.get_analysis_with_agents.return_value = _mock_analysis_record()
        resp = client.get("/api/agent/AAPL/analysis?sections=sentiment")
        data = resp.json()
        assert "sentiment" in data["agents"]
        assert "fundamentals" not in data["agents"]


class TestGetTickerChanges:
    @patch("src.routers.agent_api._get_db")
    def test_with_previous(self, mock_db, client):
        history = [
            _mock_analysis_record(recommendation="BUY", score=72.0),
            _mock_analysis_record(recommendation="HOLD", score=50.0),
        ]
        mock_db.return_value.get_analysis_history.return_value = history
        mock_db.return_value.get_analysis_with_agents.side_effect = lambda id: history[0] if id == history[0]["id"] else history[1]
        resp = client.get("/api/agent/AAPL/changes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation_changed"] is True


class TestCompare:
    @patch("src.routers.agent_api._get_db")
    def test_compare_two_tickers(self, mock_db, client):
        mock_db.return_value.get_latest_analysis.side_effect = lambda t: {"id": 1, "ticker": t}
        mock_db.return_value.get_analysis_with_agents.return_value = _mock_analysis_record()
        resp = client.get("/api/agent/compare?tickers=AAPL,MSFT")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tickers"]) == 2

    def test_too_many_tickers_returns_400(self, client):
        resp = client.get("/api/agent/compare?tickers=A,B,C,D,E,F")
        assert resp.status_code == 400
