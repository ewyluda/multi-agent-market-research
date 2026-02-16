"""Signal contract v2 builder and validator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _safe_float(value: Any) -> Optional[float]:
    """Best-effort float conversion."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp to inclusive numeric bounds."""
    return max(low, min(high, value))


def _truncate(text: Any, limit: int = 400) -> str:
    """Convert to text and truncate to a safe summary length."""
    if text is None:
        return ""
    normalized = str(text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "…"


def _scenario_expected_return_7d(scenarios: Dict[str, Any]) -> Optional[float]:
    """Compute probability-weighted scenario expected return for the 7d horizon."""
    if not isinstance(scenarios, dict):
        return None

    weighted = 0.0
    weight_sum = 0.0
    for name in ("bull", "base", "bear"):
        block = scenarios.get(name)
        if not isinstance(block, dict):
            continue
        probability = _safe_float(block.get("probability"))
        expected_return = _safe_float(block.get("expected_return_pct"))
        if probability is None or expected_return is None:
            continue
        probability = _clamp(probability, 0.0, 1.0)
        weighted += probability * expected_return
        weight_sum += probability

    if weight_sum <= 0:
        return None
    return weighted / weight_sum


def _bear_downside_component_7d(scenarios: Dict[str, Any]) -> Optional[float]:
    """Compute downside component from bear scenario probability and return."""
    if not isinstance(scenarios, dict):
        return None
    bear = scenarios.get("bear")
    if not isinstance(bear, dict):
        return None
    bear_prob = _safe_float(bear.get("probability"))
    bear_return = _safe_float(bear.get("expected_return_pct"))
    if bear_prob is None or bear_return is None:
        return None
    bear_prob = _clamp(bear_prob, 0.0, 1.0)
    return abs(min(0.0, bear_return)) * bear_prob


def _stop_loss_distance_pct(analysis: Dict[str, Any]) -> Optional[float]:
    """Estimate downside from stop-loss distance vs entry."""
    decision_card = analysis.get("decision_card") if isinstance(analysis.get("decision_card"), dict) else {}
    price_targets = analysis.get("price_targets") if isinstance(analysis.get("price_targets"), dict) else {}

    entry = _safe_float((decision_card.get("entry_zone") or {}).get("reference"))
    if entry is None:
        entry = _safe_float(price_targets.get("entry"))
    stop_loss = _safe_float(decision_card.get("stop_loss"))
    if stop_loss is None:
        stop_loss = _safe_float(price_targets.get("stop_loss"))

    if entry is None or entry <= 0 or stop_loss is None:
        return None
    return max(0.0, ((entry - stop_loss) / entry) * 100.0)


def _fallback_hit_rate(recommendation: str, confidence_raw: Optional[float]) -> float:
    """Fallback hit-rate mapping when reliability bins are unavailable."""
    conf = _clamp(confidence_raw or 0.5, 0.0, 1.0)
    rec = str(recommendation or "HOLD").upper()
    if rec == "BUY":
        return _clamp(0.45 + (0.45 * conf), 0.35, 0.90)
    if rec == "SELL":
        return _clamp(0.45 + (0.45 * conf), 0.35, 0.90)
    return _clamp(0.40 + (0.30 * conf), 0.35, 0.75)


def _derive_regime_label(analysis: Dict[str, Any], diagnostics: Dict[str, Any]) -> str:
    """Map analysis + diagnostics state into risk_on/risk_off/transition."""
    snapshot = analysis.get("signal_snapshot") if isinstance(analysis.get("signal_snapshot"), dict) else {}
    macro_risk = str(snapshot.get("macro_risk_environment") or "").lower()
    quality = str(((diagnostics or {}).get("data_quality") or {}).get("quality_level") or "warn").lower()

    if macro_risk in {"hawkish", "risk_off", "restrictive"} or quality == "poor":
        return "risk_off"
    if macro_risk in {"dovish", "risk_on", "supportive"} and quality == "good":
        return "risk_on"
    return "transition"


def _build_evidence(
    agent_results: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Create concise factor evidence rows for UI and API consumption."""
    disagreement = (diagnostics or {}).get("disagreement") or {}
    directions = disagreement.get("agent_directions") or {}
    data_quality = (diagnostics or {}).get("data_quality") or {}
    freshness = _safe_float(data_quality.get("news_freshness_hours"))

    evidence: List[Dict[str, Any]] = []
    for factor in ("market", "fundamentals", "technical", "sentiment", "macro", "options"):
        result = agent_results.get(factor) or {}
        if not result.get("success"):
            continue
        data = result.get("data") or {}
        direction = str(directions.get(factor, "neutral")).lower()
        if direction not in {"bullish", "neutral", "bearish"}:
            direction = "neutral"

        strength = 0.5
        if factor == "technical":
            technical_strength = _safe_float((data.get("signals") or {}).get("strength"))
            if technical_strength is not None:
                strength = _clamp((abs(technical_strength) / 100.0), 0.0, 1.0)
        elif factor == "fundamentals":
            health_score = _safe_float(data.get("health_score"))
            if health_score is not None:
                strength = _clamp(abs(health_score - 50.0) / 50.0, 0.0, 1.0)
        elif factor == "sentiment":
            sentiment_score = _safe_float(data.get("overall_sentiment"))
            if sentiment_score is not None:
                strength = _clamp(abs(sentiment_score), 0.0, 1.0)
        elif factor == "market":
            trend = str(data.get("trend") or "").lower()
            if any(word in trend for word in ("uptrend", "downtrend", "bull", "bear")):
                strength = 0.7
        elif factor == "options":
            pc_ratio = _safe_float(data.get("put_call_ratio"))
            if pc_ratio is not None:
                strength = _clamp(abs(pc_ratio - 1.0), 0.0, 1.0)

        evidence.append(
            {
                "factor": factor,
                "direction": direction,
                "strength": round(strength, 4),
                "freshness_hours": freshness if factor in {"sentiment", "news"} else None,
                "source": str(data.get("data_source") or data.get("source") or "unknown"),
            }
        )

    return evidence


def _confidence_payload(
    recommendation: str,
    confidence_raw: Optional[float],
    hit_rate_7d: Optional[float],
    reliability_sample_size_7d: Optional[int],
) -> Dict[str, Optional[float]]:
    """Build confidence payload with calibrated confidence and uncertainty."""
    raw = _clamp(confidence_raw or 0.5, 0.0, 1.0)

    sample = int(reliability_sample_size_7d or 0)
    calibrated = None
    uncertainty = 15.0
    if hit_rate_7d is not None and sample >= 30:
        calibrated = _clamp(float(hit_rate_7d), 0.0, 1.0)
        if sample >= 200:
            uncertainty = 5.0
        elif sample >= 100:
            uncertainty = 8.0
        else:
            uncertainty = 12.0
    else:
        # Fallback per product default: calibrated confidence equals raw when data is thin.
        calibrated = raw

    return {
        "raw": round(raw, 6),
        "calibrated": round(calibrated, 6) if calibrated is not None else None,
        "uncertainty_band_pct": round(float(uncertainty), 4),
    }


def build_signal_contract_v2(
    *,
    analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
    diagnostics: Dict[str, Any],
    hit_rate_by_horizon: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build deterministic signal_contract_v2 payload from analysis context."""
    analysis = analysis or {}
    diagnostics = diagnostics or {}
    hit_rate_by_horizon = hit_rate_by_horizon or {}

    recommendation = str(analysis.get("recommendation") or "HOLD").upper()
    scenarios = analysis.get("scenarios") if isinstance(analysis.get("scenarios"), dict) else {}
    expected_return_7d = _scenario_expected_return_7d(scenarios)

    # Rule 2/3: scaled 1d/30d returns.
    expected_return_1d = (expected_return_7d / 7.0) if expected_return_7d is not None else None
    expected_return_30d = None
    if expected_return_7d is not None:
        expected_return_30d = _clamp((expected_return_7d * 30.0 / 7.0), -60.0, 60.0)

    # Rule 4/5: downside risk by horizon.
    bear_downside = _bear_downside_component_7d(scenarios)
    stop_loss_downside = _stop_loss_distance_pct(analysis)
    downside_7d = None
    downside_candidates = [candidate for candidate in (bear_downside, stop_loss_downside) if candidate is not None]
    if downside_candidates:
        downside_7d = max(downside_candidates)
    downside_1d = (downside_7d / 7.0) if downside_7d is not None else None
    downside_30d = (downside_7d * 30.0 / 7.0) if downside_7d is not None else None

    confidence_raw = _safe_float(analysis.get("confidence"))
    hr_7d_row = hit_rate_by_horizon.get("7d") or {}
    hr_1d_row = hit_rate_by_horizon.get("1d") or {}
    hr_30d_row = hit_rate_by_horizon.get("30d") or {}

    hr_7d_sample = int(hr_7d_row.get("sample_size") or 0)
    hr_1d_sample = int(hr_1d_row.get("sample_size") or 0)
    hr_30d_sample = int(hr_30d_row.get("sample_size") or 0)

    hr_7d = _safe_float(hr_7d_row.get("hit_rate")) if hr_7d_sample >= 30 else None
    if hr_7d is None:
        hr_7d = _fallback_hit_rate(recommendation, confidence_raw)
    hr_1d = _safe_float(hr_1d_row.get("hit_rate")) if hr_1d_sample >= 30 else None
    if hr_1d is None:
        hr_1d = hr_7d
    hr_30d = _safe_float(hr_30d_row.get("hit_rate")) if hr_30d_sample >= 30 else None
    if hr_30d is None:
        hr_30d = hr_7d

    # Rule 7: EV score.
    ev_score_7d = None
    if expected_return_7d is not None and downside_7d is not None:
        ev_score_7d = (expected_return_7d * hr_7d) - (downside_7d * (1.0 - hr_7d))

    # Rule 8: risk-reward ratio.
    risk_reward_ratio_7d = None
    if expected_return_7d is not None and downside_7d is not None:
        risk_reward_ratio_7d = expected_return_7d / max(downside_7d, 0.1)

    data_quality = diagnostics.get("data_quality") or {}
    disagreement = diagnostics.get("disagreement") or {}

    # Rule 9: data quality score.
    agent_success_rate = _clamp(_safe_float(data_quality.get("agent_success_rate")) or 0.0, 0.0, 1.0)
    news_freshness_hours = _safe_float(data_quality.get("news_freshness_hours"))
    freshness_score = 0.0
    if news_freshness_hours is not None:
        freshness_score = _clamp(1.0 - (news_freshness_hours / 48.0), 0.0, 1.0)
    fallback_sources = data_quality.get("fallback_source_agents")
    fallback_count = len(fallback_sources) if isinstance(fallback_sources, list) else 0
    total_success = max(1, int(round(agent_success_rate * max(1, len(agent_results)))))
    fallback_share = _clamp(fallback_count / total_success, 0.0, 1.0)
    source_quality_score = 1.0 - fallback_share
    data_quality_score = 100.0 * (
        (0.5 * agent_success_rate) + (0.3 * freshness_score) + (0.2 * source_quality_score)
    )

    # Rule 10: conflict score.
    bullish_count = int(disagreement.get("bullish_count") or 0)
    bearish_count = int(disagreement.get("bearish_count") or 0)
    denom = max(1, bullish_count + bearish_count)
    conflict_score = 100.0 * min(1.0, min(bullish_count, bearish_count) / denom)

    market_data = ((agent_results.get("market") or {}).get("data") or {})
    current_price = _safe_float(market_data.get("current_price"))
    avg_volume = _safe_float(market_data.get("average_volume")) or _safe_float(market_data.get("volume"))
    avg_dollar_volume_20d = None
    if current_price is not None and avg_volume is not None:
        avg_dollar_volume_20d = current_price * avg_volume
    est_spread_bps = None
    vol_3m = _safe_float(market_data.get("volatility_3m"))
    if vol_3m is not None:
        est_spread_bps = _clamp(5.0 + (vol_3m * 0.5), 5.0, 250.0)
    capacity_usd = None
    if avg_dollar_volume_20d is not None:
        capacity_usd = avg_dollar_volume_20d * 0.02

    decision_card = analysis.get("decision_card") if isinstance(analysis.get("decision_card"), dict) else {}
    entry_zone = decision_card.get("entry_zone")
    stop_loss = _safe_float(decision_card.get("stop_loss"))
    targets_raw = decision_card.get("targets") if isinstance(decision_card.get("targets"), list) else []
    targets = [round(v, 4) for v in (_safe_float(item) for item in targets_raw) if v is not None]
    invalidation_conditions = decision_card.get("invalidation_conditions")
    if not isinstance(invalidation_conditions, list):
        invalidation_conditions = []

    time_horizon = str(decision_card.get("time_horizon") or analysis.get("time_horizon") or "MEDIUM_TERM").upper()
    max_holding_days = {"SHORT_TERM": 7, "MEDIUM_TERM": 30, "LONG_TERM": 90}.get(time_horizon, 30)

    rationale_text = (
        analysis.get("rationale_summary")
        or analysis.get("summary")
        or analysis.get("reasoning")
        or ""
    )

    regime_label = _derive_regime_label(analysis, diagnostics)
    confidence_payload = _confidence_payload(
        recommendation=recommendation,
        confidence_raw=confidence_raw,
        hit_rate_7d=hr_7d,
        reliability_sample_size_7d=hr_7d_sample,
    )

    payload = {
        "schema_version": "2.0",
        "instrument_type": "US_EQUITY",
        "recommendation": recommendation,
        "expected_return_pct": {
            "1d": round(expected_return_1d, 6) if expected_return_1d is not None else None,
            "7d": round(expected_return_7d, 6) if expected_return_7d is not None else None,
            "30d": round(expected_return_30d, 6) if expected_return_30d is not None else None,
        },
        "downside_risk_pct": {
            "1d": round(downside_1d, 6) if downside_1d is not None else None,
            "7d": round(downside_7d, 6) if downside_7d is not None else None,
            "30d": round(downside_30d, 6) if downside_30d is not None else None,
        },
        "hit_rate": {
            "1d": round(hr_1d, 6),
            "7d": round(hr_7d, 6),
            "30d": round(hr_30d, 6),
        },
        "ev_score_7d": round(ev_score_7d, 6) if ev_score_7d is not None else None,
        "confidence": confidence_payload,
        "risk": {
            "risk_reward_ratio_7d": round(risk_reward_ratio_7d, 6) if risk_reward_ratio_7d is not None else None,
            "max_drawdown_est_pct_7d": round(downside_7d, 6) if downside_7d is not None else None,
            "data_quality_score": round(data_quality_score, 6),
            "conflict_score": round(conflict_score, 6),
            "regime_label": regime_label,
        },
        "liquidity": {
            "avg_dollar_volume_20d": round(avg_dollar_volume_20d, 4) if avg_dollar_volume_20d is not None else None,
            "est_spread_bps": round(est_spread_bps, 4) if est_spread_bps is not None else None,
            "capacity_usd": round(capacity_usd, 4) if capacity_usd is not None else None,
        },
        "execution_plan": {
            "entry_zone": entry_zone if isinstance(entry_zone, dict) else {"low": None, "high": None, "reference": None},
            "stop_loss": round(stop_loss, 4) if stop_loss is not None else None,
            "targets": targets,
            "invalidation_conditions": [str(item) for item in invalidation_conditions],
            "max_holding_days": int(max_holding_days),
        },
        "rationale_summary": _truncate(rationale_text, 400),
        "evidence": _build_evidence(agent_results, diagnostics),
    }

    return payload


def validate_signal_contract_v2(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate signal contract shape and core value domains."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["payload must be an object"]

    if payload.get("schema_version") != "2.0":
        errors.append("schema_version must be '2.0'")
    if payload.get("instrument_type") != "US_EQUITY":
        errors.append("instrument_type must be 'US_EQUITY'")
    if payload.get("recommendation") not in {"BUY", "HOLD", "SELL"}:
        errors.append("recommendation must be BUY/HOLD/SELL")

    confidence = payload.get("confidence")
    if not isinstance(confidence, dict):
        errors.append("confidence must be an object")
    else:
        for key in ("raw", "calibrated"):
            value = confidence.get(key)
            if value is not None and not (0.0 <= float(value) <= 1.0):
                errors.append(f"confidence.{key} must be in [0,1]")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
    else:
        for idx, row in enumerate(evidence):
            if not isinstance(row, dict):
                errors.append(f"evidence[{idx}] must be an object")
                continue
            if row.get("direction") not in {"bullish", "neutral", "bearish"}:
                errors.append(f"evidence[{idx}].direction invalid")
            strength = _safe_float(row.get("strength"))
            if strength is None or not (0.0 <= strength <= 1.0):
                errors.append(f"evidence[{idx}].strength must be in [0,1]")

    return len(errors) == 0, errors
