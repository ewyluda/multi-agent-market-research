"""Tests for signal contract backfill utility."""

from src.backfill_signal_contract import run_signal_contract_backfill
from src.database import DatabaseManager


class TestSignalContractBackfill:
    """Backfill behavior and idempotency tests."""

    def test_backfill_updates_eligible_analysis(self, tmp_db_path):
        db = DatabaseManager(tmp_db_path)
        analysis_id = db.insert_analysis(
            ticker="AAPL",
            recommendation="BUY",
            confidence_score=0.72,
            overall_sentiment_score=0.22,
            solution_agent_reasoning="Thesis improving on quality and momentum.",
            duration_seconds=4.2,
            score=50,
            analysis_payload={
                "recommendation": "BUY",
                "confidence": 0.72,
                "score": 50,
                "summary": "Constructive setup.",
                "scenarios": {
                    "bull": {"probability": 0.4, "expected_return_pct": 10.0},
                    "base": {"probability": 0.4, "expected_return_pct": 3.0},
                    "bear": {"probability": 0.2, "expected_return_pct": -6.0},
                },
                "decision_card": {
                    "entry_zone": {"low": 180.0, "high": 185.0, "reference": 182.0},
                    "stop_loss": 172.0,
                    "targets": [195.0],
                    "invalidation_conditions": ["Break of 50DMA"],
                    "time_horizon": "MEDIUM_TERM",
                },
            },
        )
        db.insert_agent_result(
            analysis_id=analysis_id,
            agent_type="market",
            success=True,
            data={"trend": "uptrend", "current_price": 182.0, "average_volume": 1000000, "data_source": "alpha_vantage"},
            duration_seconds=0.5,
        )
        db.insert_agent_result(
            analysis_id=analysis_id,
            agent_type="news",
            success=True,
            data={"articles": [{"published_at": "2026-02-16T10:00:00Z"}], "data_source": "alpha_vantage"},
            duration_seconds=0.5,
        )

        report = run_signal_contract_backfill(
            db_path=tmp_db_path,
            days=365,
            batch_size=50,
        )
        assert report["eligible"] == 1
        assert report["updated"] == 1
        assert report["failed_validation"] == 0
        assert report["failed_write"] == 0

        latest = db.get_latest_analysis("AAPL")
        assert latest is not None
        assert latest["analysis_schema_version"] == "v2"
        assert latest["signal_contract_v2"]["schema_version"] == "2.0"
        assert latest["analysis"]["analysis_schema_version"] == "v2"
        assert latest["analysis"]["recommendation"] == "BUY"
        assert latest["analysis"]["signal_contract_v2"]["instrument_type"] == "US_EQUITY"

    def test_backfill_is_idempotent_for_existing_valid_contract(self, tmp_db_path):
        db = DatabaseManager(tmp_db_path)
        analysis_id = db.insert_analysis(
            ticker="MSFT",
            recommendation="HOLD",
            confidence_score=0.55,
            overall_sentiment_score=0.1,
            solution_agent_reasoning="Neutral setup.",
            duration_seconds=3.0,
            score=10,
            analysis_payload={
                "recommendation": "HOLD",
                "confidence": 0.55,
                "summary": "Neutral setup.",
                "scenarios": {
                    "bull": {"probability": 0.33, "expected_return_pct": 5.0},
                    "base": {"probability": 0.34, "expected_return_pct": 1.0},
                    "bear": {"probability": 0.33, "expected_return_pct": -4.0},
                },
            },
        )
        db.insert_agent_result(
            analysis_id=analysis_id,
            agent_type="market",
            success=True,
            data={"trend": "sideways", "current_price": 320.0, "average_volume": 900000},
            duration_seconds=0.5,
        )

        first = run_signal_contract_backfill(db_path=tmp_db_path, days=365, batch_size=25)
        second = run_signal_contract_backfill(db_path=tmp_db_path, days=365, batch_size=25)

        assert first["updated"] == 1
        assert second["updated"] == 0
        assert second["skipped_existing_valid"] >= 1

    def test_backfill_reports_missing_agent_rows(self, tmp_db_path):
        db = DatabaseManager(tmp_db_path)
        db.insert_analysis(
            ticker="NVDA",
            recommendation="BUY",
            confidence_score=0.7,
            overall_sentiment_score=0.2,
            solution_agent_reasoning="No payload row.",
            duration_seconds=2.0,
            score=20,
            analysis_payload=None,
        )
        db.insert_analysis(
            ticker="TSLA",
            recommendation="SELL",
            confidence_score=0.6,
            overall_sentiment_score=-0.1,
            solution_agent_reasoning="Payload exists but no agent rows.",
            duration_seconds=2.0,
            score=-15,
            analysis_payload={
                "recommendation": "SELL",
                "confidence": 0.6,
                "summary": "Weak setup.",
                "scenarios": {
                    "bull": {"probability": 0.2, "expected_return_pct": 7.0},
                    "base": {"probability": 0.3, "expected_return_pct": -1.0},
                    "bear": {"probability": 0.5, "expected_return_pct": -9.0},
                },
            },
        )

        report = run_signal_contract_backfill(
            db_path=tmp_db_path,
            days=365,
            batch_size=20,
        )
        assert report["eligible"] == 2
        assert report["updated"] == 0
        assert report["skipped_missing_payload"] == 0
        assert report["skipped_missing_agent_results"] == 2
