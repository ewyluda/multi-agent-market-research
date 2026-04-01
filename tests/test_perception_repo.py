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
