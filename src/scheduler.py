"""Background scheduler for recurring analysis."""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import yfinance as yf
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import Config
from .database import DatabaseManager
from .av_rate_limiter import AVRateLimiter
from .av_cache import AVCache

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback for older runtimes
    ZoneInfo = None  # type: ignore


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
        self.config = config or self._get_config_dict()
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def _get_config_dict(self) -> Dict[str, Any]:
        """Convert Config class attributes to a plain dict."""
        config_dict = {}
        for attr in dir(Config):
            if not attr.startswith("_") and not callable(getattr(Config, attr)):
                config_dict[attr] = getattr(Config, attr)
        config_dict["llm_config"] = Config.get_llm_config()
        return config_dict

    async def start(self):
        """Load all enabled schedules from DB and start the scheduler."""
        if self._running:
            return

        schedules = self.db_manager.get_schedules()
        for schedule in schedules:
            if schedule.get("enabled"):
                self._add_job(schedule)

        self._add_catalyst_scan_job()
        self._add_calibration_job()
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

    def _is_earnings_catalyst_enabled(self) -> bool:
        """Whether earnings catalyst scheduling is enabled and supported."""
        return (
            bool(self.config.get("CATALYST_SCHEDULER_ENABLED", True))
            and str(self.config.get("CATALYST_SOURCE", "earnings")).lower() == "earnings"
        )

    def _is_macro_catalyst_enabled(self) -> bool:
        """Whether macro catalyst scheduling is enabled."""
        return bool(self.config.get("MACRO_CATALYSTS_ENABLED", True))

    def _is_calibration_enabled(self) -> bool:
        """Whether daily calibration jobs are enabled."""
        return bool(self.config.get("CALIBRATION_ENABLED", True))

    def _macro_event_types(self) -> List[str]:
        """Normalize configured macro event type list."""
        raw = self.config.get("MACRO_CATALYST_EVENT_TYPES", ["fomc", "cpi", "nfp"])
        if isinstance(raw, str):
            values = [part.strip().lower() for part in raw.split(",") if part.strip()]
        elif isinstance(raw, (list, tuple, set)):
            values = [str(part).strip().lower() for part in raw if str(part).strip()]
        else:
            values = []
        return [event for event in values if event in {"fomc", "cpi", "nfp"}] or ["fomc", "cpi", "nfp"]

    def _get_non_negative_int_config(self, key: str, default: int) -> int:
        """Read integer config value while preserving explicit zero values."""
        raw_value = self.config.get(key, default)
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            parsed = int(default)
        return max(0, parsed)

    def _add_catalyst_scan_job(self):
        """Add periodic catalyst scan job if enabled."""
        if not (self._is_earnings_catalyst_enabled() or self._is_macro_catalyst_enabled()):
            return

        scan_interval = int(self.config.get("CATALYST_SCAN_INTERVAL_MINUTES", 60) or 60)
        scan_interval = max(1, scan_interval)
        job_id = "catalyst_scan"

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._scan_catalysts,
            "interval",
            minutes=scan_interval,
            id=job_id,
            replace_existing=True,
            next_run_time=datetime.utcnow() + timedelta(minutes=1),
        )
        logger.info(
            "Added catalyst scan job every %sm (earnings=%s, macro=%s)",
            scan_interval,
            self._is_earnings_catalyst_enabled(),
            self._is_macro_catalyst_enabled(),
        )

    def _add_calibration_job(self):
        """Add the daily post-close calibration job when enabled."""
        if not self._is_calibration_enabled():
            return

        job_id = "calibration_daily"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        timezone_name = str(self.config.get("CALIBRATION_TIMEZONE", "America/New_York"))
        tzinfo = ZoneInfo(timezone_name) if ZoneInfo else timezone.utc
        hour = int(self.config.get("CALIBRATION_CRON_HOUR", 17) or 17)
        minute = int(self.config.get("CALIBRATION_CRON_MINUTE", 30) or 30)

        self.scheduler.add_job(
            self._run_calibration_job,
            "cron",
            hour=hour,
            minute=minute,
            timezone=tzinfo,
            id=job_id,
            replace_existing=True,
        )
        logger.info("Added calibration job at %02d:%02d %s", hour, minute, timezone_name)

    def _coerce_to_utc_date(self, value: Any) -> Optional[date]:
        """Best-effort conversion for pandas/datetime/string date values."""
        dt_obj: Optional[datetime] = None

        if value is None:
            return None

        if isinstance(value, datetime):
            dt_obj = value
        elif isinstance(value, date):
            return value
        elif hasattr(value, "to_pydatetime"):
            try:
                dt_obj = value.to_pydatetime()
            except Exception:
                dt_obj = None
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                dt_obj = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                try:
                    dt_obj = datetime.fromisoformat(text.split(" ")[0])
                except ValueError:
                    return None

        if dt_obj is None:
            return None
        if dt_obj.tzinfo is not None:
            return dt_obj.astimezone(timezone.utc).date()
        return dt_obj.date()

    async def _resolve_next_earnings_date(self, ticker: str, lookback_days: int = 0) -> Optional[date]:
        """Resolve the nearest earnings date, allowing bounded past lookback."""
        def _fetch_earnings_dates():
            return yf.Ticker(ticker).earnings_dates

        earnings_dates = await asyncio.to_thread(_fetch_earnings_dates)
        if earnings_dates is None:
            return None

        if hasattr(earnings_dates, "index"):
            candidates: List[Any] = list(earnings_dates.index)
        elif isinstance(earnings_dates, (list, tuple)):
            candidates = list(earnings_dates)
        else:
            candidates = [earnings_dates]

        today = datetime.utcnow().date()
        lookback = max(0, int(lookback_days))
        window_start = today - timedelta(days=lookback)
        normalized: List[date] = []
        for item in candidates:
            parsed = self._coerce_to_utc_date(item)
            if parsed and parsed >= window_start:
                normalized.append(parsed)

        if not normalized:
            return None
        return min(
            normalized,
            key=lambda d: (
                abs((d - today).days),
                0 if d >= today else 1,  # Prefer future date on equal distance.
                d,
            ),
        )

    async def _scan_catalysts(self):
        """Scan enabled schedules for catalyst-triggered analysis windows."""
        if not (self._is_earnings_catalyst_enabled() or self._is_macro_catalyst_enabled()):
            return

        schedules = [s for s in self.db_manager.get_schedules() if s.get("enabled")]
        if not schedules:
            return

        today = datetime.utcnow().date()
        if self._is_earnings_catalyst_enabled():
            await self._scan_earnings_catalysts(schedules, today)
        if self._is_macro_catalyst_enabled():
            await self._scan_macro_catalysts(schedules, today)

    async def _scan_earnings_catalysts(self, schedules: List[Dict[str, Any]], today: date):
        """Scan schedules for earnings-triggered runs."""
        pre_days = self._get_non_negative_int_config("CATALYST_PRE_DAYS", 1)
        post_days = self._get_non_negative_int_config("CATALYST_POST_DAYS", 1)

        for schedule in schedules:
            schedule_id = schedule["id"]
            ticker = schedule["ticker"]

            try:
                earnings_date = await self._resolve_next_earnings_date(
                    ticker,
                    lookback_days=post_days,
                )
            except Exception as exc:
                logger.warning(f"Failed to resolve earnings date for {ticker}: {exc}")
                continue

            if not earnings_date:
                continue

            event_date_iso = earnings_date.isoformat()
            trigger_map = {
                "catalyst_pre": earnings_date - timedelta(days=pre_days),
                "catalyst_post": earnings_date + timedelta(days=post_days),
            }

            for run_reason, trigger_date in trigger_map.items():
                if trigger_date != today:
                    continue
                await self._run_catalyst_if_needed(
                    schedule_id=schedule_id,
                    ticker=ticker,
                    run_reason=run_reason,
                    catalyst_event_type="earnings",
                    catalyst_event_date=event_date_iso,
                )

    async def _scan_macro_catalysts(self, schedules: List[Dict[str, Any]], today: date):
        """Scan seeded macro events for T-1 / T+0 catalyst runs."""
        pre_days = self._get_non_negative_int_config("MACRO_CATALYST_PRE_DAYS", 1)
        run_day_enabled = bool(self.config.get("MACRO_CATALYST_DAY_ENABLED", True))
        event_types = self._macro_event_types()

        window_start = today.isoformat()
        window_end = (today + timedelta(days=max(1, pre_days))).isoformat()
        macro_events = self.db_manager.list_macro_events(
            date_from=window_start,
            date_to=window_end,
            enabled_only=True,
            event_types=event_types,
        )

        for event in macro_events:
            event_type = str(event.get("event_type", "")).lower()
            event_date = self._coerce_to_utc_date(event.get("event_date"))
            if not event_date or event_type not in {"fomc", "cpi", "nfp"}:
                continue

            event_date_iso = event_date.isoformat()
            run_reasons: List[str] = []
            if (event_date - timedelta(days=pre_days)) == today:
                run_reasons.append("catalyst_pre")
            if run_day_enabled and event_date == today:
                run_reasons.append("catalyst_day")

            if not run_reasons:
                continue

            for schedule in schedules:
                for run_reason in run_reasons:
                    await self._run_catalyst_if_needed(
                        schedule_id=schedule["id"],
                        ticker=schedule["ticker"],
                        run_reason=run_reason,
                        catalyst_event_type=event_type,
                        catalyst_event_date=event_date_iso,
                    )

    async def _run_catalyst_if_needed(
        self,
        *,
        schedule_id: int,
        ticker: str,
        run_reason: str,
        catalyst_event_type: str,
        catalyst_event_date: str,
    ):
        """Deduplicate and run one catalyst-triggered schedule analysis."""
        already_exists = self.db_manager.schedule_run_exists(
            schedule_id=schedule_id,
            run_reason=run_reason,
            catalyst_event_type=catalyst_event_type,
            catalyst_event_date=catalyst_event_date,
        )
        if already_exists:
            return

        logger.info(
            "Running catalyst analysis for %s (%s, %s=%s)",
            ticker,
            run_reason,
            catalyst_event_type,
            catalyst_event_date,
        )
        await self._run_schedule_analysis(
            schedule_id=schedule_id,
            run_reason=run_reason,
            catalyst_event_type=catalyst_event_type,
            catalyst_event_date=catalyst_event_date,
            update_next_run=False,
        )

    async def _run_scheduled_analysis(self, schedule_id: int):
        """Execute an interval-based scheduled analysis."""
        await self._run_schedule_analysis(
            schedule_id=schedule_id,
            run_reason="scheduled",
            catalyst_event_type=None,
            catalyst_event_date=None,
            update_next_run=True,
        )

    async def _run_schedule_analysis(
        self,
        schedule_id: int,
        run_reason: str = "scheduled",
        catalyst_event_type: Optional[str] = None,
        catalyst_event_date: Optional[str] = None,
        update_next_run: bool = True,
    ):
        """Execute a scheduled analysis run (interval or catalyst)."""
        from .orchestrator import Orchestrator  # Lazy import to avoid circular

        schedule = self.db_manager.get_schedule(schedule_id)
        if not schedule or not schedule.get("enabled"):
            return

        ticker = schedule["ticker"]
        agents_str = schedule.get("agents")
        requested_agents = [a.strip() for a in agents_str.split(",")] if agents_str else None

        started_at = datetime.utcnow().isoformat()
        logger.info(f"Running {run_reason} analysis for {ticker} (schedule {schedule_id})")

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
                run_reason=run_reason,
                catalyst_event_type=catalyst_event_type,
                catalyst_event_date=catalyst_event_date,
            )

            # Update schedule timestamps
            update_fields = {"last_run_at": completed_at}
            if update_next_run:
                next_run = datetime.utcnow() + timedelta(minutes=schedule["interval_minutes"])
                update_fields["next_run_at"] = next_run.isoformat()
            self.db_manager.update_schedule(schedule_id, **update_fields)

            logger.info(f"{run_reason} analysis for {ticker} completed (success={result.get('success')})")

        except Exception as e:
            completed_at = datetime.utcnow().isoformat()
            self.db_manager.insert_schedule_run(
                schedule_id=schedule_id,
                analysis_id=None,
                started_at=started_at,
                completed_at=completed_at,
                success=False,
                error=str(e),
                run_reason=run_reason,
                catalyst_event_type=catalyst_event_type,
                catalyst_event_date=catalyst_event_date,
            )
            self.db_manager.update_schedule(schedule_id, last_run_at=completed_at)
            logger.error(f"{run_reason} analysis for {ticker} failed: {e}")

    def _fallback_up_probability(self, recommendation: str) -> float:
        """Fallback mapping from recommendation to up probability."""
        rec = str(recommendation or "HOLD").upper()
        if rec == "BUY":
            return 0.65
        if rec == "SELL":
            return 0.35
        return 0.50

    def _is_direction_correct(self, recommendation: str, realized_return_pct: float) -> bool:
        """Direction correctness rule by recommendation."""
        rec = str(recommendation or "HOLD").upper()
        if rec == "BUY":
            return realized_return_pct > 0
        if rec == "SELL":
            return realized_return_pct < 0
        return abs(realized_return_pct) <= 2.0

    async def _resolve_close_on_or_after(self, ticker: str, target_date: str) -> Tuple[Optional[float], Optional[str]]:
        """Resolve close price on target date or next available trading date."""

        def _fetch_history():
            target = datetime.fromisoformat(target_date).date()
            end = target + timedelta(days=10)
            hist = yf.Ticker(ticker).history(
                start=target.isoformat(),
                end=end.isoformat(),
                interval="1d",
                auto_adjust=False,
            )
            if hist is None or getattr(hist, "empty", True):
                return None

            for index, row in hist.iterrows():
                close = row.get("Close")
                if close is None:
                    continue
                try:
                    close_value = float(close)
                except (TypeError, ValueError):
                    continue
                if close_value <= 0:
                    continue

                if hasattr(index, "date"):
                    trading_date = index.date().isoformat()
                else:
                    trading_date = str(index)[:10]
                return close_value, trading_date
            return None

        result = await asyncio.to_thread(_fetch_history)
        if not result:
            return None, None
        return result[0], result[1]

    def _mean_or_none(self, values: List[Optional[float]]) -> Optional[float]:
        """Compute arithmetic mean ignoring null values."""
        valid = [float(v) for v in values if v is not None]
        if not valid:
            return None
        return sum(valid) / len(valid)

    async def _run_calibration_job(self):
        """Evaluate due outcomes and refresh daily calibration snapshots."""
        if not self._is_calibration_enabled():
            return

        as_of_date = datetime.now(timezone.utc).date().isoformat()
        due_outcomes = self.db_manager.list_due_outcomes(as_of_date)
        if due_outcomes:
            logger.info("Calibration job evaluating %s due outcomes", len(due_outcomes))

        for outcome in due_outcomes:
            outcome_id = outcome["id"]
            ticker = outcome["ticker"]
            recommendation = outcome.get("recommendation")
            target_date = outcome.get("target_date")
            baseline_price = outcome.get("baseline_price")

            try:
                baseline = float(baseline_price)
            except (TypeError, ValueError):
                baseline = 0.0

            if baseline <= 0 or not target_date:
                self.db_manager.complete_outcome(
                    outcome_id,
                    status="skipped",
                )
                continue

            try:
                realized_price, _ = await self._resolve_close_on_or_after(ticker, target_date)
            except Exception as exc:
                logger.warning("Calibration price lookup failed for %s: %s", ticker, exc)
                realized_price = None

            if realized_price is None:
                self.db_manager.complete_outcome(
                    outcome_id,
                    status="skipped",
                )
                continue

            realized_return_pct = ((realized_price - baseline) / baseline) * 100.0
            direction_correct = self._is_direction_correct(recommendation, realized_return_pct)
            outcome_up = realized_return_pct > 0

            predicted_up_probability = outcome.get("predicted_up_probability")
            try:
                pred_prob = float(predicted_up_probability)
            except (TypeError, ValueError):
                pred_prob = self._fallback_up_probability(str(recommendation or "HOLD"))
            pred_prob = max(0.0, min(1.0, pred_prob))

            brier_component = (pred_prob - (1.0 if outcome_up else 0.0)) ** 2

            self.db_manager.complete_outcome(
                outcome_id,
                realized_price=realized_price,
                realized_return_pct=realized_return_pct,
                direction_correct=direction_correct,
                outcome_up=outcome_up,
                brier_component=brier_component,
                status="complete",
                evaluated_at=datetime.utcnow().isoformat(),
            )

        window_start = (datetime.now(timezone.utc).date() - timedelta(days=180)).isoformat()
        for horizon in (1, 7, 30):
            completed = self.db_manager.list_completed_outcomes(
                horizon_days=horizon,
                since_date=window_start,
            )
            sample_size = len(completed)
            if sample_size == 0:
                continue

            directional_hits = sum(1 for row in completed if bool(row.get("direction_correct")))
            directional_accuracy = directional_hits / sample_size
            avg_realized_return = self._mean_or_none([row.get("realized_return_pct") for row in completed])
            mean_confidence = self._mean_or_none([row.get("confidence") for row in completed])
            brier_values = [row.get("brier_component") for row in completed]
            brier_score = self._mean_or_none(brier_values) or 0.0

            self.db_manager.upsert_calibration_snapshot(
                as_of_date=as_of_date,
                horizon_days=horizon,
                sample_size=sample_size,
                directional_accuracy=directional_accuracy,
                avg_realized_return_pct=avg_realized_return,
                mean_confidence=mean_confidence,
                brier_score=brier_score,
            )

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
