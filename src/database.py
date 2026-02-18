"""Database manager for multi-agent market research application."""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, date, timedelta, timezone
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
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
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
                    score REAL,
                    decision_card TEXT,
                    change_summary TEXT,
                    analysis_payload TEXT,
                    analysis_schema_version TEXT NOT NULL DEFAULT 'v1',
                    signal_contract_v2 TEXT,
                    ev_score_7d REAL,
                    confidence_calibrated REAL,
                    data_quality_score REAL,
                    regime_label TEXT,
                    rationale_summary TEXT,
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
                    run_reason TEXT DEFAULT 'scheduled',
                    catalyst_event_type TEXT,
                    catalyst_event_date TEXT,
                    FOREIGN KEY(schedule_id) REFERENCES schedules(id),
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Portfolio profile (singleton row id=1)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT NOT NULL DEFAULT 'Primary',
                    base_currency TEXT NOT NULL DEFAULT 'USD',
                    max_position_pct REAL NOT NULL DEFAULT 0.10,
                    max_sector_pct REAL NOT NULL DEFAULT 0.30,
                    risk_budget_pct REAL NOT NULL DEFAULT 1.00,
                    target_portfolio_beta REAL NOT NULL DEFAULT 1.00,
                    max_turnover_pct REAL NOT NULL DEFAULT 0.15,
                    default_transaction_cost_bps REAL NOT NULL DEFAULT 10.00,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Portfolio holdings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL UNIQUE,
                    shares REAL NOT NULL CHECK (shares >= 0),
                    avg_cost REAL,
                    market_value REAL NOT NULL CHECK (market_value >= 0),
                    sector TEXT,
                    beta REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Seeded macro catalyst events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS macro_catalyst_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL CHECK (event_type IN ('fomc', 'cpi', 'nfp')),
                    event_date TEXT NOT NULL,
                    event_label TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'seeded',
                    enabled BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(event_type, event_date)
                )
            """)

            # Post-analysis outcomes for calibration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL CHECK (horizon_days IN (1,7,30)),
                    target_date TEXT NOT NULL,
                    baseline_price REAL NOT NULL,
                    realized_price REAL,
                    realized_return_pct REAL,
                    direction_correct BOOLEAN,
                    outcome_up BOOLEAN,
                    predicted_up_probability REAL,
                    confidence REAL,
                    brier_component REAL,
                    transaction_cost_bps REAL,
                    slippage_bps REAL,
                    realized_return_net_pct REAL,
                    max_drawdown_pct REAL,
                    utility_score REAL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','complete','skipped')),
                    evaluated_at TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(analysis_id, horizon_days),
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
                )
            """)

            # Daily calibration snapshots by horizon
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calibration_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    as_of_date TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL CHECK (horizon_days IN (1,7,30)),
                    sample_size INTEGER NOT NULL,
                    directional_accuracy REAL NOT NULL,
                    avg_realized_return_pct REAL,
                    mean_confidence REAL,
                    brier_score REAL NOT NULL,
                    mean_net_return_pct REAL,
                    mean_drawdown_pct REAL,
                    utility_mean REAL,
                    created_at TEXT NOT NULL,
                    UNIQUE(as_of_date, horizon_days)
                )
            """)

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS confidence_reliability_bins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    as_of_date TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL CHECK (horizon_days IN (1,7,30)),
                    bin_index INTEGER NOT NULL,
                    bin_lower REAL NOT NULL,
                    bin_upper REAL NOT NULL,
                    sample_size INTEGER NOT NULL,
                    empirical_hit_rate REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(as_of_date, horizon_days, bin_index)
                )
                """
            )

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
                        'confidence_below',
                        'ev_above',
                        'ev_below',
                        'regime_change',
                        'data_quality_below',
                        'calibration_drop'
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
            self._ensure_column(cursor, "analyses", "analysis_schema_version", "TEXT NOT NULL DEFAULT 'v1'")
            self._ensure_column(cursor, "analyses", "signal_contract_v2", "TEXT")
            self._ensure_column(cursor, "analyses", "ev_score_7d", "REAL")
            self._ensure_column(cursor, "analyses", "confidence_calibrated", "REAL")
            self._ensure_column(cursor, "analyses", "data_quality_score", "REAL")
            self._ensure_column(cursor, "analyses", "regime_label", "TEXT")
            self._ensure_column(cursor, "analyses", "rationale_summary", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "trigger_context", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "change_summary", "TEXT")
            self._ensure_column(cursor, "alert_notifications", "suggested_action", "TEXT")
            self._ensure_column(cursor, "schedule_runs", "run_reason", "TEXT DEFAULT 'scheduled'")
            self._ensure_column(cursor, "schedule_runs", "catalyst_event_type", "TEXT")
            self._ensure_column(cursor, "schedule_runs", "catalyst_event_date", "TEXT")
            self._ensure_column(cursor, "portfolio_profile", "name", "TEXT NOT NULL DEFAULT 'Primary'")
            self._ensure_column(cursor, "portfolio_profile", "base_currency", "TEXT NOT NULL DEFAULT 'USD'")
            self._ensure_column(cursor, "portfolio_profile", "max_position_pct", "REAL NOT NULL DEFAULT 0.10")
            self._ensure_column(cursor, "portfolio_profile", "max_sector_pct", "REAL NOT NULL DEFAULT 0.30")
            self._ensure_column(cursor, "portfolio_profile", "risk_budget_pct", "REAL NOT NULL DEFAULT 1.00")
            self._ensure_column(cursor, "portfolio_profile", "target_portfolio_beta", "REAL NOT NULL DEFAULT 1.00")
            self._ensure_column(cursor, "portfolio_profile", "max_turnover_pct", "REAL NOT NULL DEFAULT 0.15")
            self._ensure_column(cursor, "portfolio_profile", "default_transaction_cost_bps", "REAL NOT NULL DEFAULT 10.00")
            self._ensure_column(cursor, "portfolio_holdings", "sector", "TEXT")
            self._ensure_column(cursor, "portfolio_holdings", "beta", "REAL")
            self._ensure_column(cursor, "macro_catalyst_events", "source", "TEXT NOT NULL DEFAULT 'seeded'")
            self._ensure_column(cursor, "macro_catalyst_events", "enabled", "BOOLEAN NOT NULL DEFAULT 1")
            self._ensure_column(cursor, "analysis_outcomes", "predicted_up_probability", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "confidence", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "brier_component", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "status", "TEXT NOT NULL DEFAULT 'pending'")
            self._ensure_column(cursor, "analysis_outcomes", "transaction_cost_bps", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "slippage_bps", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "realized_return_net_pct", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "max_drawdown_pct", "REAL")
            self._ensure_column(cursor, "analysis_outcomes", "utility_score", "REAL")
            self._ensure_column(cursor, "calibration_snapshots", "mean_net_return_pct", "REAL")
            self._ensure_column(cursor, "calibration_snapshots", "mean_drawdown_pct", "REAL")
            self._ensure_column(cursor, "calibration_snapshots", "utility_mean", "REAL")

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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_ticker
                ON portfolio_holdings(ticker)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_macro_catalyst_events_date
                ON macro_catalyst_events(event_date, enabled)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_outcomes_due
                ON analysis_outcomes(status, target_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_outcomes_ticker
                ON analysis_outcomes(ticker, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_calibration_snapshots_horizon
                ON calibration_snapshots(horizon_days, as_of_date DESC)
            """)
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_confidence_reliability_bins_horizon
                ON confidence_reliability_bins(horizon_days, as_of_date DESC, bin_index ASC)
                """
            )

            # Ensure singleton portfolio profile exists and seed macro events.
            self._ensure_alert_rule_schema(cursor)
            self._ensure_portfolio_profile_row(cursor)
            self._seed_macro_events_from_repo(cursor)

    def _ensure_column(self, cursor: sqlite3.Cursor, table_name: str, column_name: str, column_def: str):
        """Add a column if it does not already exist."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing = {row[1] for row in cursor.fetchall()}
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def _ensure_alert_rule_schema(self, cursor: sqlite3.Cursor):
        """Rebuild alert_rules table if legacy CHECK constraint lacks v2 rule types."""
        cursor.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'alert_rules'
            """
        )
        row = cursor.fetchone()
        create_sql = str((row or [None])[0] or "").lower()
        if "ev_above" in create_sql and "regime_change" in create_sql and "calibration_drop" in create_sql:
            return

        cursor.execute("ALTER TABLE alert_rules RENAME TO alert_rules_old")
        cursor.execute(
            """
            CREATE TABLE alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                rule_type TEXT NOT NULL CHECK(rule_type IN (
                    'recommendation_change',
                    'score_above',
                    'score_below',
                    'confidence_above',
                    'confidence_below',
                    'ev_above',
                    'ev_below',
                    'regime_change',
                    'data_quality_below',
                    'calibration_drop'
                )),
                threshold REAL,
                enabled BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO alert_rules (id, ticker, rule_type, threshold, enabled, created_at, updated_at)
            SELECT id, ticker, rule_type, threshold, enabled, created_at, updated_at
            FROM alert_rules_old
            WHERE rule_type IN (
                'recommendation_change',
                'score_above',
                'score_below',
                'confidence_above',
                'confidence_below'
            )
            """
        )
        cursor.execute("DROP TABLE alert_rules_old")
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_alert_rules_ticker
            ON alert_rules(ticker)
            """
        )

    def _ensure_portfolio_profile_row(self, cursor: sqlite3.Cursor):
        """Create singleton portfolio profile row when missing."""
        cursor.execute("SELECT id FROM portfolio_profile WHERE id = 1")
        if cursor.fetchone():
            return

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO portfolio_profile (
                id, name, base_currency, max_position_pct, max_sector_pct, risk_budget_pct,
                target_portfolio_beta, max_turnover_pct, default_transaction_cost_bps,
                created_at, updated_at
            )
            VALUES (1, 'Primary', 'USD', 0.10, 0.30, 1.00, 1.00, 0.15, 10.00, ?, ?)
            """,
            (now, now),
        )

    def _seed_macro_events_from_repo(self, cursor: sqlite3.Cursor):
        """Seed macro events from docs/seeds/macro_events_2026.json when present."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        seed_path = os.path.join(repo_root, "docs", "seeds", "macro_events_2026.json")
        if not os.path.exists(seed_path):
            return

        try:
            with open(seed_path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
        except Exception:
            return

        if isinstance(payload, dict):
            events = payload.get("events") or []
        elif isinstance(payload, list):
            events = payload
        else:
            events = []

        now = datetime.now(timezone.utc).isoformat()
        for event in events:
            if not isinstance(event, dict):
                continue

            event_type = str(event.get("event_type", "")).strip().lower()
            if event_type not in {"fomc", "cpi", "nfp"}:
                continue

            event_date = str(event.get("event_date", "")).strip()
            if not event_date:
                continue

            event_label = str(event.get("event_label") or event_type.upper()).strip()
            source = str(event.get("source") or "seeded").strip() or "seeded"
            enabled = 1 if bool(event.get("enabled", True)) else 0

            cursor.execute(
                """
                INSERT INTO macro_catalyst_events (
                    event_type, event_date, event_label, source, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_type, event_date) DO UPDATE SET
                    event_label = excluded.event_label,
                    source = excluded.source,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (event_type, event_date, event_label, source, enabled, now, now),
            )

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
        self._deserialize_json_fields(
            record,
            ["decision_card", "change_summary", "analysis_payload", "signal_contract_v2"],
        )

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
        if record.get("signal_contract_v2") and not normalized.get("signal_contract_v2"):
            normalized["signal_contract_v2"] = record.get("signal_contract_v2")
        if record.get("analysis_schema_version"):
            normalized.setdefault("analysis_schema_version", record.get("analysis_schema_version"))
        if record.get("ev_score_7d") is not None and normalized.get("ev_score_7d") is None:
            normalized["ev_score_7d"] = record.get("ev_score_7d")
        if record.get("confidence_calibrated") is not None and normalized.get("confidence_calibrated") is None:
            normalized["confidence_calibrated"] = record.get("confidence_calibrated")
        if record.get("data_quality_score") is not None and normalized.get("data_quality_score") is None:
            normalized["data_quality_score"] = record.get("data_quality_score")
        if record.get("regime_label") and not normalized.get("regime_label"):
            normalized["regime_label"] = record.get("regime_label")
        if record.get("rationale_summary") and not normalized.get("rationale_summary"):
            normalized["rationale_summary"] = record.get("rationale_summary")

        record["analysis"] = normalized
        return record

    def _attach_outcomes_to_history(self, cursor: sqlite3.Cursor, items: List[Dict[str, Any]]):
        """Attach horizon outcome states to detailed history rows."""
        if not items:
            return

        analysis_ids = [item.get("id") for item in items if item.get("id") is not None]
        if not analysis_ids:
            return

        placeholders = ",".join("?" for _ in analysis_ids)
        cursor.execute(
            f"""
            SELECT
                analysis_id,
                horizon_days,
                status,
                target_date,
                realized_return_pct,
                realized_return_net_pct,
                direction_correct,
                brier_component,
                predicted_up_probability,
                max_drawdown_pct,
                utility_score,
                evaluated_at
            FROM analysis_outcomes
            WHERE analysis_id IN ({placeholders})
            """,
            analysis_ids,
        )
        outcome_rows = [dict(row) for row in cursor.fetchall()]

        by_analysis: Dict[int, Dict[str, Dict[str, Any]]] = {}
        for row in outcome_rows:
            analysis_id = row["analysis_id"]
            horizon_key = f"{int(row['horizon_days'])}d"
            by_analysis.setdefault(analysis_id, {})[horizon_key] = {
                "status": row.get("status"),
                "target_date": row.get("target_date"),
                "realized_return_pct": row.get("realized_return_pct"),
                "realized_return_net_pct": row.get("realized_return_net_pct"),
                "direction_correct": row.get("direction_correct"),
                "brier_component": row.get("brier_component"),
                "predicted_up_probability": row.get("predicted_up_probability"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "utility_score": row.get("utility_score"),
                "evaluated_at": row.get("evaluated_at"),
            }

        for item in items:
            analysis_id = item.get("id")
            if analysis_id in by_analysis:
                item["outcomes"] = by_analysis[analysis_id]

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
        analysis_schema_version: str = "v1",
        signal_contract_v2: Optional[Dict[str, Any]] = None,
        ev_score_7d: Optional[float] = None,
        confidence_calibrated: Optional[float] = None,
        data_quality_score: Optional[float] = None,
        regime_label: Optional[str] = None,
        rationale_summary: Optional[str] = None,
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
            analysis_schema_version: Analysis schema version marker
            signal_contract_v2: Deterministic signal contract payload
            ev_score_7d: Expected-value score at 7-day horizon
            confidence_calibrated: Reliability-calibrated confidence
            data_quality_score: Data quality score (0-100)
            regime_label: risk_on/risk_off/transition regime label
            rationale_summary: concise rationale summary text

        Returns:
            ID of inserted analysis
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.now(timezone.utc).isoformat()
            decision_card_json = json.dumps(decision_card) if decision_card is not None else None
            change_summary_json = json.dumps(change_summary) if change_summary is not None else None
            analysis_payload_json = json.dumps(analysis_payload) if analysis_payload is not None else None
            signal_contract_v2_json = json.dumps(signal_contract_v2) if signal_contract_v2 is not None else None

            cursor.execute("""
                INSERT INTO analyses (
                    ticker, timestamp, recommendation, confidence_score,
                    overall_sentiment_score, solution_agent_reasoning, duration_seconds,
                    score, decision_card, change_summary, analysis_payload,
                    analysis_schema_version, signal_contract_v2, ev_score_7d,
                    confidence_calibrated, data_quality_score, regime_label, rationale_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                analysis_schema_version or "v1",
                signal_contract_v2_json,
                ev_score_7d,
                confidence_calibrated,
                data_quality_score,
                regime_label,
                rationale_summary,
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

    def list_analyses_for_signal_contract_backfill(
        self,
        *,
        since_timestamp: str,
        last_id: int = 0,
        batch_size: int = 200,
    ) -> List[Dict[str, Any]]:
        """List candidate analysis rows for signal_contract_v2 backfill in ID order."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    ticker,
                    timestamp,
                    recommendation,
                    confidence_score,
                    score,
                    decision_card,
                    change_summary,
                    rationale_summary,
                    solution_agent_reasoning,
                    analysis_schema_version,
                    signal_contract_v2,
                    analysis_payload
                FROM analyses
                WHERE timestamp >= ?
                  AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (since_timestamp, int(last_id), int(batch_size)),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                self._deserialize_json_fields(
                    row,
                    ["signal_contract_v2", "analysis_payload", "decision_card", "change_summary"],
                )
            return rows

    def get_agent_results_map(self, analysis_id: int) -> Dict[str, Dict[str, Any]]:
        """Get analysis agent results as an orchestrator-compatible map."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT agent_type, success, data, error, duration_seconds
                FROM agent_results
                WHERE analysis_id = ?
                """,
                (analysis_id,),
            )
            rows = cursor.fetchall()

            mapped: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                raw_data = row["data"]
                parsed_data: Dict[str, Any] = {}
                if raw_data:
                    try:
                        value = json.loads(raw_data)
                        if isinstance(value, dict):
                            parsed_data = value
                    except (json.JSONDecodeError, TypeError):
                        parsed_data = {}

                mapped[str(row["agent_type"])] = {
                    "success": bool(row["success"]),
                    "data": parsed_data,
                    "error": row["error"],
                    "duration_seconds": float(row["duration_seconds"] or 0.0),
                    "agent_type": str(row["agent_type"]),
                }

            return mapped

    def update_analysis_signal_contract_v2(
        self,
        *,
        analysis_id: int,
        signal_contract_v2: Dict[str, Any],
        analysis_schema_version: str = "v2",
        ev_score_7d: Optional[float] = None,
        confidence_calibrated: Optional[float] = None,
        data_quality_score: Optional[float] = None,
        regime_label: Optional[str] = None,
        rationale_summary: Optional[str] = None,
        merge_into_payload: bool = True,
    ) -> bool:
        """
        Persist signal_contract_v2 backfill fields.

        This is additive and preserves legacy payload keys.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT analysis_payload
                FROM analyses
                WHERE id = ?
                """,
                (analysis_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            analysis_payload_json: Optional[str] = None
            if merge_into_payload:
                payload: Dict[str, Any] = {}
                raw_payload = row["analysis_payload"]
                if isinstance(raw_payload, str) and raw_payload:
                    try:
                        parsed = json.loads(raw_payload)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                elif isinstance(raw_payload, dict):
                    payload = dict(raw_payload)

                payload["analysis_schema_version"] = analysis_schema_version or "v2"
                payload["signal_contract_v2"] = signal_contract_v2
                payload["ev_score_7d"] = ev_score_7d
                payload["confidence_calibrated"] = confidence_calibrated
                payload["data_quality_score"] = data_quality_score
                payload["regime_label"] = regime_label
                if rationale_summary is not None:
                    payload["rationale_summary"] = rationale_summary
                analysis_payload_json = json.dumps(payload)

            cursor.execute(
                """
                UPDATE analyses
                SET analysis_schema_version = ?,
                    signal_contract_v2 = ?,
                    ev_score_7d = ?,
                    confidence_calibrated = ?,
                    data_quality_score = ?,
                    regime_label = ?,
                    rationale_summary = ?,
                    analysis_payload = COALESCE(?, analysis_payload)
                WHERE id = ?
                """,
                (
                    analysis_schema_version or "v2",
                    json.dumps(signal_contract_v2) if signal_contract_v2 is not None else None,
                    ev_score_7d,
                    confidence_calibrated,
                    data_quality_score,
                    regime_label,
                    rationale_summary,
                    analysis_payload_json,
                    analysis_id,
                ),
            )
            return cursor.rowcount > 0

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
        min_ev_score: Optional[float] = None,
        max_ev_score: Optional[float] = None,
        min_confidence_calibrated: Optional[float] = None,
        max_confidence_calibrated: Optional[float] = None,
        min_data_quality_score: Optional[float] = None,
        regime_label: Optional[str] = None,
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
            if min_ev_score is not None:
                conditions.append("ev_score_7d >= ?")
                params.append(float(min_ev_score))
            if max_ev_score is not None:
                conditions.append("ev_score_7d <= ?")
                params.append(float(max_ev_score))
            if min_confidence_calibrated is not None:
                conditions.append("confidence_calibrated >= ?")
                params.append(float(min_confidence_calibrated))
            if max_confidence_calibrated is not None:
                conditions.append("confidence_calibrated <= ?")
                params.append(float(max_confidence_calibrated))
            if min_data_quality_score is not None:
                conditions.append("data_quality_score >= ?")
                params.append(float(min_data_quality_score))
            if regime_label:
                conditions.append("regime_label = ?")
                params.append(str(regime_label))

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
            self._attach_outcomes_to_history(cursor, items)

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
            cursor.execute("DELETE FROM analysis_outcomes WHERE analysis_id = ?", (analysis_id,))
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
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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

    def get_watchlist_opportunities(
        self,
        watchlist_id: int,
        limit: int = 20,
        min_quality: Optional[float] = None,
        min_ev: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get ranked watchlist opportunities from latest per-ticker analysis rows."""
        analyses = self.get_watchlist_latest_analyses(watchlist_id)
        opportunities: List[Dict[str, Any]] = []
        for item in analyses:
            ticker = item.get("ticker")
            latest = item.get("latest_analysis")
            if not ticker or not latest:
                continue

            analysis_payload = latest.get("analysis") or latest.get("analysis_payload") or {}
            signal = analysis_payload.get("signal_contract_v2")
            if not isinstance(signal, dict):
                signal = latest.get("signal_contract_v2") if isinstance(latest.get("signal_contract_v2"), dict) else None
            if not signal:
                continue

            ev_score = signal.get("ev_score_7d")
            quality_score = ((signal.get("risk") or {}).get("data_quality_score")) if isinstance(signal.get("risk"), dict) else None
            confidence_calibrated = ((signal.get("confidence") or {}).get("calibrated")) if isinstance(signal.get("confidence"), dict) else None
            liquidity = signal.get("liquidity") if isinstance(signal.get("liquidity"), dict) else {}
            capacity_usd = liquidity.get("capacity_usd")
            recommended_action = ((analysis_payload.get("portfolio_action_v2") or {}).get("recommended_action")) or (
                (analysis_payload.get("portfolio_action") or {}).get("action")
            )

            try:
                ev_score_num = float(ev_score) if ev_score is not None else None
            except (TypeError, ValueError):
                ev_score_num = None
            try:
                quality_num = float(quality_score) if quality_score is not None else None
            except (TypeError, ValueError):
                quality_num = None

            if min_ev is not None and (ev_score_num is None or ev_score_num < float(min_ev)):
                continue
            if min_quality is not None and (quality_num is None or quality_num < float(min_quality)):
                continue

            opportunities.append(
                {
                    "ticker": ticker,
                    "analysis_id": latest.get("id"),
                    "timestamp": latest.get("timestamp"),
                    "recommendation": signal.get("recommendation") or latest.get("recommendation"),
                    "ev_score_7d": ev_score_num,
                    "confidence_calibrated": confidence_calibrated,
                    "data_quality_score": quality_num,
                    "capacity_usd": capacity_usd,
                    "regime_label": ((signal.get("risk") or {}).get("regime_label")) if isinstance(signal.get("risk"), dict) else None,
                    "recommended_action": recommended_action,
                }
            )

        opportunities.sort(
            key=lambda row: (
                -float(row.get("ev_score_7d") or -9999.0),
                -float(row.get("confidence_calibrated") or -9999.0),
                -float(row.get("data_quality_score") or -9999.0),
            )
        )
        return opportunities[: max(1, int(limit))]

    # ─── Portfolio Methods ──────────────────────────────────────────────

    def get_portfolio_profile(self) -> Dict[str, Any]:
        """Get singleton portfolio profile."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self._ensure_portfolio_profile_row(cursor)
            cursor.execute("SELECT * FROM portfolio_profile WHERE id = 1")
            row = cursor.fetchone()
            return dict(row)

    def upsert_portfolio_profile(
        self,
        name: Optional[str] = None,
        base_currency: Optional[str] = None,
        max_position_pct: Optional[float] = None,
        max_sector_pct: Optional[float] = None,
        risk_budget_pct: Optional[float] = None,
        target_portfolio_beta: Optional[float] = None,
        max_turnover_pct: Optional[float] = None,
        default_transaction_cost_bps: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update singleton portfolio profile and return latest values."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            self._ensure_portfolio_profile_row(cursor)
            cursor.execute("SELECT * FROM portfolio_profile WHERE id = 1")
            current = dict(cursor.fetchone())
            now = datetime.now(timezone.utc).isoformat()

            values = {
                "name": name if name is not None else current.get("name"),
                "base_currency": base_currency if base_currency is not None else current.get("base_currency"),
                "max_position_pct": max_position_pct if max_position_pct is not None else current.get("max_position_pct"),
                "max_sector_pct": max_sector_pct if max_sector_pct is not None else current.get("max_sector_pct"),
                "risk_budget_pct": risk_budget_pct if risk_budget_pct is not None else current.get("risk_budget_pct"),
                "target_portfolio_beta": (
                    target_portfolio_beta if target_portfolio_beta is not None else current.get("target_portfolio_beta")
                ),
                "max_turnover_pct": max_turnover_pct if max_turnover_pct is not None else current.get("max_turnover_pct"),
                "default_transaction_cost_bps": (
                    default_transaction_cost_bps
                    if default_transaction_cost_bps is not None
                    else current.get("default_transaction_cost_bps")
                ),
                "updated_at": now,
            }
            cursor.execute(
                """
                UPDATE portfolio_profile
                SET name = ?, base_currency = ?, max_position_pct = ?, max_sector_pct = ?, risk_budget_pct = ?,
                    target_portfolio_beta = ?, max_turnover_pct = ?, default_transaction_cost_bps = ?, updated_at = ?
                WHERE id = 1
                """,
                (
                    values["name"],
                    values["base_currency"],
                    values["max_position_pct"],
                    values["max_sector_pct"],
                    values["risk_budget_pct"],
                    values["target_portfolio_beta"],
                    values["max_turnover_pct"],
                    values["default_transaction_cost_bps"],
                    values["updated_at"],
                ),
            )
            cursor.execute("SELECT * FROM portfolio_profile WHERE id = 1")
            return dict(cursor.fetchone())

    def list_portfolio_holdings(self) -> List[Dict[str, Any]]:
        """List holdings ordered by market value descending."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM portfolio_holdings
                ORDER BY market_value DESC, ticker ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_portfolio_holding(
        self,
        ticker: str,
        shares: float,
        avg_cost: Optional[float],
        market_value: Optional[float],
        sector: Optional[str] = None,
        beta: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a portfolio holding and return persisted row."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO portfolio_holdings (
                    ticker, shares, avg_cost, market_value, sector, beta, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker.upper(),
                    float(shares),
                    float(avg_cost) if avg_cost is not None else None,
                    float(market_value) if market_value is not None else 0.0,
                    sector,
                    float(beta) if beta is not None else None,
                    now,
                    now,
                ),
            )
            holding_id = cursor.lastrowid
            cursor.execute("SELECT * FROM portfolio_holdings WHERE id = ?", (holding_id,))
            return dict(cursor.fetchone())

    def update_portfolio_holding(self, holding_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update holding fields and return updated row, or None when not found."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolio_holdings WHERE id = ?", (holding_id,))
            row = cursor.fetchone()
            if not row:
                return None

            allowed = {"ticker", "shares", "avg_cost", "market_value", "sector", "beta"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates:
                return dict(row)

            normalized = {}
            for key, value in updates.items():
                if key == "ticker":
                    normalized[key] = str(value).upper()
                elif key in {"shares", "avg_cost", "market_value", "beta"} and value is not None:
                    normalized[key] = float(value)
                else:
                    normalized[key] = value

            normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in normalized)
            params = list(normalized.values()) + [holding_id]
            cursor.execute(f"UPDATE portfolio_holdings SET {set_clause} WHERE id = ?", params)
            cursor.execute("SELECT * FROM portfolio_holdings WHERE id = ?", (holding_id,))
            return dict(cursor.fetchone())

    def delete_portfolio_holding(self, holding_id: int) -> bool:
        """Delete holding row by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM portfolio_holdings WHERE id = ?", (holding_id,))
            return cursor.rowcount > 0

    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """Return portfolio totals and sector exposure context."""
        profile = self.get_portfolio_profile()
        holdings = self.list_portfolio_holdings()

        total_market_value = sum(float(h.get("market_value") or 0.0) for h in holdings)
        sector_totals: Dict[str, float] = {}
        for holding in holdings:
            sector = (holding.get("sector") or "Unspecified").strip() or "Unspecified"
            sector_totals[sector] = sector_totals.get(sector, 0.0) + float(holding.get("market_value") or 0.0)

        by_ticker = []
        for holding in holdings:
            market_value = float(holding.get("market_value") or 0.0)
            sector = (holding.get("sector") or "Unspecified").strip() or "Unspecified"
            position_pct = (market_value / total_market_value) if total_market_value > 0 else 0.0
            sector_exposure_pct = (sector_totals.get(sector, 0.0) / total_market_value) if total_market_value > 0 else 0.0
            by_ticker.append(
                {
                    **holding,
                    "position_pct": round(position_pct, 6),
                    "sector_exposure_pct": round(sector_exposure_pct, 6),
                }
            )

        by_sector = []
        for sector, market_value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True):
            exposure_pct = (market_value / total_market_value) if total_market_value > 0 else 0.0
            by_sector.append(
                {
                    "sector": sector,
                    "market_value": round(market_value, 2),
                    "exposure_pct": round(exposure_pct, 6),
                }
            )

        return {
            "profile": profile,
            "total_market_value": round(total_market_value, 2),
            "holdings_count": len(holdings),
            "by_ticker": by_ticker,
            "by_sector": by_sector,
        }

    # ─── Macro Catalyst Methods ────────────────────────────────────────

    def list_macro_events(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        enabled_only: bool = True,
        event_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List macro catalyst events with optional date/type filters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions: List[str] = []
            params: List[Any] = []

            if enabled_only:
                conditions.append("enabled = 1")
            if date_from:
                conditions.append("event_date >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("event_date <= ?")
                params.append(date_to)
            if event_types:
                normalized_types = [str(e).strip().lower() for e in event_types if str(e).strip()]
                if normalized_types:
                    placeholders = ",".join("?" for _ in normalized_types)
                    conditions.append(f"event_type IN ({placeholders})")
                    params.extend(normalized_types)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cursor.execute(
                f"""
                SELECT *
                FROM macro_catalyst_events
                {where_clause}
                ORDER BY event_date ASC, event_type ASC
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def upsert_macro_events(self, events: List[Dict[str, Any]]) -> int:
        """Insert or update macro events. Returns number of rows processed."""
        if not events:
            return 0

        processed = 0
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for event in events:
                if not isinstance(event, dict):
                    continue

                event_type = str(event.get("event_type", "")).strip().lower()
                event_date = str(event.get("event_date", "")).strip()
                if event_type not in {"fomc", "cpi", "nfp"} or not event_date:
                    continue

                cursor.execute(
                    """
                    INSERT INTO macro_catalyst_events (
                        event_type, event_date, event_label, source, enabled, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_type, event_date) DO UPDATE SET
                        event_label = excluded.event_label,
                        source = excluded.source,
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                    """,
                    (
                        event_type,
                        event_date,
                        str(event.get("event_label") or event_type.upper()).strip(),
                        str(event.get("source") or "seeded").strip(),
                        1 if bool(event.get("enabled", True)) else 0,
                        now,
                        now,
                    ),
                )
                processed += 1

        return processed

    def macro_event_exists(self, event_type: str, event_date: str) -> bool:
        """Check whether a macro catalyst event exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM macro_catalyst_events
                WHERE event_type = ? AND event_date = ?
                LIMIT 1
                """,
                (str(event_type).lower(), event_date),
            )
            return cursor.fetchone() is not None

    # ─── Calibration Methods ───────────────────────────────────────────

    def create_outcome_rows_for_analysis(
        self,
        analysis_id: int,
        ticker: str,
        baseline_price: float,
        confidence: Optional[float],
        predicted_up_probability: Optional[float],
        transaction_cost_bps: Optional[float] = None,
        slippage_bps: Optional[float] = None,
    ) -> int:
        """Create pending 1d/7d/30d outcome rows for an analysis."""
        try:
            baseline = float(baseline_price)
        except (TypeError, ValueError):
            return 0
        if baseline <= 0:
            return 0

        pred_prob = None
        if predicted_up_probability is not None:
            try:
                pred_prob = max(0.0, min(1.0, float(predicted_up_probability)))
            except (TypeError, ValueError):
                pred_prob = None

        conf_val = None
        if confidence is not None:
            try:
                conf_val = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                conf_val = None

        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM analyses WHERE id = ?", (analysis_id,))
            row = cursor.fetchone()
            if not row:
                return 0

            try:
                base_dt = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            except ValueError:
                base_dt = datetime.now(timezone.utc)
            base_date = base_dt.date()

            inserted = 0
            for horizon in (1, 7, 30):
                target_date = (base_date + timedelta(days=horizon)).isoformat()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO analysis_outcomes (
                        analysis_id, ticker, horizon_days, target_date, baseline_price,
                        predicted_up_probability, confidence, transaction_cost_bps, slippage_bps, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        analysis_id,
                        ticker.upper(),
                        horizon,
                        target_date,
                        baseline,
                        pred_prob,
                        conf_val,
                        transaction_cost_bps,
                        slippage_bps,
                        now,
                    ),
                )
                inserted += cursor.rowcount

            return inserted

    def list_due_outcomes(self, as_of_date: str) -> List[Dict[str, Any]]:
        """List pending outcomes due at or before the provided date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    ao.*,
                    a.recommendation,
                    a.timestamp AS analysis_timestamp
                FROM analysis_outcomes ao
                JOIN analyses a ON a.id = ao.analysis_id
                WHERE ao.status = 'pending'
                  AND ao.target_date <= ?
                ORDER BY ao.target_date ASC, ao.id ASC
                """,
                (as_of_date,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def complete_outcome(
        self,
        outcome_id: int,
        *,
        realized_price: Optional[float] = None,
        realized_return_pct: Optional[float] = None,
        realized_return_net_pct: Optional[float] = None,
        direction_correct: Optional[bool] = None,
        outcome_up: Optional[bool] = None,
        brier_component: Optional[float] = None,
        max_drawdown_pct: Optional[float] = None,
        utility_score: Optional[float] = None,
        status: str = "complete",
        evaluated_at: Optional[str] = None,
    ) -> bool:
        """Complete or skip an outcome evaluation."""
        if status not in {"complete", "skipped"}:
            status = "complete"

        updates = {
            "realized_price": realized_price,
            "realized_return_pct": realized_return_pct,
            "realized_return_net_pct": realized_return_net_pct,
            "direction_correct": direction_correct,
            "outcome_up": outcome_up,
            "brier_component": brier_component,
            "max_drawdown_pct": max_drawdown_pct,
            "utility_score": utility_score,
            "status": status,
            "evaluated_at": evaluated_at or datetime.now(timezone.utc).isoformat(),
        }
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [outcome_id]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE analysis_outcomes SET {set_clause} WHERE id = ?", values)
            return cursor.rowcount > 0

    def upsert_calibration_snapshot(
        self,
        *,
        as_of_date: str,
        horizon_days: int,
        sample_size: int,
        directional_accuracy: float,
        avg_realized_return_pct: Optional[float],
        mean_confidence: Optional[float],
        brier_score: float,
        mean_net_return_pct: Optional[float] = None,
        mean_drawdown_pct: Optional[float] = None,
        utility_mean: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Insert/update a calibration snapshot."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO calibration_snapshots (
                    as_of_date, horizon_days, sample_size, directional_accuracy,
                    avg_realized_return_pct, mean_confidence, brier_score,
                    mean_net_return_pct, mean_drawdown_pct, utility_mean, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(as_of_date, horizon_days) DO UPDATE SET
                    sample_size = excluded.sample_size,
                    directional_accuracy = excluded.directional_accuracy,
                    avg_realized_return_pct = excluded.avg_realized_return_pct,
                    mean_confidence = excluded.mean_confidence,
                    brier_score = excluded.brier_score,
                    mean_net_return_pct = excluded.mean_net_return_pct,
                    mean_drawdown_pct = excluded.mean_drawdown_pct,
                    utility_mean = excluded.utility_mean
                """,
                (
                    as_of_date,
                    int(horizon_days),
                    int(sample_size),
                    float(directional_accuracy),
                    avg_realized_return_pct,
                    mean_confidence,
                    float(brier_score),
                    mean_net_return_pct,
                    mean_drawdown_pct,
                    utility_mean,
                    now,
                ),
            )
            cursor.execute(
                """
                SELECT * FROM calibration_snapshots
                WHERE as_of_date = ? AND horizon_days = ?
                """,
                (as_of_date, int(horizon_days)),
            )
            return dict(cursor.fetchone())

    def get_calibration_summary(
        self,
        window_days: int = 180,
        horizons: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get most recent calibration snapshots per horizon within a lookback window."""
        horizons = horizons or [1, 7, 30]
        today = date.today()
        window_start = (today - timedelta(days=max(1, int(window_days)))).isoformat()

        summary: Dict[str, Optional[Dict[str, Any]]] = {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for horizon in horizons:
                cursor.execute(
                    """
                    SELECT *
                    FROM calibration_snapshots
                    WHERE horizon_days = ?
                      AND as_of_date >= ?
                    ORDER BY as_of_date DESC
                    LIMIT 1
                    """,
                    (int(horizon), window_start),
                )
                row = cursor.fetchone()
                summary[f"{int(horizon)}d"] = dict(row) if row else None

        return {
            "window_days": int(window_days),
            "as_of_date": today.isoformat(),
            "horizons": summary,
        }

    def replace_confidence_reliability_bins(
        self,
        *,
        as_of_date: str,
        horizon_days: int,
        bins: List[Dict[str, Any]],
    ) -> int:
        """Replace reliability bins for a date/horizon."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM confidence_reliability_bins
                WHERE as_of_date = ? AND horizon_days = ?
                """,
                (as_of_date, int(horizon_days)),
            )
            inserted = 0
            for idx, row in enumerate(bins):
                lower = float(row.get("bin_lower", 0.0))
                upper = float(row.get("bin_upper", 1.0))
                sample_size = int(row.get("sample_size", 0))
                empirical_hit_rate = float(row.get("empirical_hit_rate", 0.5))
                cursor.execute(
                    """
                    INSERT INTO confidence_reliability_bins (
                        as_of_date, horizon_days, bin_index, bin_lower, bin_upper,
                        sample_size, empirical_hit_rate, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        as_of_date,
                        int(horizon_days),
                        int(row.get("bin_index", idx)),
                        lower,
                        upper,
                        sample_size,
                        empirical_hit_rate,
                        now,
                    ),
                )
                inserted += 1
            return inserted

    def get_latest_confidence_reliability_bins(self, horizon_days: int) -> List[Dict[str, Any]]:
        """Get the latest reliability bins for a horizon."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(as_of_date) AS as_of_date
                FROM confidence_reliability_bins
                WHERE horizon_days = ?
                """,
                (int(horizon_days),),
            )
            row = cursor.fetchone()
            as_of_date = row["as_of_date"] if row else None
            if not as_of_date:
                return []

            cursor.execute(
                """
                SELECT *
                FROM confidence_reliability_bins
                WHERE horizon_days = ? AND as_of_date = ?
                ORDER BY bin_index ASC
                """,
                (int(horizon_days), as_of_date),
            )
            return [dict(item) for item in cursor.fetchall()]

    def get_reliability_hit_rate(self, horizon_days: int, confidence_raw: Optional[float]) -> Optional[Dict[str, Any]]:
        """Resolve empirical hit rate for a confidence value from latest bins."""
        parsed_conf = None
        if confidence_raw is not None:
            try:
                parsed_conf = float(confidence_raw)
            except (TypeError, ValueError):
                parsed_conf = None

        bins = self.get_latest_confidence_reliability_bins(horizon_days)
        if not bins:
            return None

        if parsed_conf is None:
            weighted = 0.0
            sample_total = 0
            for row in bins:
                sample = int(row.get("sample_size") or 0)
                weighted += float(row.get("empirical_hit_rate") or 0.0) * sample
                sample_total += sample
            if sample_total <= 0:
                return None
            return {
                "hit_rate": weighted / sample_total,
                "sample_size": sample_total,
                "as_of_date": bins[0].get("as_of_date"),
            }

        for row in bins:
            lower = float(row.get("bin_lower") or 0.0)
            upper = float(row.get("bin_upper") or 1.0)
            if lower <= parsed_conf < upper or (parsed_conf == 1.0 and upper == 1.0):
                return {
                    "hit_rate": float(row.get("empirical_hit_rate") or 0.0),
                    "sample_size": int(row.get("sample_size") or 0),
                    "as_of_date": row.get("as_of_date"),
                    "bin_index": int(row.get("bin_index") or 0),
                    "bin_lower": lower,
                    "bin_upper": upper,
                }

        nearest = min(
            bins,
            key=lambda row: abs(
                float(row.get("bin_lower") or 0.0) - float(parsed_conf)
            ),
        )
        return {
            "hit_rate": float(nearest.get("empirical_hit_rate") or 0.0),
            "sample_size": int(nearest.get("sample_size") or 0),
            "as_of_date": nearest.get("as_of_date"),
            "bin_index": int(nearest.get("bin_index") or 0),
            "bin_lower": float(nearest.get("bin_lower") or 0.0),
            "bin_upper": float(nearest.get("bin_upper") or 1.0),
        }

    def get_confidence_reliability_summary(self, horizon_days: int) -> Dict[str, Any]:
        """Get latest reliability bins with summary metadata for a horizon."""
        bins = self.get_latest_confidence_reliability_bins(horizon_days)
        if not bins:
            return {
                "horizon_days": int(horizon_days),
                "as_of_date": None,
                "total_samples": 0,
                "bins": [],
            }

        total_samples = sum(int(row.get("sample_size") or 0) for row in bins)
        as_of_date = bins[0].get("as_of_date")
        return {
            "horizon_days": int(horizon_days),
            "as_of_date": as_of_date,
            "total_samples": total_samples,
            "bins": bins,
        }

    def list_completed_outcomes(
        self,
        *,
        horizon_days: int,
        since_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List completed outcomes for snapshot aggregation."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["horizon_days = ?", "status = 'complete'"]
            params: List[Any] = [int(horizon_days)]
            if since_date:
                conditions.append("target_date >= ?")
                params.append(since_date)

            where_clause = " AND ".join(conditions)
            cursor.execute(
                f"""
                SELECT
                    id,
                    horizon_days,
                    target_date,
                    realized_return_pct,
                    realized_return_net_pct,
                    direction_correct,
                    confidence,
                    predicted_up_probability,
                    brier_component,
                    transaction_cost_bps,
                    slippage_bps,
                    max_drawdown_pct,
                    utility_score
                FROM analysis_outcomes
                WHERE {where_clause}
                ORDER BY target_date DESC
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_outcomes_for_ticker(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent outcomes for a ticker."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    ao.*,
                    a.recommendation,
                    a.timestamp AS analysis_timestamp
                FROM analysis_outcomes ao
                JOIN analyses a ON a.id = ao.analysis_id
                WHERE ao.ticker = ?
                ORDER BY ao.created_at DESC, ao.horizon_days ASC
                LIMIT ?
                """,
                (ticker.upper(), int(limit)),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_outcomes_for_analysis(self, analysis_id: int) -> Dict[str, Dict[str, Any]]:
        """Get outcomes for a single analysis keyed by horizon string."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM analysis_outcomes
                WHERE analysis_id = ?
                ORDER BY horizon_days ASC
                """,
                (analysis_id,),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            result[f"{int(row['horizon_days'])}d"] = row
        return result

    # ─── Schedule Methods ──────────────────────────────────────────────

    def create_schedule(self, ticker: str, interval_minutes: int, agents: Optional[str] = None) -> Dict[str, Any]:
        """Create a new schedule. Returns the created schedule dict."""
        now = datetime.now(timezone.utc).isoformat()
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

            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
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

    def insert_schedule_run(
        self,
        schedule_id: int,
        analysis_id: Optional[int],
        started_at: str,
        completed_at: Optional[str],
        success: bool,
        error: Optional[str] = None,
        run_reason: str = "scheduled",
        catalyst_event_type: Optional[str] = None,
        catalyst_event_date: Optional[str] = None,
    ) -> int:
        """Insert a schedule run record. Returns run ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO schedule_runs (
                       schedule_id, analysis_id, started_at, completed_at, success, error,
                       run_reason, catalyst_event_type, catalyst_event_date
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    schedule_id,
                    analysis_id,
                    started_at,
                    completed_at,
                    success,
                    error,
                    run_reason,
                    catalyst_event_type,
                    catalyst_event_date,
                ),
            )
            return cursor.lastrowid

    def schedule_run_exists(
        self,
        schedule_id: int,
        run_reason: str,
        catalyst_event_type: Optional[str] = None,
        catalyst_event_date: Optional[str] = None,
    ) -> bool:
        """Return True when a run already exists for schedule/reason/event tuple."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1
                FROM schedule_runs
                WHERE schedule_id = ?
                  AND run_reason = ?
                  AND (
                    (? IS NULL AND catalyst_event_type IS NULL) OR catalyst_event_type = ?
                  )
                  AND (
                    (? IS NULL AND catalyst_event_date IS NULL) OR catalyst_event_date = ?
                  )
                LIMIT 1
                """,
                (
                    schedule_id,
                    run_reason,
                    catalyst_event_type,
                    catalyst_event_type,
                    catalyst_event_date,
                    catalyst_event_date,
                ),
            )
            return cursor.fetchone() is not None

    def get_schedule_runs(self, schedule_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent runs for a schedule."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    schedule_id,
                    analysis_id,
                    started_at,
                    completed_at,
                    success,
                    error,
                    COALESCE(run_reason, 'scheduled') AS run_reason,
                    catalyst_event_type,
                    catalyst_event_date
                FROM schedule_runs
                WHERE schedule_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (schedule_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ─── Alert Methods ─────────────────────────────────────────────

    def create_alert_rule(self, ticker: str, rule_type: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        """Create a new alert rule."""
        now = datetime.now(timezone.utc).isoformat()
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

            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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
