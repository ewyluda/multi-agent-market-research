"""Tests for AnalysisScheduler."""

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
