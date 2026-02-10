"""Tests for DatabaseManager SQLite operations."""

import sqlite3

import pytest

from src.database import DatabaseManager


class TestDatabaseManager:
    """Tests for DatabaseManager."""

    def test_initialize_creates_all_tables(self, db_manager, tmp_db_path):
        """All 5 tables are created on initialization."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "analyses",
            "agent_results",
            "price_history",
            "news_cache",
            "sentiment_scores",
        }
        assert expected_tables.issubset(tables)

    def test_initialize_creates_indexes(self, db_manager, tmp_db_path):
        """Performance indexes are created on initialization."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_analyses_ticker_timestamp" in indexes
        assert "idx_price_history_ticker" in indexes
        assert "idx_news_cache_ticker" in indexes

    def test_insert_and_get_latest_analysis(self, db_manager):
        """insert_analysis + get_latest_analysis round-trip."""
        aid = db_manager.insert_analysis(
            ticker="AAPL",
            recommendation="BUY",
            confidence_score=0.8,
            overall_sentiment_score=0.5,
            solution_agent_reasoning="Strong buy signal.",
            duration_seconds=25.0,
        )
        assert aid is not None
        assert aid > 0

        latest = db_manager.get_latest_analysis("AAPL")
        assert latest is not None
        assert latest["recommendation"] == "BUY"
        assert latest["id"] == aid
        assert latest["ticker"] == "AAPL"
        assert latest["confidence_score"] == 0.8

    def test_insert_agent_result_and_retrieve(self, db_manager):
        """insert_agent_result stores data retrievable via get_analysis_with_agents."""
        aid = db_manager.insert_analysis("NVDA", "HOLD", 0.6, 0.3, "Neutral.", 15.0)
        db_manager.insert_agent_result(
            aid, "market", True, {"trend": "uptrend", "data_source": "alpha_vantage"}, None, 2.5
        )
        db_manager.insert_agent_result(
            aid, "technical", True, {"rsi": 62.5}, None, 3.0
        )

        full = db_manager.get_analysis_with_agents(aid)
        assert full is not None
        assert len(full["agents"]) == 2

        market_agent = next(a for a in full["agents"] if a["agent_type"] == "market")
        assert market_agent["success"] == 1  # SQLite stores bool as int
        assert market_agent["data"]["trend"] == "uptrend"
        assert market_agent["duration_seconds"] == 2.5

    def test_get_analysis_history_ordering(self, db_manager):
        """get_analysis_history returns records in descending timestamp order."""
        db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "First.", 10.0)
        db_manager.insert_analysis("AAPL", "SELL", 0.7, -0.3, "Second.", 12.0)
        db_manager.insert_analysis("AAPL", "HOLD", 0.6, 0.1, "Third.", 8.0)

        history = db_manager.get_analysis_history("AAPL", limit=10)
        assert len(history) == 3
        # Most recent first (DESC by timestamp)
        assert history[0]["recommendation"] == "HOLD"
        assert history[-1]["recommendation"] == "BUY"

    def test_get_analysis_history_respects_limit(self, db_manager):
        """get_analysis_history respects the limit parameter."""
        for i in range(5):
            db_manager.insert_analysis("TSLA", f"{'BUY' if i % 2 == 0 else 'SELL'}", 0.5, 0.0, f"Analysis {i}", 5.0)

        history = db_manager.get_analysis_history("TSLA", limit=3)
        assert len(history) == 3

    def test_get_latest_analysis_returns_none_for_unknown_ticker(self, db_manager):
        """get_latest_analysis returns None when no analyses exist for ticker."""
        result = db_manager.get_latest_analysis("ZZZZ")
        assert result is None

    def test_get_analysis_with_agents_returns_none_for_unknown_id(self, db_manager):
        """get_analysis_with_agents returns None for non-existent analysis ID."""
        result = db_manager.get_analysis_with_agents(9999)
        assert result is None

    def test_insert_sentiment_scores(self, db_manager):
        """insert_sentiment_scores stores factor data retrievable via get_analysis_with_agents."""
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Buy.", 10.0)
        factors = {
            "earnings": {"score": 0.5, "weight": 0.3, "contribution": 0.15},
            "guidance": {"score": 0.3, "weight": 0.4, "contribution": 0.12},
        }
        db_manager.insert_sentiment_scores(aid, factors)

        full = db_manager.get_analysis_with_agents(aid)
        assert "earnings" in full["sentiment_factors"]
        assert "guidance" in full["sentiment_factors"]
        assert full["sentiment_factors"]["earnings"]["score"] == 0.5
        assert full["sentiment_factors"]["earnings"]["weight"] == 0.3

    def test_insert_and_get_news_articles(self, db_manager):
        """insert_news_articles and get_cached_news round-trip."""
        articles = [
            {
                "title": "Test Article",
                "published_at": "2025-02-07T12:00:00",
                "source": "Reuters",
                "url": "https://example.com/article1",
                "summary": "Test article summary.",
                "sentiment_score": 0.5,
            },
            {
                "title": "Second Article",
                "published_at": "2025-02-06T12:00:00",
                "source": "Bloomberg",
                "url": "https://example.com/article2",
                "summary": "Another article.",
                "sentiment_score": -0.2,
            },
        ]
        db_manager.insert_news_articles("AAPL", articles)
        cached = db_manager.get_cached_news("AAPL")
        assert len(cached) == 2

    def test_duplicate_news_url_handled(self, db_manager):
        """Duplicate URLs are handled gracefully (INSERT OR REPLACE)."""
        articles = [
            {
                "title": "Original",
                "published_at": "2025-02-07",
                "source": "Reuters",
                "url": "https://example.com/dup",
                "summary": "Original summary",
                "sentiment_score": 0.0,
            }
        ]
        db_manager.insert_news_articles("AAPL", articles)
        db_manager.insert_news_articles("AAPL", articles)

        cached = db_manager.get_cached_news("AAPL")
        assert len(cached) == 1

    def test_insert_and_get_price_data(self, db_manager):
        """insert_price_data and get_cached_price_data round-trip."""
        data = [
            {
                "timestamp": "2025-02-07",
                "open": 182.0,
                "high": 183.0,
                "low": 181.0,
                "close": 183.0,
                "volume": 48000000,
            },
            {
                "timestamp": "2025-02-06",
                "open": 181.0,
                "high": 182.0,
                "low": 180.0,
                "close": 182.0,
                "volume": 42000000,
            },
        ]
        db_manager.insert_price_data("AAPL", data)
        cached = db_manager.get_cached_price_data("AAPL")
        assert len(cached) == 2
        # ASC ordering
        assert cached[0]["timestamp"] == "2025-02-06"
        assert cached[1]["timestamp"] == "2025-02-07"

    def test_get_cached_price_data_with_start_date(self, db_manager):
        """get_cached_price_data filters by start_date."""
        data = [
            {"timestamp": "2025-02-05", "open": 180, "high": 181, "low": 179, "close": 180, "volume": 1000},
            {"timestamp": "2025-02-06", "open": 181, "high": 182, "low": 180, "close": 181, "volume": 1000},
            {"timestamp": "2025-02-07", "open": 182, "high": 183, "low": 181, "close": 182, "volume": 1000},
        ]
        db_manager.insert_price_data("AAPL", data)

        cached = db_manager.get_cached_price_data("AAPL", start_date="2025-02-06")
        assert len(cached) == 2
        assert cached[0]["timestamp"] == "2025-02-06"

    def test_get_cached_news_with_limit(self, db_manager):
        """get_cached_news respects the limit parameter."""
        articles = [
            {
                "title": f"Article {i}",
                "published_at": f"2025-02-{7 - i:02d}",
                "source": "Test",
                "url": f"https://example.com/art{i}",
                "summary": f"Summary {i}",
                "sentiment_score": 0.0,
            }
            for i in range(5)
        ]
        db_manager.insert_news_articles("AAPL", articles)

        cached = db_manager.get_cached_news("AAPL", limit=3)
        assert len(cached) == 3

    def test_cross_ticker_isolation(self, db_manager):
        """Analyses for different tickers are isolated."""
        db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Apple buy.", 10.0)
        db_manager.insert_analysis("NVDA", "SELL", 0.6, -0.3, "Nvidia sell.", 12.0)

        aapl = db_manager.get_latest_analysis("AAPL")
        nvda = db_manager.get_latest_analysis("NVDA")

        assert aapl["recommendation"] == "BUY"
        assert nvda["recommendation"] == "SELL"

        aapl_history = db_manager.get_analysis_history("AAPL")
        assert len(aapl_history) == 1
        assert aapl_history[0]["ticker"] == "AAPL"
