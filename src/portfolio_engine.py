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
    target_portfolio_beta: float
    max_turnover_pct: float
    default_transaction_cost_bps: float
    current_position_pct: float
    current_sector_exposure_pct: float
    has_position: bool


class PortfolioEngine:
    """Deterministic advisory overlay on top of BUY/HOLD/SELL."""

    @staticmethod
    def portfolio_risk_summary(
        holdings: List[Dict[str, Any]],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute portfolio-level risk metrics across all holdings.

        Args:
            holdings: List of holding dicts (ticker, shares, market_value, sector, beta)
            profile: Portfolio profile dict (max_position_pct, max_sector_pct)

        Returns:
            Dict with portfolio_beta, total_market_value, sector_concentration,
            position_breaches, sector_breaches, diversity_score
        """
        if not holdings:
            return {
                "portfolio_beta": 0.0,
                "total_market_value": 0.0,
                "sector_concentration": {},
                "position_breaches": [],
                "sector_breaches": [],
                "diversity_score": 0,
            }

        total_value = sum(float(h.get("market_value") or 0) for h in holdings)
        if total_value <= 0:
            total_value = 1.0  # Prevent division by zero

        max_position_pct = float(profile.get("max_position_pct") or 0.10)
        max_sector_pct = float(profile.get("max_sector_pct") or 0.30)

        # Weighted-average beta
        weighted_beta = 0.0
        for h in holdings:
            mv = float(h.get("market_value") or 0)
            beta = float(h.get("beta") or 1.0)
            weighted_beta += (mv / total_value) * beta

        # Sector concentration
        sector_values: Dict[str, float] = {}
        for h in holdings:
            sector = str(h.get("sector") or "Unknown")
            mv = float(h.get("market_value") or 0)
            sector_values[sector] = sector_values.get(sector, 0.0) + mv
        sector_concentration = {s: v / total_value for s, v in sector_values.items()}

        # Position breaches
        position_breaches = []
        for h in holdings:
            mv = float(h.get("market_value") or 0)
            pct = mv / total_value
            if pct > max_position_pct:
                position_breaches.append({
                    "ticker": h.get("ticker"),
                    "position_pct": round(pct, 4),
                    "limit_pct": max_position_pct,
                })

        # Sector breaches
        sector_breaches = []
        for sector, pct in sector_concentration.items():
            if pct > max_sector_pct:
                sector_breaches.append({
                    "sector": sector,
                    "concentration_pct": round(pct, 4),
                    "limit_pct": max_sector_pct,
                })

        # Simple diversity score: number of distinct sectors (0-100 scale)
        diversity_score = min(100, len(sector_values) * 15)

        return {
            "portfolio_beta": round(weighted_beta, 4),
            "total_market_value": round(total_value, 2),
            "sector_concentration": {s: round(v, 4) for s, v in sector_concentration.items()},
            "position_breaches": position_breaches,
            "sector_breaches": sector_breaches,
            "diversity_score": diversity_score,
        }

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
            target_portfolio_beta=max(0.0, self._to_float(profile.get("target_portfolio_beta"), 1.00)),
            max_turnover_pct=max(0.001, self._to_float(profile.get("max_turnover_pct"), 0.15)),
            default_transaction_cost_bps=max(0.0, self._to_float(profile.get("default_transaction_cost_bps"), 10.0)),
            current_position_pct=max(0.0, current_position_pct),
            current_sector_exposure_pct=max(0.0, current_sector_exposure),
            has_position=current_position_pct > 0.0001,
        )

    def _extract_signal_context(self, analysis: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        """Extract optimizer inputs from signal contract with robust fallbacks."""
        signal = analysis.get("signal_contract_v2") if isinstance(analysis.get("signal_contract_v2"), dict) else {}
        risk = signal.get("risk") if isinstance(signal.get("risk"), dict) else {}
        confidence = signal.get("confidence") if isinstance(signal.get("confidence"), dict) else {}
        recommendation = str((analysis or {}).get("recommendation", "HOLD")).upper()

        ev_score = self._to_float(signal.get("ev_score_7d"), 0.0)
        confidence_calibrated = self._to_float(confidence.get("calibrated"), None)
        if confidence_calibrated is None:
            confidence_calibrated = self._to_float(analysis.get("confidence_calibrated"), None)
        if confidence_calibrated is None:
            confidence_calibrated = self._to_float(analysis.get("confidence"), 0.5)

        data_quality_score = self._to_float(risk.get("data_quality_score"), None)
        if data_quality_score is None:
            data_quality_score = (
                self._to_float(((diagnostics or {}).get("data_quality") or {}).get("agent_success_rate"), 0.0) * 100.0
            )
        conflict_score = self._to_float(risk.get("conflict_score"), 0.0)
        regime_label = str(
            risk.get("regime_label")
            or analysis.get("regime_label")
            or "transition"
        ).lower()
        if regime_label not in {"risk_on", "risk_off", "transition"}:
            regime_label = "transition"

        return {
            "recommendation": recommendation,
            "ev_score_7d": ev_score,
            "confidence_calibrated": self._clamp(confidence_calibrated, 0.0, 1.0),
            "data_quality_score": self._clamp(data_quality_score, 0.0, 100.0),
            "conflict_score": self._clamp(conflict_score, 0.0, 100.0),
            "regime_label": regime_label,
        }

    def _objective_for_delta(
        self,
        *,
        delta: float,
        alpha_strength: float,
        current_position: float,
        current_sector: float,
        ctx: PortfolioContext,
        data_quality_score: float,
        regime_label: str,
    ) -> Dict[str, Any]:
        """Compute objective score and constraint penalties for a candidate delta."""
        target_position = self._clamp(current_position + delta, 0.0, 1.0)
        target_sector = self._clamp(current_sector + (target_position - current_position), 0.0, 1.0)

        position_excess = max(0.0, target_position - ctx.max_position_pct)
        sector_excess = max(0.0, target_sector - ctx.max_sector_pct)
        turnover_penalty = abs(delta) / max(0.0001, ctx.max_turnover_pct)
        cost_penalty = abs(delta) * (ctx.default_transaction_cost_bps / 10.0)

        quality_gate_penalty = 0.0
        if data_quality_score < 40 and delta > 0:
            quality_gate_penalty += 8.0
        if regime_label == "risk_off" and delta > 0:
            quality_gate_penalty += 8.0

        objective = (
            (alpha_strength * delta * 100.0)
            - (position_excess * 220.0)
            - (sector_excess * 180.0)
            - (turnover_penalty * 4.0)
            - cost_penalty
            - quality_gate_penalty
        )

        return {
            "delta": delta,
            "target_position_pct": target_position,
            "target_sector_pct": target_sector,
            "position_excess": position_excess,
            "sector_excess": sector_excess,
            "turnover_penalty": turnover_penalty,
            "cost_penalty": cost_penalty,
            "quality_gate_penalty": quality_gate_penalty,
            "objective": objective,
        }

    def _optimize_action_v2(
        self,
        *,
        analysis: Dict[str, Any],
        diagnostics: Dict[str, Any],
        ctx: PortfolioContext,
    ) -> Dict[str, Any]:
        """Constrained one-dimensional optimization for target weight delta."""
        signal = self._extract_signal_context(analysis, diagnostics)
        recommendation = signal["recommendation"]
        ev_score = self._to_float(signal.get("ev_score_7d"), 0.0)
        confidence_calibrated = self._to_float(signal.get("confidence_calibrated"), 0.5)
        data_quality_score = self._to_float(signal.get("data_quality_score"), 0.0)
        regime_label = str(signal.get("regime_label") or "transition")

        recommendation_bias = {"BUY": 0.30, "HOLD": 0.00, "SELL": -0.30}.get(recommendation, 0.0)
        alpha_strength = self._clamp(((ev_score / 100.0) + recommendation_bias) * confidence_calibrated, -1.0, 1.0)
        if data_quality_score < 50:
            alpha_strength *= 0.7
        if regime_label == "risk_off":
            alpha_strength = min(alpha_strength, 0.05)

        max_turnover = max(0.005, ctx.max_turnover_pct)
        step = max(0.0025, max_turnover / 40.0)
        candidate_deltas: List[float] = []
        n_steps = int((2 * max_turnover) / step)
        for idx in range(n_steps + 1):
            candidate = (-max_turnover) + (idx * step)
            candidate_deltas.append(round(candidate, 6))

        evaluations = [
            self._objective_for_delta(
                delta=delta,
                alpha_strength=alpha_strength,
                current_position=ctx.current_position_pct,
                current_sector=ctx.current_sector_exposure_pct,
                ctx=ctx,
                data_quality_score=data_quality_score,
                regime_label=regime_label,
            )
            for delta in candidate_deltas
        ]

        best = max(evaluations, key=lambda row: row["objective"])
        delta = float(best["delta"])
        target_position = float(best["target_position_pct"])
        target_sector = float(best["target_sector_pct"])

        if abs(delta) < 0.002:
            recommended_action = "hold"
        elif delta > 0:
            recommended_action = "add"
        elif target_position <= 0.002:
            recommended_action = "exit"
        else:
            recommended_action = "trim"

        fit_score = int(self._clamp(50.0 + best["objective"], 0.0, 100.0))
        constraint_trace = [
            {
                "name": "max_position",
                "limit_pct": ctx.max_position_pct,
                "projected_pct": target_position,
                "status": "pass" if target_position <= ctx.max_position_pct else "fail",
            },
            {
                "name": "max_sector",
                "limit_pct": ctx.max_sector_pct,
                "projected_pct": target_sector,
                "status": "pass" if target_sector <= ctx.max_sector_pct else "fail",
            },
            {
                "name": "max_turnover",
                "limit_pct": ctx.max_turnover_pct,
                "projected_pct": abs(delta),
                "status": "pass" if abs(delta) <= ctx.max_turnover_pct else "fail",
            },
        ]

        return {
            "recommended_action": recommended_action,
            "fit_score": fit_score,
            "objective_score": round(best["objective"], 6),
            "current_position_pct": round(ctx.current_position_pct, 6),
            "target_position_pct": round(target_position, 6),
            "target_delta_pct": round(delta, 6),
            "projected_sector_pct": round(target_sector, 6),
            "signal_inputs": signal,
            "constraint_trace": constraint_trace,
            "search_space": {
                "max_turnover_pct": round(max_turnover, 6),
                "step_pct": round(step, 6),
                "candidate_count": len(candidate_deltas),
            },
        }

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

        portfolio_action_v2 = self._optimize_action_v2(
            analysis=analysis or {},
            diagnostics=diagnostics or {},
            ctx=ctx,
        )
        summary_v2 = (
            f"Optimizer action: {str(portfolio_action_v2.get('recommended_action', 'hold')).upper()} "
            f"(fit {portfolio_action_v2.get('fit_score', 0)}/100)."
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
            "portfolio_action_v2": portfolio_action_v2,
            "portfolio_summary": summary,
            "portfolio_summary_v2": summary_v2,
        }
