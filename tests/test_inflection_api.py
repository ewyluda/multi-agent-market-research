"""Tests for inflection API endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_manager):
    from src.api import app
    import src.api as api_module
    original_db = api_module.db_manager
    api_module.db_manager = db_manager
    yield TestClient(app)
    api_module.db_manager = original_db


class TestInflectionAPI:
    def _seed_data(self, db_manager):
        from src.repositories.perception_repo import PerceptionRepository
        aid1 = db_manager.insert_analysis(
            ticker="AAPL", recommendation="HOLD", confidence_score=0.8,
            overall_sentiment_score=0.5, solution_agent_reasoning="Test.", duration_seconds=10.0,
        )
        aid2 = db_manager.insert_analysis(
            ticker="AAPL", recommendation="BUY", confidence_score=0.85,
            overall_sentiment_score=0.6, solution_agent_reasoning="Test.", duration_seconds=10.0,
        )
        repo = PerceptionRepository(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 25.0, "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.0, "source_agent": "fundamentals", "confidence": 0.9},
        ])
        repo.insert_inflection_events("AAPL", aid2, [{
            "kpi_name": "forward_pe", "direction": "positive", "magnitude": 0.2,
            "prior_value": 25.0, "current_value": 20.0, "pct_change": -20.0,
            "source_agents": ["fundamentals"], "convergence_score": 0.8, "summary": "Forward PE improved -20%",
        }])

    def test_get_inflection_history(self, client, db_manager):
        self._seed_data(db_manager)
        response = client.get("/api/inflections/AAPL")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_get_timeseries(self, client, db_manager):
        self._seed_data(db_manager)
        response = client.get("/api/inflections/AAPL/timeseries?kpis=forward_pe")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_inflection_history_empty(self, client, db_manager):
        response = client.get("/api/inflections/ZZZZ")
        assert response.status_code == 200
        assert response.json() == []
