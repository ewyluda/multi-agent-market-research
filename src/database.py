"""Database manager for multi-agent market research application."""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
import os


class DatabaseManager:
    """Manages SQLite database operations for market research data."""

    def __init__(self, db_path: str = "market_research.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.initialize_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_database(self):
        """Create database schema if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Main analysis runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    recommendation TEXT CHECK(recommendation IN ('BUY', 'HOLD', 'SELL')),
                    confidence_score REAL,
                    overall_sentiment_score REAL,
                    solution_agent_reasoning TEXT,
                    duration_seconds REAL,
                    UNIQUE(ticker, timestamp)
                )
            """)

            # Individual agent results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER,
                    agent_type TEXT NOT NULL,
                    success BOOLEAN,
                    data TEXT,
                    error TEXT,
                    duration_seconds REAL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Price history cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    UNIQUE(ticker, timestamp)
                )
            """)

            # News articles cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    title TEXT,
                    source TEXT,
                    url TEXT,
                    summary TEXT,
                    sentiment_score REAL,
                    UNIQUE(ticker, url)
                )
            """)

            # Sentiment scores
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER,
                    factor TEXT,
                    score REAL,
                    weight REAL,
                    contribution REAL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_ticker_timestamp
                ON analyses(ticker, timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_history_ticker
                ON price_history(ticker, timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_cache_ticker
                ON news_cache(ticker, published_at DESC)
            """)

    def insert_analysis(
        self,
        ticker: str,
        recommendation: str,
        confidence_score: float,
        overall_sentiment_score: float,
        solution_agent_reasoning: str,
        duration_seconds: float
    ) -> int:
        """
        Insert a new analysis record.

        Args:
            ticker: Stock ticker symbol
            recommendation: BUY, HOLD, or SELL
            confidence_score: Confidence score (0-1)
            overall_sentiment_score: Overall sentiment score (-1 to 1)
            solution_agent_reasoning: Reasoning text from solution agent
            duration_seconds: Total analysis duration

        Returns:
            ID of inserted analysis
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT INTO analyses (
                    ticker, timestamp, recommendation, confidence_score,
                    overall_sentiment_score, solution_agent_reasoning, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ticker, timestamp, recommendation, confidence_score,
                  overall_sentiment_score, solution_agent_reasoning, duration_seconds))

            return cursor.lastrowid

    def insert_agent_result(
        self,
        analysis_id: int,
        agent_type: str,
        success: bool,
        data: Dict[str, Any],
        error: Optional[str] = None,
        duration_seconds: float = 0.0
    ):
        """
        Insert agent execution result.

        Args:
            analysis_id: ID of parent analysis
            agent_type: Type of agent (news, sentiment, etc.)
            success: Whether agent execution succeeded
            data: Agent output data
            error: Error message if failed
            duration_seconds: Agent execution duration
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            data_json = json.dumps(data) if data else None

            cursor.execute("""
                INSERT INTO agent_results (
                    analysis_id, agent_type, success, data, error, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (analysis_id, agent_type, success, data_json, error, duration_seconds))

    def insert_price_data(self, ticker: str, price_data: List[Dict[str, Any]]):
        """
        Insert or update price history data.

        Args:
            ticker: Stock ticker symbol
            price_data: List of price records with OHLCV data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            for record in price_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO price_history (
                        ticker, timestamp, open, high, low, close, volume
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker,
                    record['timestamp'],
                    record.get('open'),
                    record.get('high'),
                    record.get('low'),
                    record.get('close'),
                    record.get('volume')
                ))

    def insert_news_articles(self, ticker: str, articles: List[Dict[str, Any]]):
        """
        Insert or update news articles.

        Args:
            ticker: Stock ticker symbol
            articles: List of news article records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            for article in articles:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO news_cache (
                            ticker, published_at, title, source, url, summary, sentiment_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker,
                        article.get('published_at'),
                        article.get('title'),
                        article.get('source'),
                        article.get('url'),
                        article.get('summary'),
                        article.get('sentiment_score')
                    ))
                except sqlite3.IntegrityError:
                    # Skip duplicate URLs
                    continue

    def insert_sentiment_scores(
        self,
        analysis_id: int,
        sentiment_factors: Dict[str, Dict[str, float]]
    ):
        """
        Insert sentiment factor scores.

        Args:
            analysis_id: ID of parent analysis
            sentiment_factors: Dict of factors with score, weight, contribution
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            for factor, values in sentiment_factors.items():
                cursor.execute("""
                    INSERT INTO sentiment_scores (
                        analysis_id, factor, score, weight, contribution
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    analysis_id,
                    factor,
                    values.get('score', 0.0),
                    values.get('weight', 0.0),
                    values.get('contribution', 0.0)
                ))

    def get_latest_analysis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent analysis for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Analysis record as dict, or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM analyses
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (ticker,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_analysis_with_agents(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """
        Get complete analysis with all agent results.

        Args:
            analysis_id: ID of analysis

        Returns:
            Analysis record with agent results
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get main analysis
            cursor.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
            analysis = cursor.fetchone()
            if not analysis:
                return None

            result = dict(analysis)

            # Get agent results
            cursor.execute("""
                SELECT * FROM agent_results WHERE analysis_id = ?
            """, (analysis_id,))
            agent_rows = cursor.fetchall()
            result['agents'] = [dict(row) for row in agent_rows]

            # Parse JSON data
            for agent in result['agents']:
                if agent['data']:
                    agent['data'] = json.loads(agent['data'])

            # Get sentiment scores
            cursor.execute("""
                SELECT * FROM sentiment_scores WHERE analysis_id = ?
            """, (analysis_id,))
            sentiment_rows = cursor.fetchall()
            result['sentiment_factors'] = {
                row['factor']: {
                    'score': row['score'],
                    'weight': row['weight'],
                    'contribution': row['contribution']
                }
                for row in sentiment_rows
            }

            return result

    def get_analysis_history(
        self,
        ticker: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get analysis history for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records to return

        Returns:
            List of analysis records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM analyses
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (ticker, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_cached_price_data(
        self,
        ticker: str,
        start_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get cached price history.

        Args:
            ticker: Stock ticker symbol
            start_date: Optional start date filter (ISO format)

        Returns:
            List of price records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if start_date:
                cursor.execute("""
                    SELECT * FROM price_history
                    WHERE ticker = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """, (ticker, start_date))
            else:
                cursor.execute("""
                    SELECT * FROM price_history
                    WHERE ticker = ?
                    ORDER BY timestamp ASC
                """, (ticker,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_cached_news(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get cached news articles.

        Args:
            ticker: Stock ticker symbol
            start_date: Optional start date filter (ISO format)
            limit: Maximum number of articles

        Returns:
            List of news article records
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if start_date:
                cursor.execute("""
                    SELECT * FROM news_cache
                    WHERE ticker = ? AND published_at >= ?
                    ORDER BY published_at DESC
                    LIMIT ?
                """, (ticker, start_date, limit))
            else:
                cursor.execute("""
                    SELECT * FROM news_cache
                    WHERE ticker = ?
                    ORDER BY published_at DESC
                    LIMIT ?
                """, (ticker, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
