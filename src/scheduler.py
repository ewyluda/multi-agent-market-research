"""Background scheduler for recurring analysis."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import DatabaseManager
from .av_rate_limiter import AVRateLimiter
from .av_cache import AVCache


logger = logging.getLogger(__name__)


class AnalysisScheduler:
    """Manages background scheduled analyses using APScheduler."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        rate_limiter: AVRateLimiter,
        av_cache: AVCache,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.db_manager = db_manager
        self.rate_limiter = rate_limiter
        self.av_cache = av_cache
        self.config = config or {}
        self.scheduler = AsyncIOScheduler()
        self._running = False

    async def start(self):
        """Load all enabled schedules from DB and start the scheduler."""
        if self._running:
            return

        schedules = self.db_manager.get_schedules()
        for schedule in schedules:
            if schedule.get("enabled"):
                self._add_job(schedule)

        self.scheduler.start()
        self._running = True
        logger.info(f"Scheduler started with {len(schedules)} schedules loaded")

    async def stop(self):
        """Shut down the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    def _add_job(self, schedule: Dict[str, Any]):
        """Add or replace an APScheduler job for a schedule."""
        job_id = f"schedule_{schedule['id']}"
        interval = schedule.get("interval_minutes", 60)

        # Remove existing job if any
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._run_scheduled_analysis,
            'interval',
            minutes=interval,
            id=job_id,
            args=[schedule["id"]],
            replace_existing=True,
            next_run_time=datetime.utcnow() + timedelta(minutes=interval),
        )
        logger.info(f"Added job {job_id} for {schedule['ticker']} every {interval}m")

    def _remove_job(self, schedule_id: int):
        """Remove an APScheduler job."""
        job_id = f"schedule_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def _run_scheduled_analysis(self, schedule_id: int):
        """Execute a scheduled analysis."""
        from .orchestrator import Orchestrator  # Lazy import to avoid circular

        schedule = self.db_manager.get_schedule(schedule_id)
        if not schedule or not schedule.get("enabled"):
            return

        ticker = schedule["ticker"]
        agents_str = schedule.get("agents")
        requested_agents = [a.strip() for a in agents_str.split(",")] if agents_str else None

        started_at = datetime.utcnow().isoformat()
        logger.info(f"Running scheduled analysis for {ticker} (schedule {schedule_id})")

        try:
            orch = Orchestrator(
                config=self.config,
                db_manager=self.db_manager,
                rate_limiter=self.rate_limiter,
                av_cache=self.av_cache,
            )
            result = await orch.analyze_ticker(ticker, requested_agents)

            completed_at = datetime.utcnow().isoformat()
            analysis_id = result.get("analysis_id") if result.get("success") else None

            self.db_manager.insert_schedule_run(
                schedule_id=schedule_id,
                analysis_id=analysis_id,
                started_at=started_at,
                completed_at=completed_at,
                success=result.get("success", False),
                error=result.get("error"),
            )

            # Update schedule timestamps
            next_run = datetime.utcnow() + timedelta(minutes=schedule["interval_minutes"])
            self.db_manager.update_schedule(
                schedule_id,
                last_run_at=completed_at,
                next_run_at=next_run.isoformat(),
            )

            logger.info(f"Scheduled analysis for {ticker} completed (success={result.get('success')})")

        except Exception as e:
            completed_at = datetime.utcnow().isoformat()
            self.db_manager.insert_schedule_run(
                schedule_id=schedule_id,
                analysis_id=None,
                started_at=started_at,
                completed_at=completed_at,
                success=False,
                error=str(e),
            )
            logger.error(f"Scheduled analysis for {ticker} failed: {e}")

    def add_schedule(self, schedule: Dict[str, Any]):
        """Add a new schedule job (call after DB insert)."""
        if schedule.get("enabled", True) and self._running:
            self._add_job(schedule)

    def remove_schedule(self, schedule_id: int):
        """Remove a schedule job (call after DB delete)."""
        self._remove_job(schedule_id)

    def update_schedule_job(self, schedule: Dict[str, Any]):
        """Update a schedule job (call after DB update)."""
        if not self._running:
            return
        if schedule.get("enabled"):
            self._add_job(schedule)
        else:
            self._remove_job(schedule["id"])
