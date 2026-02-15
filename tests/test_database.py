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

    def test_analysis_json_fields_are_persisted_and_hydrated(self, db_manager):
        """decision_card/change_summary/analysis_payload are stored and decoded on read."""
        decision_card = {
            "action": "buy",
            "entry_zone": {"low": 100.0, "high": 105.0, "reference": 102.5},
            "stop_loss": 95.0,
            "targets": [115.0],
            "time_horizon": "MEDIUM_TERM",
            "confidence": 0.77,
            "invalidation_conditions": ["Breaks below support"],
            "position_sizing_hint": "Use standard risk.",
        }
        change_summary = {
            "has_previous": True,
            "summary": "Recommendation changed from HOLD to BUY",
            "material_changes": [{"type": "recommendation_change", "label": "HOLD -> BUY"}],
            "change_count": 1,
        }
        payload = {
            "recommendation": "BUY",
            "score": 68,
            "confidence": 0.77,
            "decision_card": decision_card,
            "changes_since_last_run": change_summary,
        }

        aid = db_manager.insert_analysis(
            ticker="AAPL",
            recommendation="BUY",
            confidence_score=0.77,
            overall_sentiment_score=0.41,
            solution_agent_reasoning="Thesis improving.",
            duration_seconds=9.2,
            score=68,
            decision_card=decision_card,
            change_summary=change_summary,
            analysis_payload=payload,
        )
        latest = db_manager.get_latest_analysis("AAPL")
        full = db_manager.get_analysis_with_agents(aid)

        assert latest["score"] == 68
        assert latest["decision_card"]["action"] == "buy"
        assert latest["change_summary"]["change_count"] == 1
        assert latest["analysis"]["recommendation"] == "BUY"
        assert latest["analysis"]["decision_card"]["stop_loss"] == 95.0
        assert full["analysis"]["changes_since_last_run"]["has_previous"] is True

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

    def test_alert_notification_extended_fields_round_trip(self, db_manager):
        """trigger_context/change_summary/suggested_action are persisted on notifications."""
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.4, "Reasoning", 7.0)
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        trigger_context = {"rule_type": "recommendation_change", "event": "BUY -> SELL"}
        change_summary = {"summary": "Signal regime flipped", "material_changes": [{"type": "regime"}]}
        notification_id = db_manager.insert_alert_notification(
            alert_rule_id=rule["id"],
            analysis_id=aid,
            ticker="AAPL",
            message="Recommendation changed from BUY to SELL",
            previous_value="BUY",
            current_value="SELL",
            trigger_context=trigger_context,
            change_summary=change_summary,
            suggested_action="Reduce exposure.",
        )
        assert notification_id > 0

        notifications = db_manager.get_alert_notifications(limit=5)
        assert len(notifications) == 1
        notif = notifications[0]
        assert notif["trigger_context"]["rule_type"] == "recommendation_change"
        assert notif["change_summary"]["summary"] == "Signal regime flipped"
        assert notif["suggested_action"] == "Reduce exposure."


