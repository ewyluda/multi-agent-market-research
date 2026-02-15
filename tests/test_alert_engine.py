"""Tests for AlertEngine alert evaluation logic."""

import pytest

from src.alert_engine import AlertEngine
from src.database import DatabaseManager


class TestAlertEngine:
    """Tests for AlertEngine.evaluate_alerts and rule evaluation."""

    def _insert_analysis(self, db_manager, ticker="AAPL", recommendation="BUY", confidence=0.8):
        """Helper to insert a test analysis."""
        return db_manager.insert_analysis(
            ticker=ticker,
            recommendation=recommendation,
            confidence_score=confidence,
            overall_sentiment_score=0.5,
            solution_agent_reasoning="Test reasoning.",
            duration_seconds=10.0,
        )

    def test_recommendation_change_triggers_alert(self, db_manager):
        """Alert fires when recommendation changes between analyses."""
        self._insert_analysis(db_manager, recommendation="BUY")
        aid2 = self._insert_analysis(db_manager, recommendation="SELL")

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 1
        assert "BUY" in triggered[0]["message"]
        assert "SELL" in triggered[0]["message"]
        assert triggered[0]["previous_value"] == "BUY"
        assert triggered[0]["current_value"] == "SELL"

    def test_recommendation_no_change_no_alert(self, db_manager):
        """No alert when recommendation stays the same."""
        self._insert_analysis(db_manager, recommendation="BUY")
        aid2 = self._insert_analysis(db_manager, recommendation="BUY")

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 0

    def test_recommendation_change_no_previous(self, db_manager):
        """No trigger for recommendation_change on first analysis (no previous)."""
        aid = self._insert_analysis(db_manager, recommendation="BUY")

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 0

    def test_score_above_triggers(self, db_manager):
        """Alert fires when synthetic score crosses from below to above threshold."""
        # Previous BUY 0.3 -> score 30 (below 50), then BUY 0.8 -> score 80 (above 50)
        self._insert_analysis(db_manager, recommendation="BUY", confidence=0.3)
        aid = self._insert_analysis(db_manager, recommendation="BUY", confidence=0.8)

        db_manager.create_alert_rule("AAPL", "score_above", threshold=50)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 1
        assert "above" in triggered[0]["message"].lower()

    def test_score_above_not_triggered(self, db_manager):
        """No alert when score does not cross above threshold."""
        # BUY 0.7 -> score 70, BUY 0.8 -> score 80 (already above threshold on previous)
        self._insert_analysis(db_manager, recommendation="BUY", confidence=0.7)
        aid = self._insert_analysis(db_manager, recommendation="BUY", confidence=0.8)

        db_manager.create_alert_rule("AAPL", "score_above", threshold=50)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 0

    def test_score_below_triggers(self, db_manager):
        """Alert fires when synthetic score crosses from above to below threshold."""
        # Previous BUY 0.8 -> score 80 (above -50), then SELL 0.7 -> score -70 (below -50)
        self._insert_analysis(db_manager, recommendation="BUY", confidence=0.8)
        aid = self._insert_analysis(db_manager, recommendation="SELL", confidence=0.7)

        db_manager.create_alert_rule("AAPL", "score_below", threshold=-50)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 1
        assert "below" in triggered[0]["message"].lower()

    def test_score_below_not_triggered(self, db_manager):
        """No alert when score stays below threshold without crossing."""
        # SELL 0.8 -> score -80, SELL 0.9 -> score -90 (already below on previous)
        self._insert_analysis(db_manager, recommendation="SELL", confidence=0.8)
        aid = self._insert_analysis(db_manager, recommendation="SELL", confidence=0.9)

        db_manager.create_alert_rule("AAPL", "score_below", threshold=-50)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 0

    def test_confidence_above_triggers(self, db_manager):
        """Alert fires when confidence crosses from below to above threshold."""
        self._insert_analysis(db_manager, confidence=0.6)
        aid = self._insert_analysis(db_manager, confidence=0.9)

        db_manager.create_alert_rule("AAPL", "confidence_above", threshold=0.8)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 1
        assert "above" in triggered[0]["message"].lower()

    def test_confidence_below_triggers(self, db_manager):
        """Alert fires when confidence crosses from above to below threshold."""
        self._insert_analysis(db_manager, confidence=0.8)
        aid = self._insert_analysis(db_manager, confidence=0.3)

        db_manager.create_alert_rule("AAPL", "confidence_below", threshold=0.5)
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid)

        assert len(triggered) == 1
        assert "below" in triggered[0]["message"].lower()

    def test_disabled_rule_not_evaluated(self, db_manager):
        """Disabled rules are skipped during evaluation."""
        self._insert_analysis(db_manager, recommendation="BUY")
        aid2 = self._insert_analysis(db_manager, recommendation="SELL")

        rule = db_manager.create_alert_rule("AAPL", "recommendation_change")
        db_manager.update_alert_rule(rule["id"], enabled=False)

        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 0

    def test_multiple_rules_multiple_triggers(self, db_manager):
        """Multiple matching rules all fire independently."""
        self._insert_analysis(db_manager, recommendation="BUY", confidence=0.5)
        aid2 = self._insert_analysis(db_manager, recommendation="SELL", confidence=0.9)

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        db_manager.create_alert_rule("AAPL", "confidence_above", threshold=0.8)

        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 2

    def test_notification_stored_in_db(self, db_manager):
        """Triggered alerts are persisted as notifications in the database."""
        self._insert_analysis(db_manager, recommendation="BUY")
        aid2 = self._insert_analysis(db_manager, recommendation="SELL")

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        engine = AlertEngine(db_manager)
        engine.evaluate_alerts("AAPL", aid2)

        notifications = db_manager.get_alert_notifications()
        assert len(notifications) == 1
        assert notifications[0]["ticker"] == "AAPL"
        assert notifications[0]["acknowledged"] == 0
        assert "BUY" in notifications[0]["message"]
        assert "SELL" in notifications[0]["message"]

    def test_triggered_alert_includes_playbook_fields(self, db_manager):
        """Triggered notifications include trigger_context, change_summary, and suggested_action."""
        self._insert_analysis(db_manager, recommendation="HOLD", confidence=0.5)
        aid2 = db_manager.insert_analysis(
            ticker="AAPL",
            recommendation="BUY",
            confidence_score=0.82,
            overall_sentiment_score=0.44,
            solution_agent_reasoning="Momentum improving.",
            duration_seconds=8.0,
            score=74,
            analysis_payload={
                "recommendation": "BUY",
                "score": 74,
                "confidence": 0.82,
                "decision_card": {"action": "buy"},
                "changes_since_last_run": {
                    "summary": "Recommendation changed from HOLD to BUY",
                    "material_changes": [{"type": "recommendation_change", "label": "HOLD -> BUY"}],
                },
            },
            change_summary={
                "summary": "Recommendation changed from HOLD to BUY",
                "material_changes": [{"type": "recommendation_change", "label": "HOLD -> BUY"}],
            },
        )

        db_manager.create_alert_rule("AAPL", "recommendation_change")
        engine = AlertEngine(db_manager)
        triggered = engine.evaluate_alerts("AAPL", aid2)

        assert len(triggered) == 1
        notification = triggered[0]
        assert notification["trigger_context"]["rule_type"] == "recommendation_change"
        assert notification["change_summary"]["summary"] == "Recommendation changed from HOLD to BUY"
        assert isinstance(notification["suggested_action"], str)
        assert len(notification["suggested_action"]) > 0
