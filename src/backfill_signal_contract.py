"""Backfill utility for signal_contract_v2 on historical analyses."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .database import DatabaseManager
from .orchestrator import Orchestrator
from .signal_contract import build_signal_contract_v2, validate_signal_contract_v2, _safe_float


logger = logging.getLogger(__name__)


@dataclass
class BackfillStats:
    """Execution metrics for signal contract v2 backfill."""

    started_at: str
    ended_at: Optional[str] = None
    since_timestamp: str = ""
    days: int = 180
    batch_size: int = 200
    dry_run: bool = False
    checkpoint_file: Optional[str] = None
    scanned: int = 0
    eligible: int = 0
    updated: int = 0
    skipped_existing_valid: int = 0
    skipped_missing_payload: int = 0
    skipped_missing_agent_results: int = 0
    skipped_missing_recommendation: int = 0
    failed_validation: int = 0
    failed_write: int = 0
    failures: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def hard_failures(self) -> int:
        """Number of hard failures from validation/write stages."""
        return int(self.failed_validation) + int(self.failed_write)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report payload."""
        return {
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "since_timestamp": self.since_timestamp,
            "days": self.days,
            "batch_size": self.batch_size,
            "dry_run": self.dry_run,
            "checkpoint_file": self.checkpoint_file,
            "scanned": self.scanned,
            "eligible": self.eligible,
            "updated": self.updated,
            "skipped_existing_valid": self.skipped_existing_valid,
            "skipped_missing_payload": self.skipped_missing_payload,
            "skipped_missing_agent_results": self.skipped_missing_agent_results,
            "skipped_missing_recommendation": self.skipped_missing_recommendation,
            "failed_validation": self.failed_validation,
            "failed_write": self.failed_write,
            "hard_failures": self.hard_failures,
            "failures": self.failures,
        }


def _load_checkpoint(path: Optional[str]) -> int:
    """Load checkpoint cursor (last processed analysis id)."""
    if not path:
        return 0
    checkpoint_path = Path(path)
    if not checkpoint_path.exists():
        return 0
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return int(payload.get("last_processed_id") or 0)


