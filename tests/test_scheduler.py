"""Tests for AnalysisScheduler."""

from datetime import datetime, timedelta

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scheduler import AnalysisScheduler
from src.database import DatabaseManager
from src.av_rate_limiter import AVRateLimiter
from src.av_cache import AVCache


@pytest.fixture
def mock_db():
    """Create a mock DatabaseManager."""
    db = MagicMock(spec=DatabaseManager)
    db.get_schedules.return_value = []
    return db


@pytest.fixture
def scheduler(mock_db):
    """Create an AnalysisScheduler with mocked deps."""
    return AnalysisScheduler(
        db_manager=mock_db,
        rate_limiter=AVRateLimiter(100, 1000),
        av_cache=AVCache(),
        config={
            "CATALYST_SCHEDULER_ENABLED": True,
            "CATALYST_SOURCE": "earnings",
            "CATALYST_PRE_DAYS": 1,
            "CATALYST_POST_DAYS": 1,
            "CATALYST_SCAN_INTERVAL_MINUTES": 60,
            "MACRO_CATALYSTS_ENABLED": True,
            "MACRO_CATALYST_PRE_DAYS": 1,
            "MACRO_CATALYST_DAY_ENABLED": True,
            "MACRO_CATALYST_EVENT_TYPES": ["fomc", "cpi", "nfp"],
            "CALIBRATION_ENABLED": True,
            "CALIBRATION_TIMEZONE": "America/New_York",
            "CALIBRATION_CRON_HOUR": 17,
            "CALIBRATION_CRON_MINUTE": 30,
            "SIGNAL_CONTRACT_V2_ENABLED": False,
            "CALIBRATION_ECONOMICS_ENABLED": False,
            "PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "ALERTS_V2_ENABLED": False,
            "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": False,
            "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": False,
            "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
            "SCHEDULED_ALERTS_V2_ENABLED": False,
        },
    )


