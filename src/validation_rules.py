"""Deterministic validation rule engine.

Pure functions that cross-check synthesis claims against raw agent data.
No classes, no state, no LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def validate(
    *,
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run all validation rules against analysis output.

    Returns a RuleValidationReport dict.
    """
    results: List[Dict[str, Any]] = []

    results.append(_check_direction_consistency(final_analysis, agent_results))
    results.append(_check_regime_consistency(final_analysis, agent_results))
    results.append(_check_options_alignment(final_analysis, agent_results))
    results.append(_check_technical_alignment(final_analysis, agent_results))

    # Check for hard recommendation override (supermajority disagreement)
    override_result = _check_recommendation_override(final_analysis, agent_results)
    results.append(override_result)

    passed = sum(1 for r in results if r["passed"])
    warnings = sum(1 for r in results if not r["passed"] and r["severity"] == "warning")
    contradictions = sum(1 for r in results if not r["passed"] and r["severity"] == "contradiction")
    total_penalty = min(sum(r["confidence_penalty"] for r in results if not r["passed"]), 0.40)

    report = {
        "total_rules_checked": len(results),
        "passed": passed,
        "warnings": warnings,
        "contradictions": contradictions,
        "results": results,
        "total_confidence_penalty": round(total_penalty, 4),
    }

    # Propagate override if triggered
    if override_result.get("override_recommendation"):
        report["override_recommendation"] = override_result["override_recommendation"]

    return report


# ─── Individual rules ────────────────────────────────────────────────────────