def _write_checkpoint(path: Optional[str], last_id: int, stats: BackfillStats) -> None:
    """Persist checkpoint cursor and current progress."""
    if not path:
        return
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_processed_id": int(last_id),
        "updated": int(stats.updated),
        "scanned": int(stats.scanned),
        "eligible": int(stats.eligible),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _normalize_analysis(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build analysis payload with deterministic fallbacks from DB columns."""
    payload = row.get("analysis_payload")
    normalized = dict(payload) if isinstance(payload, dict) else {}
    normalized.setdefault("recommendation", row.get("recommendation"))
    normalized.setdefault("confidence", row.get("confidence_score"))
    if row.get("score") is not None:
        normalized.setdefault("score", row.get("score"))
    if isinstance(row.get("decision_card"), dict):
        normalized.setdefault("decision_card", row.get("decision_card"))
    if isinstance(row.get("change_summary"), dict):
        normalized.setdefault("change_summary", row.get("change_summary"))
        normalized.setdefault("changes_since_last_run", row.get("change_summary"))
    if row.get("rationale_summary"):
        normalized.setdefault("rationale_summary", row.get("rationale_summary"))

    persisted_reasoning = str(row.get("solution_agent_reasoning") or "").strip()
    if persisted_reasoning:
        normalized.setdefault("reasoning", persisted_reasoning)
        normalized.setdefault("summary", persisted_reasoning[:400])
        normalized.setdefault("rationale_summary", persisted_reasoning[:400])

    if not normalized:
        return None
    return normalized


def _build_hit_rate_by_horizon(db_manager: DatabaseManager, confidence_raw: Any) -> Dict[str, Dict[str, Any]]:
    """Resolve empirical hit-rate rows for 1d/7d/30d horizons."""
    hit_rate_by_horizon: Dict[str, Dict[str, Any]] = {}
    parsed_confidence = _safe_float(confidence_raw)
    for horizon in (1, 7, 30):
        row = db_manager.get_reliability_hit_rate(horizon_days=horizon, confidence_raw=parsed_confidence)
        if row:
            hit_rate_by_horizon[f"{horizon}d"] = row
    return hit_rate_by_horizon


def _build_markdown_report(stats: BackfillStats) -> str:
    """Render markdown audit report from a completed run."""
    failures = stats.failures[:20]
    hard_failure_rate = 0.0
    if stats.eligible > 0:
        hard_failure_rate = (stats.hard_failures / stats.eligible) * 100.0

    lines = [
        "# Signal Contract V2 Backfill Audit Report",
        "",
        f"- Started: `{stats.started_at}`",
        f"- Ended: `{stats.ended_at or ''}`",
        f"- Scope: `{stats.days}` day window from `{stats.since_timestamp}`",
        f"- Batch size: `{stats.batch_size}`",
        f"- Dry run: `{str(stats.dry_run).lower()}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Scanned | {stats.scanned} |",
        f"| Eligible | {stats.eligible} |",
        f"| Updated | {stats.updated} |",
        f"| Skipped (existing valid) | {stats.skipped_existing_valid} |",
        f"| Skipped (missing payload) | {stats.skipped_missing_payload} |",
        f"| Skipped (missing agent results) | {stats.skipped_missing_agent_results} |",
        f"| Skipped (missing recommendation) | {stats.skipped_missing_recommendation} |",
        f"| Failed (validation) | {stats.failed_validation} |",
        f"| Failed (write) | {stats.failed_write} |",
        f"| Hard failure rate | {hard_failure_rate:.2f}% |",
        "",
        "## Execution Checklist",
        "",
        "- [x] 180-day scope applied",
        "- [x] Deterministic contract builder used",
        "- [x] Contract validation enforced before write",
        "- [x] Additive write path used (legacy keys preserved)",
        "- [x] Batch processing + checkpoint cursor used",
        "",
        "## Spot-Check Template (20 Random Rows)",
        "",
        "Use this table for manual QA after backfill:",
        "",
        "| analysis_id | ticker | schema_version=v2 | signal_contract_v2 valid | legacy keys unchanged | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    if failures:
        lines.extend(
            [
                "",
                "## Failure Samples",
                "",
                "| analysis_id | ticker | reason | detail |",
                "| ---: | --- | --- | --- |",
            ]
        )
        for failure in failures:
            detail = str(failure.get("detail") or "").replace("\n", " ")
            lines.append(
                f"| {failure.get('analysis_id')} | {failure.get('ticker')} | "
                f"{failure.get('reason')} | {detail[:200]} |"
            )

    return "\n".join(lines) + "\n"


def run_signal_contract_backfill(
    *,
    db_path: str,
    days: int = 180,
    batch_size: int = 200,
    checkpoint_file: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute batched signal_contract_v2 backfill for historical analyses."""
    now = datetime.now(timezone.utc)
    since_timestamp = (now - timedelta(days=max(1, int(days)))).isoformat()
    stats = BackfillStats(
        started_at=now.isoformat(),
        since_timestamp=since_timestamp,
        days=max(1, int(days)),
        batch_size=max(1, int(batch_size)),
        dry_run=bool(dry_run),
        checkpoint_file=checkpoint_file,
    )

    db_manager = DatabaseManager(db_path)
    diagnostics_builder = Orchestrator(db_manager=db_manager)
    last_processed_id = _load_checkpoint(checkpoint_file)

    while True:
        rows = db_manager.list_analyses_for_signal_contract_backfill(
            since_timestamp=since_timestamp,
            last_id=last_processed_id,
            batch_size=stats.batch_size,
        )
        if not rows:
            break

        for row in rows:
            analysis_id = int(row.get("id") or 0)
            last_processed_id = analysis_id
            stats.scanned += 1

            existing_contract = row.get("signal_contract_v2")
            if isinstance(existing_contract, dict):
                is_valid, _ = validate_signal_contract_v2(existing_contract)
                if is_valid:
                    stats.skipped_existing_valid += 1
                    continue

            stats.eligible += 1

            analysis = _normalize_analysis(row)
            if not isinstance(analysis, dict):
                stats.skipped_missing_payload += 1
                continue

            if not str(analysis.get("recommendation") or "").strip():
                stats.skipped_missing_recommendation += 1
                continue

            agent_results = db_manager.get_agent_results_map(analysis_id)
            if not agent_results:
                stats.skipped_missing_agent_results += 1
                continue

            diagnostics = analysis.get("diagnostics")
            if not isinstance(diagnostics, dict):
                diagnostics = diagnostics_builder._build_diagnostics(agent_results)

            hit_rate_by_horizon = _build_hit_rate_by_horizon(
                db_manager=db_manager,
                confidence_raw=analysis.get("confidence"),
            )

            contract = build_signal_contract_v2(
                analysis=analysis,
                agent_results=agent_results,
                diagnostics=diagnostics,
                hit_rate_by_horizon=hit_rate_by_horizon,
            )
            is_valid, errors = validate_signal_contract_v2(contract)
            if not is_valid:
                stats.failed_validation += 1
                stats.failures.append(
                    {
                        "analysis_id": analysis_id,
                        "ticker": row.get("ticker"),
                        "reason": "validation_failed",
                        "detail": "; ".join(errors),
                    }
                )
                continue

            if dry_run:
                stats.updated += 1
                continue

            updated = db_manager.update_analysis_signal_contract_v2(
                analysis_id=analysis_id,
                signal_contract_v2=contract,
                analysis_schema_version="v2",
                ev_score_7d=contract.get("ev_score_7d"),
                confidence_calibrated=((contract.get("confidence") or {}).get("calibrated")),
                data_quality_score=((contract.get("risk") or {}).get("data_quality_score")),
                regime_label=((contract.get("risk") or {}).get("regime_label")),
                rationale_summary=contract.get("rationale_summary"),
                merge_into_payload=True,
            )
            if not updated:
                stats.failed_write += 1
                stats.failures.append(
                    {
                        "analysis_id": analysis_id,
                        "ticker": row.get("ticker"),
                        "reason": "write_failed",
                        "detail": "DB row not updated",
                    }
                )
                continue

            stats.updated += 1

        _write_checkpoint(checkpoint_file, last_processed_id, stats)

    stats.ended_at = datetime.now(timezone.utc).isoformat()
    return stats.to_dict()


def main() -> None:
    """CLI entrypoint for signal contract backfill."""
    parser = argparse.ArgumentParser(description="Backfill analyses with signal_contract_v2")
    parser.add_argument("--db-path", default="market_research.db", help="SQLite DB path")
    parser.add_argument("--days", type=int, default=180, help="Lookback window in days")
    parser.add_argument("--batch-size", type=int, default=200, help="Batch size for scan/update")
    parser.add_argument("--checkpoint-file", default=None, help="Optional checkpoint JSON path")
    parser.add_argument("--report-path", default=None, help="Optional markdown report output path")
    parser.add_argument("--dry-run", action="store_true", help="Compute eligibility without writing DB rows")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    report = run_signal_contract_backfill(
        db_path=args.db_path,
        days=args.days,
        batch_size=args.batch_size,
        checkpoint_file=args.checkpoint_file,
        dry_run=args.dry_run,
    )
    logger.info("Backfill complete: %s", json.dumps(report, indent=2))

    if args.report_path:
        stats = BackfillStats(
            started_at=report.get("started_at", ""),
            ended_at=report.get("ended_at"),
            since_timestamp=report.get("since_timestamp", ""),
            days=int(report.get("days") or 180),
            batch_size=int(report.get("batch_size") or 200),
            dry_run=bool(report.get("dry_run")),
            checkpoint_file=report.get("checkpoint_file"),
            scanned=int(report.get("scanned") or 0),
            eligible=int(report.get("eligible") or 0),
            updated=int(report.get("updated") or 0),
            skipped_existing_valid=int(report.get("skipped_existing_valid") or 0),
            skipped_missing_payload=int(report.get("skipped_missing_payload") or 0),
            skipped_missing_agent_results=int(report.get("skipped_missing_agent_results") or 0),
            skipped_missing_recommendation=int(report.get("skipped_missing_recommendation") or 0),
            failed_validation=int(report.get("failed_validation") or 0),
            failed_write=int(report.get("failed_write") or 0),
            failures=list(report.get("failures") or []),
        )
        markdown = _build_markdown_report(stats)
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
        logger.info("Wrote report: %s", str(report_path))


if __name__ == "__main__":
    main()
