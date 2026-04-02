"""Tests for tag screening and CRUD API endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Mock the db_manager on the app state."""
    mock = MagicMock()
    monkeypatch.setattr(app.state, "db_manager", mock, raising=False)
    # Also set app.state.db_manager for endpoints that use it
    if not hasattr(app.state, "db_manager"):
        app.state.db_manager = mock
    return mock


class TestScreenEndpoint:
    """Tests for GET /api/screen."""

    def test_screen_returns_matching_tickers(self, client, mock_db):
        mock_db.screen_by_tags.return_value = [
            {"ticker": "AAPL", "matching_tags": 2, "total_tags": 5, "tags": []},
        ]
        response = client.get("/api/screen?tags=recurring_revenue,pricing_power")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["ticker"] == "AAPL"
        mock_db.screen_by_tags.assert_called_once_with(
            ["recurring_revenue", "pricing_power"], max_age_days=None
        )

    def test_screen_with_max_age(self, client, mock_db):
        mock_db.screen_by_tags.return_value = []
        response = client.get("/api/screen?tags=recurring_revenue&max_age_days=90")
        assert response.status_code == 200
        mock_db.screen_by_tags.assert_called_once_with(
            ["recurring_revenue"], max_age_days=90
        )

    def test_screen_missing_tags_param(self, client):
        response = client.get("/api/screen")
        assert response.status_code == 422 or response.status_code == 400


class TestGetTagsEndpoint:
    """Tests for GET /api/tags/{ticker}."""

    def test_get_tags_returns_list(self, client, mock_db):
        mock_db.get_company_tags.return_value = [
            {"tag": "recurring_revenue", "category": "business_model", "evidence": "Subs",
             "first_seen": "2025-01-01", "last_seen": "2025-06-01"},
        ]
        response = client.get("/api/tags/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["count"] == 1
        assert data["tags"][0]["tag"] == "recurring_revenue"

    def test_get_tags_empty(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.get("/api/tags/UNKNOWN")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestPostTagsEndpoint:
    """Tests for POST /api/tags/{ticker}."""

    def test_add_tags(self, client, mock_db):
        mock_db.get_company_tags.return_value = [
            {"tag": "activist_involved", "category": "corporate_events", "evidence": "Icahn 5%",
             "first_seen": "2025-01-01", "last_seen": "2025-06-01"},
        ]
        response = client.post("/api/tags/AAPL", json={
            "add": [{"tag": "activist_involved", "evidence": "Carl Icahn disclosed 5% stake"}],
        })
        assert response.status_code == 200
        mock_db.upsert_company_tags.assert_called_once()

    def test_remove_tags(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.post("/api/tags/AAPL", json={
            "remove": ["ipo_recent"],
        })
        assert response.status_code == 200
        mock_db.delete_company_tags.assert_called_once_with("AAPL", ["ipo_recent"])

    def test_add_invalid_tag_rejected(self, client, mock_db):
        mock_db.get_company_tags.return_value = []
        response = client.post("/api/tags/AAPL", json={
            "add": [{"tag": "made_up_tag", "evidence": "Fake"}],
        })
        assert response.status_code == 400 or response.status_code == 422
