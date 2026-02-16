"""Portfolio advisory overlay engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class PortfolioContext:
    """Normalized portfolio limits and current ticker exposure context."""

    max_position_pct: float
    max_sector_pct: float
    risk_budget_pct: float
    current_position_pct: float
    current_sector_exposure_pct: float
    has_position: bool


class PortfolioEngine:
    """Deterministic advisory overlay on top of BUY/HOLD/SELL."""

    def __init__(self, portfolio_snapshot: Dict[str, Any]):
        self.portfolio_snapshot = portfolio_snapshot or {}

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _build_context(self, ticker: str) -> PortfolioContext:
        profile = (self.portfolio_snapshot or {}).get("profile") or {}
        positions = (self.portfolio_snapshot or {}).get("by_ticker") or []

        ticker_position = None
        for position in positions:
            if str(position.get("ticker", "")).upper() == ticker.upper():
                ticker_position = position
                break

        current_position_pct = self._to_float((ticker_position or {}).get("position_pct"), 0.0)
        current_sector_exposure = self._to_float((ticker_position or {}).get("sector_exposure_pct"), 0.0)

        return PortfolioContext(
            max_position_pct=max(0.0, self._to_float(profile.get("max_position_pct"), 0.10)),
            max_sector_pct=max(0.0, self._to_float(profile.get("max_sector_pct"), 0.30)),
            risk_budget_pct=max(0.0, self._to_float(profile.get("risk_budget_pct"), 1.00)),
            current_position_pct=max(0.0, current_position_pct),
            current_sector_exposure_pct=max(0.0, current_sector_exposure),
            has_position=current_position_pct > 0.0001,
        )

    def _projected_exposure(self, action: str, ctx: PortfolioContext) -> Tuple[float, float]:
        default_step = max(0.01, min(0.05, ctx.max_position_pct * 0.5 if ctx.max_position_pct > 0 else 0.03))
        projected_position = ctx.current_position_pct

        if action == "add":
            projected_position = self._clamp(ctx.current_position_pct + default_step, 0.0, 1.0)
        elif action == "trim":
            projected_position = self._clamp(ctx.current_position_pct * 0.7, 0.0, 1.0)
        elif action == "exit":
            projected_position = 0.0
        elif action in {"hold", "hedge"}:
            projected_position = ctx.current_position_pct

        sector_delta = projected_position - ctx.current_position_pct
        projected_sector = self._clamp(ctx.current_sector_exposure_pct + sector_delta, 0.0, 1.0)
        return projected_position, projected_sector

    def evaluate(
        self,
        *,
        ticker: str,
        analysis: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return portfolio action overlay and display summary."""
        ctx = self._build_context(ticker)
        recommendation = str((analysis or {}).get("recommendation", "HOLD")).upper()

        if recommendation == "BUY":
            action = "add"
        elif recommendation == "SELL":
            action = "exit" if ctx.has_position else "hold"
        else:
            action = "hold"

        disagreement = (diagnostics or {}).get("disagreement") or {}
        data_quality = (diagnostics or {}).get("data_quality") or {}
        is_conflicted = bool(disagreement.get("is_conflicted"))
        quality_level = str(data_quality.get("quality_level", "warn")).lower()

        rationale: List[str] = [f"Base mapping from recommendation {recommendation}."]

        if quality_level == "poor" or is_conflicted:
            if ctx.has_position and recommendation in {"BUY", "HOLD"}:
                action = "hedge"
                rationale.append("Signal conflict or poor data quality triggered defensive hedge guidance.")
            elif recommendation == "BUY":
                action = "hold"
                rationale.append("Signal conflict or poor data quality blocked adding exposure.")

        projected_position, projected_sector = self._projected_exposure(action, ctx)

        if projected_position > ctx.max_position_pct:
            if recommendation == "BUY":
                action = "hold"
                rationale.append("Projected position breaches max position limit; add was downgraded to hold.")
            elif ctx.has_position and ctx.current_position_pct > ctx.max_position_pct:
                action = "trim"
                rationale.append("Current position exceeds max position limit; trim recommended.")

        projected_position, projected_sector = self._projected_exposure(action, ctx)

        if projected_sector > ctx.max_sector_pct:
            if recommendation == "BUY":
                action = "hold"
                rationale.append("Projected sector concentration exceeds limit; add was downgraded to hold.")
            elif ctx.has_position and ctx.current_sector_exposure_pct > ctx.max_sector_pct:
                action = "trim"
                rationale.append("Sector concentration already above limit; trim recommended.")

        projected_position, projected_sector = self._projected_exposure(action, ctx)
        risk_budget_utilization = (
            projected_position / ctx.risk_budget_pct
            if ctx.risk_budget_pct > 0
            else 1.0
        )

        def _status_for_limit(projected: float, limit: float) -> str:
            if projected <= limit:
                return "pass"
            if projected <= (limit * 1.15 if limit > 0 else 0.05):
                return "warn"
            return "fail"

        max_position_status = _status_for_limit(projected_position, ctx.max_position_pct)
        max_sector_status = _status_for_limit(projected_sector, ctx.max_sector_pct)
        if quality_level == "poor" or is_conflicted:
            quality_status = "fail"
        elif quality_level == "warn":
            quality_status = "warn"
        else:
            quality_status = "pass"

        constraint_checks = [
            {
                "name": "max_position",
                "status": max_position_status,
                "detail": f"Projected {projected_position:.2%} vs limit {ctx.max_position_pct:.2%}.",
            },
            {
                "name": "max_sector",
                "status": max_sector_status,
                "detail": f"Projected sector {projected_sector:.2%} vs limit {ctx.max_sector_pct:.2%}.",
            },
            {
                "name": "data_quality_gate",
                "status": quality_status,
                "detail": f"Quality={quality_level}; conflicted={is_conflicted}.",
            },
        ]

        fit_score = 85
        if quality_status == "warn":
            fit_score -= 12
        if quality_status == "fail":
            fit_score -= 22
        if max_position_status == "warn":
            fit_score -= 8
        if max_position_status == "fail":
            fit_score -= 16
        if max_sector_status == "warn":
            fit_score -= 8
        if max_sector_status == "fail":
            fit_score -= 16
        if risk_budget_utilization > 1.0:
            fit_score -= 8
        if action in {"hedge", "trim"}:
            fit_score -= 4

        fit_score = int(self._clamp(float(fit_score), 0.0, 100.0))

        if not rationale:
            rationale.append("Portfolio constraints are within limits for the base action.")

        summary = (
            f"Advisory action: {action.upper()} (fit {fit_score}/100). "
            f"Position {projected_position:.1%}, sector {projected_sector:.1%}."
        )

        return {
            "portfolio_action": {
                "action": action,
                "fit_score": fit_score,
                "current_position_pct": round(ctx.current_position_pct, 6),
                "projected_position_pct": round(projected_position, 6),
                "sector_exposure_pct": round(projected_sector, 6),
                "risk_budget_utilization_pct": round(risk_budget_utilization, 6),
                "constraint_checks": constraint_checks,
                "rationale": rationale,
            },
            "portfolio_summary": summary,
        }
