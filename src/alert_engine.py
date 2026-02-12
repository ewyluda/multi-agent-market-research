"""Alert evaluation engine for post-analysis notifications."""

import logging
from typing import Dict, Any, Optional, List

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class AlertEngine:
    """Evaluates alert rules after each analysis and generates notifications."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def evaluate_alerts(self, ticker: str, analysis_id: int) -> List[Dict[str, Any]]:
        """
        Evaluate all alert rules for a ticker after a new analysis.

        Returns list of triggered alert notification dicts.
        """
        # Get the new analysis
        new_analysis = self.db_manager.get_latest_analysis(ticker)
        if not new_analysis or new_analysis["id"] != analysis_id:
            return []

        # Get the previous analysis (second most recent)
        history = self.db_manager.get_analysis_history(ticker, limit=2)
        previous_analysis = history[1] if len(history) > 1 else None

        # Get enabled alert rules for this ticker
        all_rules = self.db_manager.get_alert_rules(ticker=ticker)
        enabled_rules = [r for r in all_rules if r.get("enabled", True)]

        triggered = []
        for rule in enabled_rules:
            notification = self._evaluate_rule(rule, new_analysis, previous_analysis)
            if notification:
                notif_id = self.db_manager.insert_alert_notification(
                    alert_rule_id=rule["id"],
                    analysis_id=analysis_id,
                    ticker=ticker,
                    message=notification["message"],
                    previous_value=notification.get("previous_value"),
                    current_value=notification.get("current_value"),
                )
                notification["id"] = notif_id
                triggered.append(notification)

        if triggered:
            logger.info(f"Triggered {len(triggered)} alerts for {ticker}")

        return triggered

    def _evaluate_rule(
        self,
        rule: Dict[str, Any],
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a single rule. Returns notification dict if triggered, None otherwise."""
        rule_type = rule["rule_type"]
        threshold = rule.get("threshold")

        if rule_type == "recommendation_change":
            return self._check_recommendation_change(current, previous)
        elif rule_type == "score_above":
            return self._check_score_threshold(current, previous, threshold, above=True)
        elif rule_type == "score_below":
            return self._check_score_threshold(current, previous, threshold, above=False)
        elif rule_type == "confidence_above":
            return self._check_confidence_threshold(current, previous, threshold, above=True)
        elif rule_type == "confidence_below":
            return self._check_confidence_threshold(current, previous, threshold, above=False)

        return None

    def _check_recommendation_change(self, current, previous):
        """Check if the recommendation changed from previous analysis."""
        if not previous:
            return None
        curr_rec = current.get("recommendation")
        prev_rec = previous.get("recommendation")
        if curr_rec and prev_rec and curr_rec != prev_rec:
            return {
                "message": f"Recommendation changed from {prev_rec} to {curr_rec}",
                "previous_value": prev_rec,
                "current_value": curr_rec,
            }
        return None

    def _synthetic_score(self, analysis: Optional[Dict[str, Any]]) -> Optional[float]:
        """Map recommendation + confidence to a synthetic score (-100..100)."""
        if not analysis:
            return None

        rec = analysis.get("recommendation", "HOLD")
        conf = analysis.get("confidence_score", 0.0) or 0.0
        if rec == "BUY":
            return conf * 100
        if rec == "SELL":
            return -conf * 100
        return 0.0

    def _check_score_threshold(self, current, previous, threshold, above=True):
        """
        Check if a synthetic score crosses the threshold.

        The analyses table stores confidence_score (0-1 float) but not the raw
        score (-100 to 100).  We derive a synthetic score from the recommendation
        and confidence:
            BUY  -> +confidence * 100
            SELL -> -confidence * 100
            HOLD -> 0
        """
        if threshold is None:
            return None

        score = self._synthetic_score(current)
        prev_score = self._synthetic_score(previous)
        if score is None or prev_score is None:
            return None

        if above and prev_score <= threshold and score > threshold:
            return {
                "message": f"Score {score:.0f} crossed above threshold {threshold}",
                "previous_value": str(round(prev_score)),
                "current_value": str(round(score)),
            }
        elif not above and prev_score >= threshold and score < threshold:
            return {
                "message": f"Score {score:.0f} crossed below threshold {threshold}",
                "previous_value": str(round(prev_score)),
                "current_value": str(round(score)),
            }
        return None

    def _check_confidence_threshold(self, current, previous, threshold, above=True):
        """Check if confidence crosses the threshold."""
        if threshold is None:
            return None
        confidence = current.get("confidence_score", 0.0) or 0.0
        prev_confidence = (previous.get("confidence_score", 0.0) or 0.0) if previous else None
        if prev_confidence is None:
            return None
        if above and prev_confidence <= threshold and confidence > threshold:
            return {
                "message": f"Confidence {confidence:.0%} crossed above {threshold:.0%}",
                "previous_value": f"{prev_confidence:.2f}",
                "current_value": f"{confidence:.2f}",
            }
        elif not above and prev_confidence >= threshold and confidence < threshold:
            return {
                "message": f"Confidence {confidence:.0%} crossed below {threshold:.0%}",
                "previous_value": f"{prev_confidence:.2f}",
                "current_value": f"{confidence:.2f}",
            }
        return None
