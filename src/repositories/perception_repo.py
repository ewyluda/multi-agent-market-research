"""Repository for perception_snapshots and inflection_events CRUD operations."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class PerceptionRepository:
    """Handles all CRUD for perception_snapshots and inflection_events tables."""

    def __init__(self, db_manager):
        self._db = db_manager

    # ─── Snapshot Methods ────────────────────────────────────────────────────

    def insert_snapshots(
        self, ticker: str, analysis_id: int, snapshots: List[Dict[str, Any]]
    ) -> int:
        """Batch insert perception snapshots.

        Each snapshot dict must have: kpi_name, kpi_category, source_agent.
        Optional fields: value, value_text, source_detail, confidence.
        Rows where both value and value_text are None are skipped.

        Returns the count of inserted rows.
        """
        captured_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for snap in snapshots:
            value = snap.get("value")
            value_text = snap.get("value_text")
            if value is None and value_text is None:
                continue
            rows.append(
                (
                    ticker,
                    analysis_id,
                    captured_at,
                    snap["kpi_name"],
                    snap["kpi_category"],
                    value,
                    value_text,
                    snap.get("source_agent"),
                    snap.get("source_detail"),
                    snap.get("confidence"),
                )
            )

        if not rows:
            return 0

        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO perception_snapshots
                    (ticker, analysis_id, captured_at, kpi_name, kpi_category,
                     value, value_text, source_agent, source_detail, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return cursor.rowcount

    def get_latest_snapshots(self, ticker: str) -> List[Dict[str, Any]]:
        """Return all snapshots for the most recent analysis of ticker."""
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            # Find the most recent analysis_id that has snapshots for this ticker
            cursor.execute(
                """
                SELECT analysis_id
                FROM perception_snapshots
                WHERE ticker = ?
                ORDER BY analysis_id DESC
                LIMIT 1
                """,
                (ticker,),
            )
            row = cursor.fetchone()
            if row is None:
                return []
            latest_aid = row["analysis_id"]

            cursor.execute(
                """
                SELECT *
                FROM perception_snapshots
                WHERE ticker = ? AND analysis_id = ?
                ORDER BY kpi_name ASC
                """,
                (ticker, latest_aid),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_prior_snapshots(
        self, ticker: str, current_analysis_id: int
    ) -> List[Dict[str, Any]]:
        """Return snapshots for the analysis immediately before current_analysis_id."""
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT analysis_id
                FROM perception_snapshots
                WHERE ticker = ? AND analysis_id < ?
                ORDER BY analysis_id DESC
                LIMIT 1
                """,
                (ticker, current_analysis_id),
            )
            row = cursor.fetchone()
            if row is None:
                return []
            prior_aid = row["analysis_id"]

            cursor.execute(
                """
                SELECT *
                FROM perception_snapshots
                WHERE ticker = ? AND analysis_id = ?
                ORDER BY kpi_name ASC
                """,
                (ticker, prior_aid),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_timeseries(
        self, ticker: str, kpis: Optional[List[str]] = None, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Return chronological snapshots, optionally filtered by KPI names."""
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            if kpis:
                placeholders = ",".join("?" * len(kpis))
                cursor.execute(
                    f"""
                    SELECT *
                    FROM perception_snapshots
                    WHERE ticker = ? AND kpi_name IN ({placeholders})
                    ORDER BY analysis_id ASC, kpi_name ASC
                    LIMIT ?
                    """,
                    [ticker] + list(kpis) + [limit],
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM perception_snapshots
                    WHERE ticker = ?
                    ORDER BY analysis_id ASC, kpi_name ASC
                    LIMIT ?
                    """,
                    (ticker, limit),
                )
            return [dict(r) for r in cursor.fetchall()]

    # ─── Inflection Event Methods ─────────────────────────────────────────────

    def insert_inflection_events(
        self, ticker: str, analysis_id: int, events: List[Dict[str, Any]]
    ) -> int:
        """Batch insert inflection events.

        source_agents is JSON-serialized if it is a list.
        Returns count of inserted rows.
        """
        detected_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for ev in events:
            source_agents = ev.get("source_agents")
            if isinstance(source_agents, list):
                source_agents = json.dumps(source_agents)
            rows.append(
                (
                    ticker,
                    detected_at,
                    analysis_id,
                    ev.get("kpi_name"),
                    ev.get("direction"),
                    ev.get("magnitude"),
                    ev.get("prior_value"),
                    ev.get("current_value"),
                    ev.get("pct_change"),
                    source_agents,
                    ev.get("convergence_score"),
                    ev.get("summary"),
                )
            )

        if not rows:
            return 0

        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO inflection_events
                    (ticker, detected_at, analysis_id, kpi_name,
                     direction, magnitude, prior_value, current_value,
                     pct_change, source_agents, convergence_score, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return cursor.rowcount

    def get_inflection_history(
        self, ticker: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return inflection events for ticker, most recent first."""
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM inflection_events
                WHERE ticker = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (ticker, limit),
            )
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                if d.get("source_agents") and isinstance(d["source_agents"], str):
                    try:
                        d["source_agents"] = json.loads(d["source_agents"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results.append(d)
            return results

    def get_watchlist_inflections(
        self, watchlist_tickers: List[str], limit_per_ticker: int = 5
    ) -> List[Dict[str, Any]]:
        """Return recent inflections across multiple tickers."""
        if not watchlist_tickers:
            return []

        results = []
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            for ticker in watchlist_tickers:
                cursor.execute(
                    """
                    SELECT *
                    FROM inflection_events
                    WHERE ticker = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (ticker, limit_per_ticker),
                )
                for row in cursor.fetchall():
                    d = dict(row)
                    if d.get("source_agents") and isinstance(d["source_agents"], str):
                        try:
                            d["source_agents"] = json.loads(d["source_agents"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    results.append(d)
        return results