def _check_direction_consistency(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if recommendation direction matches majority of agent signals."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    rec_direction = _recommendation_to_direction(recommendation)

    directions = _extract_agent_directions(agent_results)
    if not directions:
        return _pass("direction_consistency", "No agent directions to validate against")

    bullish = sum(1 for d in directions.values() if d == "bullish")
    bearish = sum(1 for d in directions.values() if d == "bearish")
    total = len(directions)

    if rec_direction == "bullish" and bearish >= (total * 0.6):
        return _fail(
            rule_id="direction_consistency",
            severity="contradiction",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence=f"{bearish}/{total} agents signal bearish",
            source_agent="multiple",
            penalty=0.15,
        )
    if rec_direction == "bearish" and bullish >= (total * 0.6):
        return _fail(
            rule_id="direction_consistency",
            severity="contradiction",
            claim=f"Recommendation is {recommendation} (bearish)",
            evidence=f"{bullish}/{total} agents signal bullish",
            source_agent="multiple",
            penalty=0.15,
        )
    return _pass("direction_consistency", "Recommendation aligns with agent majority")


def _check_regime_consistency(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if signal snapshot regime matches macro agent output."""
    snapshot = final_analysis.get("signal_snapshot") or {}
    macro_data = ((agent_results.get("macro") or {}).get("data") or {})

    snapshot_regime = str(snapshot.get("macro_risk_environment") or "").lower()
    macro_cycle = str(macro_data.get("economic_cycle") or "").lower()
    macro_risk = str(macro_data.get("risk_environment") or "").lower()

    if not snapshot_regime or not (macro_cycle or macro_risk):
        return _pass("regime_consistency", "Insufficient regime data to validate")

    if snapshot_regime == "risk_on" and (macro_cycle == "contraction" or macro_risk == "risk_off"):
        return _fail(
            rule_id="regime_consistency",
            severity="warning",
            claim="Signal snapshot says risk_on",
            evidence=f"Macro agent: cycle={macro_cycle}, risk={macro_risk}",
            source_agent="macro",
            penalty=0.05,
        )
    if snapshot_regime == "risk_off" and (macro_cycle == "expansion" and macro_risk == "risk_on"):
        return _fail(
            rule_id="regime_consistency",
            severity="warning",
            claim="Signal snapshot says risk_off",
            evidence=f"Macro agent: cycle={macro_cycle}, risk={macro_risk}",
            source_agent="macro",
            penalty=0.05,
        )
    return _pass("regime_consistency", "Regime labels are consistent")


def _check_options_alignment(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if recommendation aligns with options flow."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    rec_direction = _recommendation_to_direction(recommendation)
    options_data = ((agent_results.get("options") or {}).get("data") or {})

    put_call = _safe_float(options_data.get("put_call_ratio"))
    options_signal = str(options_data.get("overall_signal") or "").lower()

    if put_call is None and not options_signal:
        return _pass("options_alignment", "No options data to validate against")

    if rec_direction == "bullish" and (put_call is not None and put_call > 1.5):
        return _fail(
            rule_id="options_alignment",
            severity="warning",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence=f"Put/call ratio is {put_call:.2f} (>1.5 = heavy put buying)",
            source_agent="options",
            penalty=0.05,
        )
    if rec_direction == "bullish" and options_signal == "bearish":
        return _fail(
            rule_id="options_alignment",
            severity="warning",
            claim=f"Recommendation is {recommendation} (bullish)",
            evidence="Options overall signal is bearish",
            source_agent="options",
            penalty=0.05,
        )
    return _pass("options_alignment", "Options flow aligns with recommendation")


def _check_technical_alignment(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check if BUY recommendation aligns with technical signals."""
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    tech_data = ((agent_results.get("technical") or {}).get("data") or {})

    rsi = _safe_float(tech_data.get("rsi"))
    tech_signal = str((tech_data.get("signals") or {}).get("overall") or "").lower()
    tech_strength = _safe_float((tech_data.get("signals") or {}).get("strength"))

    if recommendation == "BUY":
        if rsi is not None and rsi > 70 and tech_signal in ("sell", "bearish"):
            return _fail(
                rule_id="technical_alignment",
                severity="warning",
                claim="BUY recommendation",
                evidence=f"RSI={rsi:.1f} (overbought), technical signal={tech_signal}",
                source_agent="technical",
                penalty=0.05,
            )
        if tech_strength is not None and tech_strength <= -20:
            return _fail(
                rule_id="technical_alignment",
                severity="warning",
                claim="BUY recommendation",
                evidence=f"Technical strength={tech_strength:.1f} (bearish)",
                source_agent="technical",
                penalty=0.05,
            )
    return _pass("technical_alignment", "Technical signals align with recommendation")


def _check_recommendation_override(
    final_analysis: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Override recommendation to HOLD if supermajority (5+/7) of agents disagree.

    Unlike _check_direction_consistency (which only penalizes confidence at 60%),
    this is a hard override: if 5 or more agents signal the opposite direction,
    the recommendation is forced to HOLD.
    """
    recommendation = str(final_analysis.get("recommendation") or "HOLD").upper()
    rec_direction = _recommendation_to_direction(recommendation)

    if rec_direction == "neutral":
        return _pass("recommendation_override", "Recommendation is already neutral (HOLD)")

    directions = _extract_agent_directions(agent_results)
    if not directions:
        return _pass("recommendation_override", "No agent directions to validate against")

    total = len(directions)
    if total < 5:
        return _pass("recommendation_override", f"Only {total} agents available; override requires 5+ disagreement")

    if rec_direction == "bullish":
        disagreeing = sum(1 for d in directions.values() if d == "bearish")
    else:
        disagreeing = sum(1 for d in directions.values() if d == "bullish")

    if disagreeing >= 5:
        result = _fail(
            rule_id="recommendation_override",
            severity="contradiction",
            claim=f"Recommendation is {recommendation} ({rec_direction})",
            evidence=f"{disagreeing}/{total} agents signal opposite direction — overriding to HOLD",
            source_agent="multiple",
            penalty=0.20,
        )
        result["override_recommendation"] = "HOLD"
        return result

    return _pass("recommendation_override", f"Only {disagreeing}/{total} agents disagree; no override needed")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _recommendation_to_direction(recommendation: str) -> str:
    if recommendation in ("BUY", "STRONG_BUY"):
        return "bullish"
    if recommendation in ("SELL", "STRONG_SELL"):
        return "bearish"
    return "neutral"


def _extract_agent_directions(agent_results: Dict[str, Any]) -> Dict[str, str]:
    """Extract directional signal from each agent's data."""
    directions: Dict[str, str] = {}

    # Market
    market = (agent_results.get("market") or {}).get("data") or {}
    trend = str(market.get("trend") or "").lower()
    if trend in ("bullish", "uptrend", "strong_uptrend"):
        directions["market"] = "bullish"
    elif trend in ("bearish", "downtrend", "strong_downtrend"):
        directions["market"] = "bearish"
    else:
        directions["market"] = "neutral"

    # Technical
    tech = (agent_results.get("technical") or {}).get("data") or {}
    tech_signal = str((tech.get("signals") or {}).get("overall") or "").lower()
    tech_strength = _safe_float((tech.get("signals") or {}).get("strength"))
    if tech_signal in ("buy", "bullish") or (tech_strength is not None and tech_strength >= 20):
        directions["technical"] = "bullish"
    elif tech_signal in ("sell", "bearish") or (tech_strength is not None and tech_strength <= -20):
        directions["technical"] = "bearish"
    else:
        directions["technical"] = "neutral"

    # Fundamentals
    fund = (agent_results.get("fundamentals") or {}).get("data") or {}
    health = _safe_float(fund.get("health_score"))
    if health is not None:
        if health >= 60:
            directions["fundamentals"] = "bullish"
        elif health <= 40:
            directions["fundamentals"] = "bearish"
        else:
            directions["fundamentals"] = "neutral"

    # Macro
    macro = (agent_results.get("macro") or {}).get("data") or {}
    risk_env = str(macro.get("risk_environment") or "").lower()
    if risk_env == "risk_on":
        directions["macro"] = "bullish"
    elif risk_env == "risk_off":
        directions["macro"] = "bearish"
    else:
        directions["macro"] = "neutral"

    # Options
    opts = (agent_results.get("options") or {}).get("data") or {}
    opts_signal = str(opts.get("overall_signal") or "").lower()
    if opts_signal == "bullish":
        directions["options"] = "bullish"
    elif opts_signal == "bearish":
        directions["options"] = "bearish"
    else:
        directions["options"] = "neutral"

    # Sentiment
    sent = (agent_results.get("sentiment") or {}).get("data") or {}
    sent_score = _safe_float(sent.get("overall_sentiment"))
    if sent_score is not None:
        if sent_score > 0.1:
            directions["sentiment"] = "bullish"
        elif sent_score < -0.1:
            directions["sentiment"] = "bearish"
        else:
            directions["sentiment"] = "neutral"

    return directions


def _pass(rule_id: str, evidence: str) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "passed": True,
        "severity": "info",
        "claim": "",
        "evidence": evidence,
        "source_agent": "",
        "confidence_penalty": 0.0,
    }


def _fail(
    *,
    rule_id: str,
    severity: str,
    claim: str,
    evidence: str,
    source_agent: str,
    penalty: float,
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "passed": False,
        "severity": severity,
        "claim": claim,
        "evidence": evidence,
        "source_agent": source_agent,
        "confidence_penalty": penalty,
    }


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