class TestSchedulerStartStop:
    """Tests for scheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_loads_schedules(self, scheduler, mock_db):
        """start() calls get_schedules and starts the APScheduler."""
        with patch.object(scheduler.scheduler, "start") as mock_start:
            await scheduler.start()

            mock_db.get_schedules.assert_called_once()
            mock_start.assert_called_once()
            assert scheduler._running is True

    @pytest.mark.asyncio
    async def test_start_adds_jobs_for_enabled(self, mock_db):
        """With enabled schedules in DB, jobs are added on start."""
        mock_db.get_schedules.return_value = [
            {"id": 1, "ticker": "AAPL", "interval_minutes": 60, "enabled": True},
            {"id": 2, "ticker": "NVDA", "interval_minutes": 120, "enabled": False},
            {"id": 3, "ticker": "TSLA", "interval_minutes": 30, "enabled": True},
        ]

        sched = AnalysisScheduler(
            db_manager=mock_db,
            rate_limiter=AVRateLimiter(100, 1000),
            av_cache=AVCache(),
            config={
                "CATALYST_SCHEDULER_ENABLED": True,
                "CATALYST_SOURCE": "earnings",
                "CATALYST_PRE_DAYS": 1,
                "CATALYST_POST_DAYS": 1,
                "CATALYST_SCAN_INTERVAL_MINUTES": 60,
                "MACRO_CATALYSTS_ENABLED": True,
                "MACRO_CATALYST_PRE_DAYS": 1,
                "MACRO_CATALYST_DAY_ENABLED": True,
                "MACRO_CATALYST_EVENT_TYPES": ["fomc", "cpi", "nfp"],
                "CALIBRATION_ENABLED": True,
                "CALIBRATION_TIMEZONE": "America/New_York",
                "CALIBRATION_CRON_HOUR": 17,
                "CALIBRATION_CRON_MINUTE": 30,
            },
        )

        with patch.object(sched.scheduler, "start"), \
             patch.object(sched, "_add_job") as mock_add:
            await sched.start()

            # Only enabled schedules (id=1 and id=3) should be added
            assert mock_add.call_count == 2
            added_ids = [call.args[0]["id"] for call in mock_add.call_args_list]
            assert 1 in added_ids
            assert 3 in added_ids
            assert 2 not in added_ids

    @pytest.mark.asyncio
    async def test_stop_shuts_down(self, scheduler):
        """stop() shuts down the scheduler."""
        with patch.object(scheduler.scheduler, "start"):
            await scheduler.start()

        with patch.object(scheduler.scheduler, "shutdown") as mock_shutdown:
            await scheduler.stop()

            mock_shutdown.assert_called_once_with(wait=False)
            assert scheduler._running is False


class TestSchedulerJobManagement:
    """Tests for adding/removing schedule jobs."""

    def test_add_schedule_creates_job(self, scheduler):
        """add_schedule with enabled=True creates a job when scheduler is running."""
        scheduler._running = True
        schedule = {"id": 1, "ticker": "AAPL", "interval_minutes": 60, "enabled": True}

        with patch.object(scheduler, "_add_job") as mock_add:
            scheduler.add_schedule(schedule)
            mock_add.assert_called_once_with(schedule)

    def test_remove_schedule_removes_job(self, scheduler):
        """remove_schedule removes the job for a given schedule ID."""
        with patch.object(scheduler, "_remove_job") as mock_remove:
            scheduler.remove_schedule(42)
            mock_remove.assert_called_once_with(42)


class TestSchedulerExecution:
    """Tests for scheduled analysis execution."""

    @pytest.mark.asyncio
    async def test_run_scheduled_analysis_success(self, scheduler, mock_db):
        """_run_scheduled_analysis calls Orchestrator and inserts a success run record."""
        mock_db.get_schedule.return_value = {
            "id": 1,
            "ticker": "AAPL",
            "interval_minutes": 60,
            "enabled": True,
            "agents": None,
        }

        mock_result = {
            "success": True,
            "analysis_id": 42,
        }

        with patch("src.orchestrator.Orchestrator") as MockOrch:
            mock_orch_instance = MockOrch.return_value
            mock_orch_instance.analyze_ticker = AsyncMock(return_value=mock_result)

            await scheduler._run_scheduled_analysis(1)

            # Orchestrator was called with correct ticker
            mock_orch_instance.analyze_ticker.assert_awaited_once_with("AAPL", None)

            # A success run was inserted
            mock_db.insert_schedule_run.assert_called_once()
            call_kwargs = mock_db.insert_schedule_run.call_args
            assert call_kwargs[1]["schedule_id"] == 1
            assert call_kwargs[1]["analysis_id"] == 42
            assert call_kwargs[1]["success"] is True
            assert call_kwargs[1]["error"] is None
            assert call_kwargs[1]["run_reason"] == "scheduled"
            assert call_kwargs[1]["catalyst_event_type"] is None
            assert call_kwargs[1]["catalyst_event_date"] is None

            # Schedule timestamps were updated
            mock_db.update_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scheduled_analysis_failure(self, scheduler, mock_db):
        """_run_scheduled_analysis inserts an error run record on Orchestrator failure."""
        mock_db.get_schedule.return_value = {
            "id": 1,
            "ticker": "AAPL",
            "interval_minutes": 60,
            "enabled": True,
            "agents": None,
        }

        with patch("src.orchestrator.Orchestrator") as MockOrch:
            mock_orch_instance = MockOrch.return_value
            mock_orch_instance.analyze_ticker = AsyncMock(side_effect=RuntimeError("LLM timeout"))

            await scheduler._run_scheduled_analysis(1)

            # An error run was inserted
            mock_db.insert_schedule_run.assert_called_once()
            call_kwargs = mock_db.insert_schedule_run.call_args
            assert call_kwargs[1]["schedule_id"] == 1
            assert call_kwargs[1]["analysis_id"] is None
            assert call_kwargs[1]["success"] is False
            assert "LLM timeout" in call_kwargs[1]["error"]
            assert call_kwargs[1]["run_reason"] == "scheduled"

    @pytest.mark.asyncio
    async def test_run_scheduled_analysis_applies_scheduled_rollout_overrides(self, mock_db):
        """Scheduler can enable v2 features for scheduled runs while global flags remain off."""
        mock_db.get_schedule.return_value = {
            "id": 1,
            "ticker": "AAPL",
            "interval_minutes": 60,
            "enabled": True,
            "agents": None,
        }

        sched = AnalysisScheduler(
            db_manager=mock_db,
            rate_limiter=AVRateLimiter(100, 1000),
            av_cache=AVCache(),
            config={
                "SIGNAL_CONTRACT_V2_ENABLED": False,
                "CALIBRATION_ECONOMICS_ENABLED": False,
                "PORTFOLIO_OPTIMIZER_V2_ENABLED": False,
                "ALERTS_V2_ENABLED": False,
                "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": True,
                "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
                "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": True,
                "SCHEDULED_ALERTS_V2_ENABLED": True,
                "CALIBRATION_ENABLED": True,
                "CALIBRATION_TIMEZONE": "America/New_York",
                "CALIBRATION_CRON_HOUR": 17,
                "CALIBRATION_CRON_MINUTE": 30,
            },
        )

        with patch("src.orchestrator.Orchestrator") as MockOrch:
            mock_orch_instance = MockOrch.return_value
            mock_orch_instance.analyze_ticker = AsyncMock(return_value={"success": True, "analysis_id": 99})

            await sched._run_scheduled_analysis(1)

            called_config = MockOrch.call_args.kwargs["config"]
            assert called_config["SIGNAL_CONTRACT_V2_ENABLED"] is True
            assert called_config["CALIBRATION_ECONOMICS_ENABLED"] is True
            assert called_config["PORTFOLIO_OPTIMIZER_V2_ENABLED"] is True
            assert called_config["ALERTS_V2_ENABLED"] is True


class TestSchedulerCatalysts:
    """Tests for catalyst scan behavior."""

    @pytest.mark.asyncio
    async def test_resolve_next_earnings_date_allows_bounded_lookback(self, scheduler):
        """Earnings resolver can include recent past dates when lookback is configured."""
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        far_future = today + timedelta(days=10)

        class FakeFrame:
            index = [yesterday, far_future]

        class FakeTicker:
            earnings_dates = FakeFrame()

        with patch("src.scheduler.yf.Ticker", return_value=FakeTicker()):
            resolved = await scheduler._resolve_next_earnings_date("AAPL", lookback_days=2)

        assert resolved == yesterday

    @pytest.mark.asyncio
    async def test_scan_catalysts_runs_pre_earnings_trigger(self, scheduler, mock_db):
        """Catalyst scan launches pre-earnings run when trigger date matches."""
        today = datetime.utcnow().date()
        earnings_date = today + timedelta(days=1)

        mock_db.get_schedules.return_value = [
            {"id": 11, "ticker": "AAPL", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.schedule_run_exists.return_value = False

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=earnings_date)), \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

            mock_run.assert_awaited_once_with(
                schedule_id=11,
                run_reason="catalyst_pre",
                catalyst_event_type="earnings",
                catalyst_event_date=earnings_date.isoformat(),
                update_next_run=False,
            )

    @pytest.mark.asyncio
    async def test_scan_catalysts_runs_post_earnings_trigger(self, scheduler, mock_db):
        """Catalyst scan launches post-earnings run when trigger date matches."""
        today = datetime.utcnow().date()
        earnings_date = today - timedelta(days=2)
        scheduler.config["CATALYST_POST_DAYS"] = 2

        mock_db.get_schedules.return_value = [
            {"id": 12, "ticker": "MSFT", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.schedule_run_exists.return_value = False

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=earnings_date)) as mock_resolve, \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

            mock_resolve.assert_awaited_once_with("MSFT", lookback_days=2)
            mock_run.assert_awaited_once_with(
                schedule_id=12,
                run_reason="catalyst_post",
                catalyst_event_type="earnings",
                catalyst_event_date=earnings_date.isoformat(),
                update_next_run=False,
            )

    @pytest.mark.asyncio
    async def test_scan_catalysts_honors_zero_day_earnings_offsets(self, scheduler, mock_db):
        """Explicit zero-day pre/post settings trigger same-day catalyst windows."""
        today = datetime.utcnow().date()
        scheduler.config["MACRO_CATALYSTS_ENABLED"] = False
        scheduler.config["CATALYST_PRE_DAYS"] = 0
        scheduler.config["CATALYST_POST_DAYS"] = 0

        mock_db.get_schedules.return_value = [
            {"id": 14, "ticker": "AAPL", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.schedule_run_exists.return_value = False

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=today)) as mock_resolve, \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

        mock_resolve.assert_awaited_once_with("AAPL", lookback_days=0)
        assert mock_run.await_count == 2
        run_reasons = [call.kwargs["run_reason"] for call in mock_run.await_args_list]
        assert run_reasons == ["catalyst_pre", "catalyst_post"]

    @pytest.mark.asyncio
    async def test_scan_catalysts_skips_duplicate_event_reason(self, scheduler, mock_db):
        """Catalyst scan does not run duplicate schedule/event/reason."""
        today = datetime.utcnow().date()
        earnings_date = today + timedelta(days=1)

        mock_db.get_schedules.return_value = [
            {"id": 13, "ticker": "NVDA", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.schedule_run_exists.return_value = True

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=earnings_date)), \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

            mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_scan_catalysts_runs_macro_pre_and_day(self, scheduler, mock_db):
        """Macro catalysts trigger pre-day and day runs with correct metadata."""
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)

        mock_db.get_schedules.return_value = [
            {"id": 21, "ticker": "AAPL", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.list_macro_events.return_value = [
            {"event_type": "fomc", "event_date": tomorrow.isoformat(), "enabled": 1},
            {"event_type": "cpi", "event_date": today.isoformat(), "enabled": 1},
        ]
        mock_db.schedule_run_exists.return_value = False

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=None)), \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

        assert mock_run.await_count == 2
        first_call = mock_run.await_args_list[0].kwargs
        second_call = mock_run.await_args_list[1].kwargs

        assert first_call["run_reason"] == "catalyst_pre"
        assert first_call["catalyst_event_type"] == "fomc"
        assert first_call["catalyst_event_date"] == tomorrow.isoformat()

        assert second_call["run_reason"] == "catalyst_day"
        assert second_call["catalyst_event_type"] == "cpi"
        assert second_call["catalyst_event_date"] == today.isoformat()

    @pytest.mark.asyncio
    async def test_scan_catalysts_skips_duplicate_macro_event_reason(self, scheduler, mock_db):
        """Macro catalyst scans deduplicate schedule/event/reason runs."""
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)

        mock_db.get_schedules.return_value = [
            {"id": 22, "ticker": "MSFT", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.list_macro_events.return_value = [
            {"event_type": "nfp", "event_date": tomorrow.isoformat(), "enabled": 1},
        ]
        mock_db.schedule_run_exists.return_value = True

        with patch.object(scheduler, "_resolve_next_earnings_date", new=AsyncMock(return_value=None)), \
             patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

        mock_run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_scan_catalysts_honors_zero_day_macro_pre_offset(self, scheduler, mock_db):
        """Macro pre-trigger should run same-day when pre offset is explicitly zero."""
        today = datetime.utcnow().date()
        scheduler.config["CATALYST_SCHEDULER_ENABLED"] = False
        scheduler.config["MACRO_CATALYST_PRE_DAYS"] = 0
        scheduler.config["MACRO_CATALYST_DAY_ENABLED"] = False

        mock_db.get_schedules.return_value = [
            {"id": 23, "ticker": "MSFT", "enabled": True, "interval_minutes": 60},
        ]
        mock_db.list_macro_events.return_value = [
            {"event_type": "cpi", "event_date": today.isoformat(), "enabled": 1},
        ]
        mock_db.schedule_run_exists.return_value = False

        with patch.object(scheduler, "_run_schedule_analysis", new=AsyncMock()) as mock_run:
            await scheduler._scan_catalysts()

        mock_run.assert_awaited_once_with(
            schedule_id=23,
            run_reason="catalyst_pre",
            catalyst_event_type="cpi",
            catalyst_event_date=today.isoformat(),
            update_next_run=False,
        )


class TestSchedulerCalibration:
    """Tests for daily calibration scheduler job."""

    @pytest.mark.asyncio
    async def test_calibration_job_processes_due_outcomes_and_snapshots(self, scheduler, mock_db):
        mock_db.list_due_outcomes.return_value = [
            {
                "id": 301,
                "ticker": "AAPL",
                "target_date": "2026-02-10",
                "baseline_price": 100.0,
                "recommendation": "BUY",
                "predicted_up_probability": 0.7,
                "confidence": 0.8,
            }
        ]
        mock_db.list_completed_outcomes.side_effect = [
            [
                {
                    "id": 1,
                    "horizon_days": 1,
                    "realized_return_pct": 2.0,
                    "direction_correct": 1,
                    "confidence": 0.8,
                    "brier_component": 0.09,
                }
            ],
            [],
            [],
        ]

        with patch.object(scheduler, "_resolve_close_on_or_after", new=AsyncMock(return_value=(102.0, "2026-02-10"))):
            await scheduler._run_calibration_job()

        assert mock_db.complete_outcome.call_count == 1
        kwargs = mock_db.complete_outcome.call_args.kwargs
        assert kwargs["status"] == "complete"
        assert kwargs["direction_correct"] is True
        assert round(kwargs["brier_component"], 4) == 0.09

        assert mock_db.upsert_calibration_snapshot.call_count == 1
        snap_kwargs = mock_db.upsert_calibration_snapshot.call_args.kwargs
        assert snap_kwargs["horizon_days"] == 1
        assert snap_kwargs["sample_size"] == 1

    @pytest.mark.asyncio
    async def test_calibration_job_uses_scheduled_economics_override(self, mock_db):
        """Scheduled economics override enables net-return fields even when global flag is off."""
        sched = AnalysisScheduler(
            db_manager=mock_db,
            rate_limiter=AVRateLimiter(100, 1000),
            av_cache=AVCache(),
            config={
                "CALIBRATION_ENABLED": True,
                "CALIBRATION_ECONOMICS_ENABLED": False,
                "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": True,
            },
        )

        mock_db.list_due_outcomes.return_value = [
            {
                "id": 401,
                "ticker": "AAPL",
                "target_date": "2026-02-10",
                "baseline_price": 100.0,
                "recommendation": "BUY",
                "predicted_up_probability": 0.7,
                "confidence": 0.8,
                "transaction_cost_bps": 10.0,
                "slippage_bps": 5.0,
            }
        ]
        mock_db.list_completed_outcomes.side_effect = [
            [
                {
                    "id": 1,
                    "horizon_days": 1,
                    "realized_return_pct": 2.0,
                    "realized_return_net_pct": 1.85,
                    "max_drawdown_pct": 1.2,
                    "utility_score": 1.25,
                    "direction_correct": 1,
                    "confidence": 0.8,
                    "brier_component": 0.09,
                }
            ],
            [],
            [],
        ]

        with patch.object(sched, "_resolve_close_and_drawdown_on_or_after", new=AsyncMock(return_value=(102.0, "2026-02-10", 99.0))):
            await sched._run_calibration_job()

        kwargs = mock_db.complete_outcome.call_args.kwargs
        assert kwargs["realized_return_net_pct"] is not None
        assert kwargs["max_drawdown_pct"] is not None
        assert kwargs["utility_score"] is not None
