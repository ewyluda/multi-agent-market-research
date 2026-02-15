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

            # Watchlists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Watchlist tickers (many-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_tickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watchlist_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY(watchlist_id) REFERENCES watchlists(id),
                    UNIQUE(watchlist_id, ticker)
                )
            """)

            # Scheduled analyses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    agents TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(ticker)
                )
            """)

            # Schedule run history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    analysis_id INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    success BOOLEAN,
                    error TEXT,
                    FOREIGN KEY(schedule_id) REFERENCES schedules(id),
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Alert rules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    rule_type TEXT NOT NULL CHECK(rule_type IN (
                        'recommendation_change',
                        'score_above',
                        'score_below',
                        'confidence_above',
                        'confidence_below'
                    )),
                    threshold REAL,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Alert notifications
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_rule_id INTEGER NOT NULL,
                    analysis_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    message TEXT NOT NULL,
                    previous_value TEXT,
                    current_value TEXT,
                    acknowledged BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(alert_rule_id) REFERENCES alert_rules(id),
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Manual/explicit schema migrations for existing databases.
            self._ensure_column(cursor, "analyses", "score", "REAL")
            self._ensure_column(cursor, "analyses", "decision_card", "TEXT")
            self._ensure_column(cursor, "analyses", "change_summary", "TEXT")
            self._ensure_column(cursor, "analyses", "analysis_payload", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "trigger_context", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "change_summary", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "suggested_action", "TEXT")

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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_watchlist_tickers_watchlist
                ON watchlist_tickers(watchlist_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule
                ON schedule_runs(schedule_id, started_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_rules_ticker
                ON alert_rules(ticker)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_notifications_acknowledged
                ON alert_notifications(acknowledged, created_at DESC)
            """)

    def _ensure_column(self, cursor: sqlite3.Cursor, table_name: str, column_name: str, column_def: str):
        """Add a column if it does not already exist."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in cursor.fetchall()}
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def _deserialize_json_fields(self, record: Dict[str, Any], fields: List[str]):
        """Best-effort JSON decoding for selected record fields."""
        for field in fields:
            value = record.get(field)
            if value is None or isinstance(value, (dict, list)):
                continue
            try:
                record[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Keep original value when not valid JSON
                continue

    def _hydrate_analysis_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Decode analysis JSON fields and attach a normalized nested `analysis` payload."""
        self._deserialize_json_fields(record, ["decision_card", "change_summary", "analysis_payload"])

        payload = record.get("analysis_payload")
        normalized = dict(payload) if isinstance(payload, dict) else {}

        # Keep canonical fields in sync with DB columns.
        normalized.setdefault("recommendation", record.get("recommendation"))
        normalized.setdefault("score", record.get("score"))
        normalized.setdefault("confidence", record.get("confidence_score"))
        normalized.setdefault("reasoning", record.get("solution_agent_reasoning"))
        if record.get("decision_card") and not normalized.get("decision_card"):
            normalized["decision_card"] = record.get("decision_card")
        if record.get("change_summary"):
            normalized.setdefault("changes_since_last_run", record.get("change_summary"))
            normalized.setdefault("change_summary", record.get("change_summary"))

        record["analysis"] = normalized
        return record

    def insert_analysis(
        self,
        ticker: str,
        recommendation: str,
        confidence_score: float,
        overall_sentiment_score: float,
        solution_agent_reasoning: str,
        duration_seconds: float,
        score: Optional[float] = None,
        decision_card: Optional[Dict[str, Any]] = None,
        change_summary: Optional[Dict[str, Any]] = None,
        analysis_payload: Optional[Dict[str, Any]] = None,
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
            score: Analysis score (-100..100)
            decision_card: Structured decision output
            change_summary: Delta vs previous run
            analysis_payload: Full synthesized analysis JSON

        Returns:
            ID of inserted analysis
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            decision_card_json = json.dumps(decision_card) if decision_card is not None else None
            change_summary_json = json.dumps(change_summary) if change_summary is not None else None
            analysis_payload_json = json.dumps(analysis_payload) if analysis_payload is not None else None

            cursor.execute("""
                INSERT INTO analyses (
                    ticker, timestamp, recommendation, confidence_score,
                    overall_sentiment_score, solution_agent_reasoning, duration_seconds,
                    score, decision_card, change_summary, analysis_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                timestamp,
                recommendation,
                confidence_score,
                overall_sentiment_score,
                solution_agent_reasoning,
                duration_seconds,
                score,
                decision_card_json,
                change_summary_json,
                analysis_payload_json,
            ))

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
            if not row:
                return None

            return self._hydrate_analysis_record(dict(row))

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

            result = self._hydrate_analysis_record(dict(analysis))

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
            return [self._hydrate_analysis_record(dict(row)) for row in rows]

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

    def get_analysis_history_with_filters(
        self,
        ticker: str,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        recommendation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get paginated, filtered analysis history for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records per page
            offset: Number of records to skip
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            recommendation: Optional recommendation filter (BUY, HOLD, SELL)

        Returns:
            Dict with items, total_count, and has_more
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["ticker = ?"]
            params: list = [ticker]

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date)
            if recommendation:
                conditions.append("recommendation = ?")
                params.append(recommendation.upper())

            where_clause = " AND ".join(conditions)

            cursor.execute(f"SELECT COUNT(*) FROM analyses WHERE {where_clause}", params)
            total_count = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT * FROM analyses
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            )
            rows = cursor.fetchall()
            items = [self._hydrate_analysis_record(dict(row)) for row in rows]

            return {
                "items": items,
                "total_count": total_count,
                "has_more": (offset + limit) < total_count,
            }

    def delete_analysis(self, analysis_id: int) -> bool:
        """
        Delete an analysis and its associated agent_results and sentiment_scores.

        Args:
            analysis_id: ID of the analysis to delete

        Returns:
            True if deleted, False if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM analyses WHERE id = ?", (analysis_id,))
            if not cursor.fetchone():
                return False

            cursor.execute("DELETE FROM agent_results WHERE analysis_id = ?", (analysis_id,))
            cursor.execute("DELETE FROM sentiment_scores WHERE analysis_id = ?", (analysis_id,))
            cursor.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
            return True

    def get_all_analyzed_tickers(self) -> List[Dict[str, Any]]:
        """
        Return all tickers that have at least one analysis.

        Returns:
            List of dicts with ticker, analysis_count, latest_timestamp, latest_recommendation
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    ticker,
                    COUNT(*) as analysis_count,
                    MAX(timestamp) as latest_timestamp,
                    (SELECT recommendation FROM analyses a2
                     WHERE a2.ticker = a1.ticker
                     ORDER BY a2.timestamp DESC LIMIT 1) as latest_recommendation
                FROM analyses a1
                GROUP BY ticker
                ORDER BY latest_timestamp DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ─── Watchlist Methods ─────────────────────────────────────────────

    def create_watchlist(self, name: str) -> Dict[str, Any]:
        """Create a new watchlist."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlists (name, created_at, updated_at) VALUES (?, ?, ?)",
                (name, now, now),
            )
            return {"id": cursor.lastrowid, "name": name, "created_at": now, "updated_at": now, "tickers": []}

    def get_watchlists(self) -> List[Dict[str, Any]]:
        """Get all watchlists with their tickers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlists ORDER BY updated_at DESC")
            watchlists = [dict(row) for row in cursor.fetchall()]

            for wl in watchlists:
                cursor.execute(
                    "SELECT ticker, added_at FROM watchlist_tickers WHERE watchlist_id = ? ORDER BY added_at DESC",
                    (wl["id"],),
                )
                wl["tickers"] = [dict(row) for row in cursor.fetchall()]

            return watchlists

    def get_watchlist(self, watchlist_id: int) -> Optional[Dict[str, Any]]:
        """Get a single watchlist with tickers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,))
            row = cursor.fetchone()
            if not row:
                return None
            wl = dict(row)
            cursor.execute(
                "SELECT ticker, added_at FROM watchlist_tickers WHERE watchlist_id = ? ORDER BY added_at DESC",
                (watchlist_id,),
            )
            wl["tickers"] = [dict(r) for r in cursor.fetchall()]
            return wl

    def rename_watchlist(self, watchlist_id: int, new_name: str) -> bool:
        """Rename a watchlist."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM watchlists WHERE id = ?", (watchlist_id,))
            if not cursor.fetchone():
                return False
            cursor.execute(
                "UPDATE watchlists SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, now, watchlist_id),
            )
            return True

    def delete_watchlist(self, watchlist_id: int) -> bool:
        """Delete a watchlist and its ticker associations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM watchlists WHERE id = ?", (watchlist_id,))
            if not cursor.fetchone():
                return False
            cursor.execute("DELETE FROM watchlist_tickers WHERE watchlist_id = ?", (watchlist_id,))
            cursor.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
            return True

    def add_ticker_to_watchlist(self, watchlist_id: int, ticker: str) -> bool:
        """Add a ticker to a watchlist. Returns False if watchlist doesn't exist."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM watchlists WHERE id = ?", (watchlist_id,))
            if not cursor.fetchone():
                return False
            try:
                cursor.execute(
                    "INSERT INTO watchlist_tickers (watchlist_id, ticker, added_at) VALUES (?, ?, ?)",
                    (watchlist_id, ticker.upper(), now),
                )
            except sqlite3.IntegrityError:
                pass  # Already exists
            cursor.execute(
                "UPDATE watchlists SET updated_at = ? WHERE id = ?",
                (now, watchlist_id),
            )
            return True

    def remove_ticker_from_watchlist(self, watchlist_id: int, ticker: str) -> bool:
        """Remove a ticker from a watchlist."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM watchlist_tickers WHERE watchlist_id = ? AND ticker = ?",
                (watchlist_id, ticker.upper()),
            )
            if cursor.rowcount == 0:
                return False
            cursor.execute(
                "UPDATE watchlists SET updated_at = ? WHERE id = ?",
                (now, watchlist_id),
            )
            return True

    def get_watchlist_latest_analyses(self, watchlist_id: int) -> List[Dict[str, Any]]:
        """Get the latest analysis for each ticker in a watchlist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticker FROM watchlist_tickers WHERE watchlist_id = ? ORDER BY added_at DESC",
                (watchlist_id,),
            )
            tickers = [row["ticker"] for row in cursor.fetchall()]

            results = []
            for ticker in tickers:
                cursor.execute(
                    "SELECT * FROM analyses WHERE ticker = ? ORDER BY timestamp DESC LIMIT 1",
                    (ticker,),
                )
                row = cursor.fetchone()
                results.append({
                    "ticker": ticker,
                    "latest_analysis": self._hydrate_analysis_record(dict(row)) if row else None,
                })
            return results

    # ─── Schedule Methods ──────────────────────────────────────────────

    def create_schedule(self, ticker: str, interval_minutes: int, agents: Optional[str] = None) -> Dict[str, Any]:
        """Create a new schedule. Returns the created schedule dict."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO schedules (ticker, interval_minutes, agents, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (ticker.upper(), interval_minutes, agents, now, now),
            )
            return {
                "id": cursor.lastrowid,
                "ticker": ticker.upper(),
                "interval_minutes": interval_minutes,
                "agents": agents,
                "enabled": True,
                "last_run_at": None,
                "next_run_at": None,
                "created_at": now,
                "updated_at": now,
            }

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedules ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_schedule(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        """Get a single schedule by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_schedule(self, schedule_id: int, **kwargs) -> bool:
        """Update schedule fields (interval_minutes, agents, enabled, last_run_at, next_run_at). Returns False if not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM schedules WHERE id = ?", (schedule_id,))
            if not cursor.fetchone():
                return False

            allowed = {"interval_minutes", "agents", "enabled", "last_run_at", "next_run_at"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates:
                return True

            updates["updated_at"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [schedule_id]
            cursor.execute(f"UPDATE schedules SET {set_clause} WHERE id = ?", values)
            return True

    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule and its runs. Returns False if not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM schedules WHERE id = ?", (schedule_id,))
            if not cursor.fetchone():
                return False
            cursor.execute("DELETE FROM schedule_runs WHERE schedule_id = ?", (schedule_id,))
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            return True

    def insert_schedule_run(self, schedule_id: int, analysis_id: Optional[int], started_at: str, completed_at: Optional[str], success: bool, error: Optional[str] = None) -> int:
        """Insert a schedule run record. Returns run ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO schedule_runs (schedule_id, analysis_id, started_at, completed_at, success, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (schedule_id, analysis_id, started_at, completed_at, success, error),
            )
            return cursor.lastrowid

    def get_schedule_runs(self, schedule_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent runs for a schedule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM schedule_runs WHERE schedule_id = ? ORDER BY started_at DESC LIMIT ?",
                (schedule_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ─── Alert Methods ─────────────────────────────────────────────

    def create_alert_rule(self, ticker: str, rule_type: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        """Create a new alert rule."""
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO alert_rules (ticker, rule_type, threshold, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (ticker.upper(), rule_type, threshold, now, now),
            )
            return {
                "id": cursor.lastrowid,
                "ticker": ticker.upper(),
                "rule_type": rule_type,
                "threshold": threshold,
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }

    def get_alert_rules(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all alert rules, optionally filtered by ticker."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if ticker:
                cursor.execute(
                    "SELECT * FROM alert_rules WHERE ticker = ? ORDER BY created_at DESC",
                    (ticker.upper(),),
                )
            else:
                cursor.execute("SELECT * FROM alert_rules ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_alert_rule(self, rule_id: int) -> Optional[Dict[str, Any]]:
        """Get a single alert rule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alert_rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_alert_rule(self, rule_id: int, **kwargs) -> bool:
        """Update alert rule fields. Allowed: rule_type, threshold, enabled."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM alert_rules WHERE id = ?", (rule_id,))
            if not cursor.fetchone():
                return False

            allowed = {"rule_type", "threshold", "enabled"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates:
                return True

            updates["updated_at"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [rule_id]
            cursor.execute(f"UPDATE alert_rules SET {set_clause} WHERE id = ?", values)
            return True

    def delete_alert_rule(self, rule_id: int) -> bool:
        """Delete an alert rule and its notifications."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM alert_rules WHERE id = ?", (rule_id,))
            if not cursor.fetchone():
                return False
            cursor.execute("DELETE FROM alert_notifications WHERE alert_rule_id = ?", (rule_id,))
            cursor.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            return True

    def insert_alert_notification(
        self,
        alert_rule_id: int,
        analysis_id: int,
        ticker: str,
        message: str,
        previous_value: Optional[str] = None,
        current_value: Optional[str] = None,
        trigger_context: Optional[Dict[str, Any]] = None,
        change_summary: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None,
    ) -> int:
        """Insert an alert notification. Returns notification ID."""
        now = datetime.utcnow().isoformat()
        trigger_context_json = json.dumps(trigger_context) if trigger_context is not None else None
        change_summary_json = json.dumps(change_summary) if change_summary is not None else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO alert_notifications (
                       alert_rule_id, analysis_id, ticker, message,
                       previous_value, current_value, trigger_context,
                       change_summary, suggested_action, acknowledged, created_at
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    alert_rule_id,
                    analysis_id,
                    ticker.upper(),
                    message,
                    previous_value,
                    current_value,
                    trigger_context_json,
                    change_summary_json,
                    suggested_action,
                    now,
                ),
            )
            return cursor.lastrowid

    def get_alert_notifications(self, unacknowledged_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """Get alert notifications."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if unacknowledged_only:
                cursor.execute(
                    "SELECT * FROM alert_notifications WHERE acknowledged = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM alert_notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            notifications = [dict(row) for row in cursor.fetchall()]
            for notification in notifications:
                self._deserialize_json_fields(notification, ["trigger_context", "change_summary"])
            return notifications

    def acknowledge_alert(self, notification_id: int) -> bool:
        """Mark a notification as acknowledged. Returns False if not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM alert_notifications WHERE id = ?", (notification_id,))
            if not cursor.fetchone():
                return False
            cursor.execute(
                "UPDATE alert_notifications SET acknowledged = 1 WHERE id = ?",
                (notification_id,),
            )
            return True

    def get_unacknowledged_count(self) -> int:
        """Get count of unacknowledged notifications."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alert_notifications WHERE acknowledged = 0")
            return cursor.fetchone()[0]

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
