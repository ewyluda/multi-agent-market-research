"""Tests for agent API endpoints."""

from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

import pandas as pd
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


class TestRunAnalysis:
    @patch("src.routers.agent_api._get_data_provider")
    @patch("src.routers.agent_api._get_db")
    @patch("src.routers.agent_api.Orchestrator")
    def test_triggers_analysis(self, mock_orch_cls, mock_db, mock_dp, client):
        mock_orch = MagicMock()
        mock_orch.analyze_ticker = AsyncMock(return_value={
            "success": True,
            "analysis_id": 42,
            "analysis": {
                "recommendation": "BUY", "score": 72, "confidence": 0.81,
                "reasoning": "Good.", "risks": [], "opportunities": [],
                "price_targets": {"entry": 185, "target": 210, "stop_loss": 175},
                "position_size": "MEDIUM", "time_horizon": "MEDIUM_TERM",
            },
            "duration_seconds": 15.0,
        })
        mock_orch_cls.return_value = mock_orch
        resp = client.post("/api/agent/AAPL/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["analysis_id"] == 42

    @patch("src.routers.agent_api._get_data_provider")
    @patch("src.routers.agent_api._get_db")
    @patch("src.routers.agent_api.Orchestrator")
    def test_analysis_failure(self, mock_orch_cls, mock_db, mock_dp, client):
        mock_orch = MagicMock()
        mock_orch.analyze_ticker = AsyncMock(return_value={
            "success": False,
            "error": "LLM timeout",
        })
        mock_orch_cls.return_value = mock_orch
        resp = client.post("/api/agent/AAPL/analyze")
        assert resp.status_code == 200
        assert resp.json()["success"] is False


class TestWatchlistEndpoints:
    @patch("src.routers.agent_api._get_db")
    def test_list_watchlists(self, mock_db, client):
        mock_db.return_value.get_watchlists.return_value = [
            {"id": 1, "name": "Tech", "tickers": ["AAPL", "MSFT"]}
        ]
        resp = client.get("/api/agent/watchlists")
        assert resp.status_code == 200
        assert len(resp.json()["watchlists"]) == 1

    @patch("src.routers.agent_api._get_db")
    def test_create_watchlist(self, mock_db, client):
        mock_db.return_value.create_watchlist.return_value = {
            "id": 1, "name": "Tech", "tickers": []
        }
        resp = client.post("/api/agent/watchlists", json={"name": "Tech"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Tech"

    @patch("src.routers.agent_api._get_db")
    def test_delete_watchlist(self, mock_db, client):
        mock_db.return_value.delete_watchlist.return_value = True
        resp = client.delete("/api/agent/watchlists/1")
        assert resp.status_code == 200


class TestAlertEndpoints:
    @patch("src.routers.agent_api._get_db")
    def test_list_alerts(self, mock_db, client):
        mock_db.return_value.get_alert_rules.return_value = [
            {"id": 1, "ticker": "AAPL", "rule_type": "price_change", "threshold": 5.0}
        ]
        resp = client.get("/api/agent/alerts")
        assert resp.status_code == 200
        assert len(resp.json()["alerts"]) == 1

    @patch("src.routers.agent_api._get_db")
    def test_create_alert(self, mock_db, client):
        mock_db.return_value.create_alert_rule.return_value = {
            "id": 1, "ticker": "AAPL", "rule_type": "score_above", "threshold": 50.0
        }
        resp = client.post("/api/agent/alerts", json={
            "ticker": "AAPL", "rule_type": "score_above", "threshold": 50.0
        })
        assert resp.status_code == 200

    def test_create_alert_invalid_rule_type(self, client):
        resp = client.post("/api/agent/alerts", json={
            "ticker": "AAPL", "rule_type": "invalid_type", "threshold": 5.0
        })
        assert resp.status_code == 400

    def test_create_alert_missing_threshold(self, client):
        resp = client.post("/api/agent/alerts", json={
            "ticker": "AAPL", "rule_type": "score_above"
        })
        assert resp.status_code == 400

    @patch("src.routers.agent_api._get_db")
    def test_delete_alert(self, mock_db, client):
        mock_db.return_value.delete_alert_rule.return_value = True
        resp = client.delete("/api/agent/alerts/1")
        assert resp.status_code == 200


class TestPortfolioEndpoints:
    @patch("src.routers.agent_api._get_db")
    def test_get_portfolio(self, mock_db, client):
        mock_db.return_value.get_portfolio_snapshot.return_value = {
            "profile": {}, "by_ticker": {}, "total_market_value": 10000
        }
        mock_db.return_value.list_portfolio_holdings.return_value = [
            {"id": 1, "ticker": "AAPL", "shares": 10, "market_value": 1850}
        ]
        resp = client.get("/api/agent/portfolio")
        assert resp.status_code == 200

    @patch("src.routers.agent_api._get_db")
    def test_add_holding(self, mock_db, client):
        mock_db.return_value.create_portfolio_holding.return_value = {
            "id": 1, "ticker": "AAPL", "shares": 10
        }
        resp = client.post("/api/agent/portfolio", json={
            "ticker": "AAPL", "shares": 10
        })
        assert resp.status_code == 200

    @patch("src.routers.agent_api._get_db")
    def test_delete_holding(self, mock_db, client):
        mock_db.return_value.delete_portfolio_holding.return_value = True
        resp = client.delete("/api/agent/portfolio/1")
        assert resp.status_code == 200


class TestRawDataEndpoints:
    @patch("src.routers.agent_api._get_data_provider")
    def test_get_stock_quote(self, mock_dp, client):
        mock_dp.return_value.get_quote = AsyncMock(return_value={
            "symbol": "AAPL", "price": 185.50, "change": 2.30
        })
        resp = client.get("/api/agent/data/AAPL/quote")
        assert resp.status_code == 200
        assert resp.json()["price"] == 185.5

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_price_history(self, mock_dp, client):
        df = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02"],
            "open": [180.0, 182.0],
            "high": [185.0, 186.0],
            "low": [179.0, 181.0],
            "close": [184.0, 185.0],
            "volume": [1000000, 1100000],
        })
        mock_dp.return_value.get_price_history = AsyncMock(return_value=df)
        resp = client.get("/api/agent/data/AAPL/price-history?period=1m")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_financials(self, mock_dp, client):
        mock_dp.return_value.get_financials = AsyncMock(return_value={
            "revenue": 394000000000, "net_income": 97000000000
        })
        resp = client.get("/api/agent/data/AAPL/financials")
        assert resp.status_code == 200

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_earnings_transcript(self, mock_dp, client):
        mock_dp.return_value.get_earnings_transcript = AsyncMock(return_value={
            "quarter": 1, "year": 2026, "content": "CEO: Good quarter..."
        })
        resp = client.get("/api/agent/data/AAPL/transcript?year=2026&quarter=1")
        assert resp.status_code == 200
        assert resp.json()["quarter"] == 1

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_macro_indicators(self, mock_dp, client):
        mock_dp.return_value.get_macro_indicators = AsyncMock(return_value={
            "fed_funds_rate": {"value": 5.25}
        })
        resp = client.get("/api/agent/data/macro")
        assert resp.status_code == 200

    @patch("src.routers.agent_api._get_data_provider")
    def test_provider_returns_none_gives_404(self, mock_dp, client):
        mock_dp.return_value.get_quote = AsyncMock(return_value=None)
        resp = client.get("/api/agent/data/AAPL/quote")
        assert resp.status_code == 404

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_options_chain(self, mock_dp, client):
        mock_dp.return_value.get_options_chain = AsyncMock(return_value={
            "put_call_ratio": 0.85, "chains": []
        })
        resp = client.get("/api/agent/data/AAPL/options")
        assert resp.status_code == 200

    @patch("src.routers.agent_api._get_data_provider")
    def test_get_sec_filings(self, mock_dp, client):
        mock_dp.return_value.get_sec_filing_metadata = AsyncMock(return_value=[
            {"filing_type": "10-K", "filing_date": "2025-11-01"}
        ])
        resp = client.get("/api/agent/data/AAPL/sec-filings")
        assert resp.status_code == 200
        assert len(resp.json()["filings"]) == 1

    def test_sec_section_rejects_non_edgar_url(self, client):
        resp = client.get(
            "/api/agent/data/AAPL/sec-section",
            params={"filing_url": "http://evil.com/steal-data"},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]["message"]

    @patch("src.routers.agent_api._get_data_provider")
    def test_sec_section_allows_edgar_url(self, mock_dp, client):
        mock_dp.return_value.get_sec_filing_section = AsyncMock(return_value={
            "section_text": "Risk factors...", "char_count": 100
        })
        resp = client.get(
            "/api/agent/data/AAPL/sec-section",
            params={"filing_url": "https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm"},
        )
        assert resp.status_code == 200
