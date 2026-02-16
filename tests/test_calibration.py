"""Calibration-specific scheduler tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.av_cache import AVCache
from src.av_rate_limiter import AVRateLimiter
from src.database import DatabaseManager
from src.scheduler import AnalysisScheduler


@pytest.fixture
def mock_db():
    db = MagicMock(spec=DatabaseManager)
    db.get_schedules.return_value = []
    db.list_due_outcomes.return_value = []
    db.list_completed_outcomes.return_value = []
    return db


@pytest.fixture
def scheduler(mock_db):
    return AnalysisScheduler(
        db_manager=mock_db,
        rate_limiter=AVRateLimiter(100, 1000),
        av_cache=AVCache(),
        config={
            "CALIBRATION_ENABLED": True,
            "CALIBRATION_TIMEZONE": "America/New_York",
            "CALIBRATION_CRON_HOUR": 17,
            "CALIBRATION_CRON_MINUTE": 30,
        },
    )


def test_probability_fallback_mapping(scheduler):
    assert scheduler._fallback_up_probability("BUY") == 0.65
    assert scheduler._fallback_up_probability("HOLD") == 0.50
    assert scheduler._fallback_up_probability("SELL") == 0.35


def test_direction_correctness_rules(scheduler):
    assert scheduler._is_direction_correct("BUY", 1.2) is True
    assert scheduler._is_direction_correct("BUY", -0.1) is False

    assert scheduler._is_direction_correct("SELL", -0.5) is True
    assert scheduler._is_direction_correct("SELL", 0.2) is False

    assert scheduler._is_direction_correct("HOLD", 1.5) is True
    assert scheduler._is_direction_correct("HOLD", 2.1) is False


@pytest.mark.asyncio
async def test_run_calibration_job_computes_brier_and_direction(scheduler, mock_db):
    mock_db.list_due_outcomes.return_value = [
        {
            "id": 101,
            "ticker": "AAPL",
            "target_date": "2026-02-10",
            "baseline_price": 100.0,
            "recommendation": "BUY",
            "predicted_up_probability": None,
            "confidence": 0.7,
        }
    ]
    mock_db.list_completed_outcomes.side_effect = [[], [], []]

    with patch.object(scheduler, "_resolve_close_on_or_after", new=AsyncMock(return_value=(103.0, "2026-02-10"))):
        await scheduler._run_calibration_job()

    assert mock_db.complete_outcome.call_count == 1
    kwargs = mock_db.complete_outcome.call_args.kwargs
    assert kwargs["status"] == "complete"
    assert kwargs["direction_correct"] is True
    assert round(kwargs["realized_return_pct"], 4) == 3.0
    assert round(kwargs["brier_component"], 4) == 0.1225


@pytest.mark.asyncio
async def test_resolve_close_rolls_to_next_trading_day(scheduler):
    class FakeFrame:
        empty = False

        def iterrows(self):
            yield datetime(2026, 2, 9), {"Close": 250.5}  # Monday close after weekend target

    class FakeTicker:
        def history(self, **kwargs):
            return FakeFrame()

    with patch("src.scheduler.yf.Ticker", return_value=FakeTicker()):
        close, trading_date = await scheduler._resolve_close_on_or_after("MSFT", "2026-02-07")

    assert close == 250.5
    assert trading_date == "2026-02-09"