class TestScheduleDatabase:
    """Tests for schedule-related DatabaseManager methods."""

    def test_create_schedule(self, db_manager):
        """create_schedule returns a dict with all expected fields."""
        schedule = db_manager.create_schedule("AAPL", 60, "market,technical")
        assert schedule["id"] is not None
        assert schedule["id"] > 0
        assert schedule["ticker"] == "AAPL"
        assert schedule["interval_minutes"] == 60
        assert schedule["agents"] == "market,technical"
        assert schedule["enabled"] is True
        assert schedule["last_run_at"] is None
        assert schedule["next_run_at"] is None
        assert "created_at" in schedule
        assert "updated_at" in schedule

    def test_get_schedules(self, db_manager):
        """get_schedules returns all schedules in descending created_at order."""
        db_manager.create_schedule("AAPL", 60)
        db_manager.create_schedule("NVDA", 120)
        db_manager.create_schedule("TSLA", 30)

        schedules = db_manager.get_schedules()
        assert len(schedules) == 3
        # Most recently created first (DESC by created_at)
        assert schedules[0]["ticker"] == "TSLA"
        assert schedules[-1]["ticker"] == "AAPL"

    def test_get_schedule_by_id(self, db_manager):
        """get_schedule retrieves a specific schedule by ID."""
        created = db_manager.create_schedule("AAPL", 60, "news,sentiment")
        schedule = db_manager.get_schedule(created["id"])
        assert schedule is not None
        assert schedule["ticker"] == "AAPL"
        assert schedule["interval_minutes"] == 60
        assert schedule["agents"] == "news,sentiment"

    def test_get_schedule_not_found(self, db_manager):
        """get_schedule returns None for a non-existent ID."""
        result = db_manager.get_schedule(9999)
        assert result is None

    def test_update_schedule(self, db_manager):
        """update_schedule modifies allowed fields and returns True."""
        created = db_manager.create_schedule("AAPL", 60)
        success = db_manager.update_schedule(created["id"], interval_minutes=120)
        assert success is True

        updated = db_manager.get_schedule(created["id"])
        assert updated["interval_minutes"] == 120

    def test_update_schedule_not_found(self, db_manager):
        """update_schedule returns False for a non-existent ID."""
        result = db_manager.update_schedule(9999, interval_minutes=120)
        assert result is False

    def test_delete_schedule(self, db_manager):
        """delete_schedule removes the schedule and returns True."""
        created = db_manager.create_schedule("AAPL", 60)
        deleted = db_manager.delete_schedule(created["id"])
        assert deleted is True

        result = db_manager.get_schedule(created["id"])
        assert result is None

    def test_delete_schedule_cascades_runs(self, db_manager):
        """delete_schedule also removes associated schedule_runs."""
        created = db_manager.create_schedule("AAPL", 60)
        sid = created["id"]

        # Insert some runs for this schedule
        db_manager.insert_schedule_run(sid, None, "2025-01-01T00:00:00", "2025-01-01T00:01:00", True)
        db_manager.insert_schedule_run(sid, None, "2025-01-01T01:00:00", "2025-01-01T01:01:00", False, "timeout")

        runs_before = db_manager.get_schedule_runs(sid)
        assert len(runs_before) == 2

        db_manager.delete_schedule(sid)
        runs_after = db_manager.get_schedule_runs(sid)
        assert len(runs_after) == 0

    def test_duplicate_ticker_schedule(self, db_manager):
        """Creating two schedules for the same ticker raises IntegrityError."""
        db_manager.create_schedule("AAPL", 60)
        with pytest.raises(sqlite3.IntegrityError):
            db_manager.create_schedule("AAPL", 120)

    def test_insert_and_get_schedule_runs(self, db_manager):
        """insert_schedule_run + get_schedule_runs round-trip with ordering."""
        created = db_manager.create_schedule("AAPL", 60)
        sid = created["id"]

        run1_id = db_manager.insert_schedule_run(
            sid, None, "2025-01-01T00:00:00", "2025-01-01T00:01:00", True
        )
        run2_id = db_manager.insert_schedule_run(
            sid, None, "2025-01-01T01:00:00", "2025-01-01T01:01:00", False, "error msg"
        )
        assert run1_id > 0
        assert run2_id > 0

        runs = db_manager.get_schedule_runs(sid)
        assert len(runs) == 2
        # Most recent first (DESC by started_at)
        assert runs[0]["started_at"] == "2025-01-01T01:00:00"
        assert runs[0]["success"] == 0  # SQLite stores bool as int
        assert runs[0]["error"] == "error msg"
        assert runs[1]["started_at"] == "2025-01-01T00:00:00"
        assert runs[1]["success"] == 1

    def test_schedule_tables_created(self, db_manager, tmp_db_path):
        """Verify schedules and schedule_runs tables exist after initialization."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "schedules" in tables
        assert "schedule_runs" in tables


class TestAlertDatabase:
    """Tests for alert-related DatabaseManager methods."""

    def test_create_and_get_alert_rule(self, db_manager):
        """create_alert_rule + get_alert_rule round-trip."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        assert rule["id"] is not None
        assert rule["id"] > 0
        assert rule["ticker"] == "AAPL"
        assert rule["rule_type"] == "recommendation_change"
        assert rule["threshold"] is None
        assert rule["enabled"] is True

        fetched = db_manager.get_alert_rule(rule["id"])
        assert fetched is not None
        assert fetched["ticker"] == "AAPL"
        assert fetched["rule_type"] == "recommendation_change"

    def test_get_alert_rules_by_ticker(self, db_manager):
        """get_alert_rules filters by ticker."""
        db_manager.create_alert_rule("AAPL", "recommendation_change")
        db_manager.create_alert_rule("AAPL", "score_above", threshold=50)
        db_manager.create_alert_rule("NVDA", "confidence_below", threshold=0.5)

        aapl_rules = db_manager.get_alert_rules(ticker="AAPL")
        assert len(aapl_rules) == 2
        assert all(r["ticker"] == "AAPL" for r in aapl_rules)

        all_rules = db_manager.get_alert_rules()
        assert len(all_rules) == 3

    def test_update_alert_rule(self, db_manager):
        """update_alert_rule modifies threshold and enabled."""
        rule = db_manager.create_alert_rule("AAPL", "score_above", threshold=50)
        success = db_manager.update_alert_rule(rule["id"], threshold=75, enabled=False)
        assert success is True

        updated = db_manager.get_alert_rule(rule["id"])
        assert updated["threshold"] == 75
        assert updated["enabled"] == 0  # SQLite stores bool as int

    def test_delete_alert_rule_cascades(self, db_manager):
        """delete_alert_rule removes the rule and its notifications."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")

        # Insert a fake analysis for the notification FK
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Test.", 5.0)

        # Insert a notification linked to this rule
        db_manager.insert_alert_notification(
            rule["id"], aid, "AAPL", "Test notification"
        )

        notifs_before = db_manager.get_alert_notifications()
        assert len(notifs_before) == 1

        db_manager.delete_alert_rule(rule["id"])

        # Rule should be gone
        assert db_manager.get_alert_rule(rule["id"]) is None
        # Notification should be cascade-deleted
        notifs_after = db_manager.get_alert_notifications()
        assert len(notifs_after) == 0

    def test_insert_and_get_notification(self, db_manager):
        """insert_alert_notification + get_alert_notifications round-trip."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Test.", 5.0)

        notif_id = db_manager.insert_alert_notification(
            rule["id"], aid, "AAPL", "Rec changed BUY to SELL",
            previous_value="BUY", current_value="SELL"
        )
        assert notif_id > 0

        notifs = db_manager.get_alert_notifications()
        assert len(notifs) == 1
        assert notifs[0]["ticker"] == "AAPL"
        assert notifs[0]["message"] == "Rec changed BUY to SELL"
        assert notifs[0]["previous_value"] == "BUY"
        assert notifs[0]["current_value"] == "SELL"
        assert notifs[0]["acknowledged"] == 0

    def test_acknowledge_alert(self, db_manager):
        """acknowledge_alert marks notification as read."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Test.", 5.0)
        notif_id = db_manager.insert_alert_notification(
            rule["id"], aid, "AAPL", "Changed"
        )

        result = db_manager.acknowledge_alert(notif_id)
        assert result is True

        notifs = db_manager.get_alert_notifications()
        assert notifs[0]["acknowledged"] == 1

    def test_get_unacknowledged_count(self, db_manager):
        """get_unacknowledged_count returns correct count."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Test.", 5.0)

        db_manager.insert_alert_notification(rule["id"], aid, "AAPL", "Alert 1")
        db_manager.insert_alert_notification(rule["id"], aid, "AAPL", "Alert 2")
        db_manager.insert_alert_notification(rule["id"], aid, "AAPL", "Alert 3")

        assert db_manager.get_unacknowledged_count() == 3

        # Acknowledge one
        notifs = db_manager.get_alert_notifications()
        db_manager.acknowledge_alert(notifs[0]["id"])

        assert db_manager.get_unacknowledged_count() == 2

    def test_get_notifications_unacknowledged_filter(self, db_manager):
        """get_alert_notifications with unacknowledged_only=True filters correctly."""
        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        aid = db_manager.insert_analysis("AAPL", "BUY", 0.8, 0.5, "Test.", 5.0)

        nid1 = db_manager.insert_alert_notification(rule["id"], aid, "AAPL", "Alert 1")
        db_manager.insert_alert_notification(rule["id"], aid, "AAPL", "Alert 2")

        # Acknowledge the first one
        db_manager.acknowledge_alert(nid1)

        all_notifs = db_manager.get_alert_notifications(unacknowledged_only=False)
        assert len(all_notifs) == 2

        unread_notifs = db_manager.get_alert_notifications(unacknowledged_only=True)
        assert len(unread_notifs) == 1
        assert unread_notifs[0]["message"] == "Alert 2"

    def test_alert_tables_created(self, db_manager, tmp_db_path):
        """Verify alert_rules and alert_notifications tables exist."""
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "alert_rules" in tables
        assert "alert_notifications" in tables
