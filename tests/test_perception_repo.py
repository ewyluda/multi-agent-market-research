"""Tests for perception snapshot and inflection event persistence."""

import sqlite3
import pytest
from src.database import DatabaseManager


class TestPerceptionSchema:
    """Tests for perception ledger database schema."""

    def test_perception_snapshots_table_exists(self, db_manager, tmp_db_path):
        """perception_snapshots table is created on init."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "perception_snapshots" in tables

    def test_inflection_events_table_exists(self, db_manager, tmp_db_path):
        """inflection_events table is created on init."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "inflection_events" in tables

    def test_perception_indexes_exist(self, db_manager, tmp_db_path):
        """Perception indexes are created."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "idx_perception_ticker_kpi" in indexes
        assert "idx_perception_analysis" in indexes
        assert "idx_inflection_ticker" in indexes
        assert "idx_inflection_convergence" in indexes


from src.repositories.perception_repo import PerceptionRepository


class TestPerceptionRepository:
    """Tests for PerceptionRepository CRUD operations."""

    def _make_repo(self, db_manager):
        return PerceptionRepository(db_manager)

    def _insert_analysis(self, db_manager, ticker="AAPL"):
        return db_manager.insert_analysis(
            ticker=ticker,
            recommendation="BUY",
            confidence_score=0.8,
            overall_sentiment_score=0.5,
            solution_agent_reasoning="Test.",
            duration_seconds=10.0,
        )

    def test_insert_snapshots(self, db_manager):
        """Snapshots are persisted and retrievable."""
        repo = self._make_repo(db_manager)
        aid = self._insert_analysis(db_manager)
        snapshots = [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
            {"kpi_name": "overall_sentiment", "kpi_category": "sentiment", "value": 0.65,
             "source_agent": "sentiment", "confidence": 0.8},
        ]
        repo.insert_snapshots("AAPL", aid, snapshots)
        result = repo.get_latest_snapshots("AAPL")
        assert len(result) == 2
        assert result[0]["kpi_name"] in ("forward_pe", "overall_sentiment")

    def test_get_latest_snapshots_returns_most_recent(self, db_manager):
        """get_latest_snapshots returns only the most recent snapshot set."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        result = repo.get_latest_snapshots("AAPL")
        assert len(result) == 1
        assert result[0]["value"] == 20.1

    def test_get_prior_snapshots(self, db_manager):
        """get_prior_snapshots returns the snapshot set before the given analysis."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        prior = repo.get_prior_snapshots("AAPL", aid2)
        assert len(prior) == 1
        assert prior[0]["value"] == 22.5
        assert prior[0]["analysis_id"] == aid1

    def test_get_timeseries(self, db_manager):
        """get_timeseries returns chronological KPI values."""
        repo = self._make_repo(db_manager)
        aid1 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid1, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        aid2 = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid2, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 20.1,
             "source_agent": "fundamentals", "confidence": 0.9},
        ])
        ts = repo.get_timeseries("AAPL", kpis=["forward_pe"])
        assert len(ts) == 2
        assert ts[0]["value"] == 22.5
        assert ts[1]["value"] == 20.1

    def test_get_timeseries_filters_by_kpi(self, db_manager):
        """get_timeseries filters to requested KPIs only."""
        repo = self._make_repo(db_manager)
        aid = self._insert_analysis(db_manager)
        repo.insert_snapshots("AAPL", aid, [
            {"kpi_name": "forward_pe", "kpi_category": "valuation", "value": 22.5,
             "source_agent": "fundamentals", "confidence": 0.9},
            {"kpi_name": "rsi", "kpi_category": "technical", "value": 65.0,
             "source_agent": "technical", "confidence": 0.8},
        ])
        ts = repo.get_timeseries("AAPL", kpis=["forward_pe"])
        assert len(ts) == 1
        assert ts[0]["kpi_name"] == "forward_pe"


class TestWatchlistSchedule:
    def test_watchlist_has_schedule_column(self, db_manager):
        wl = db_manager.create_watchlist("test_wl")
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE watchlists SET auto_analyze_schedule = ? WHERE id = ?", ("twice_daily", wl["id"]))
        result = db_manager.get_watchlist(wl["id"])
        assert result["auto_analyze_schedule"] == "twice_daily"

    def test_watchlist_schedule_defaults_to_null(self, db_manager):
        wl = db_manager.create_watchlist("test_wl2")
        result = db_manager.get_watchlist(wl["id"])
        assert result.get("auto_analyze_schedule") is None
