"""Thesis health indicator drift detection and aggregate rollup.

Pure functions. No classes, no state, no LLM calls.
Maps thesis card health_indicators to agent result data, computes drift
from baselines, and rolls up to INTACT/WATCHING/DETERIORATING/BROKEN.
"""

from typing import Any, Dict, List, Optional


_SIGNAL_MAP = {
    "price": ("market", "current_price"),
    "current_price": ("market", "current_price"),
    "rsi": ("technical", "rsi"),
    "macd": ("technical", "signals", "strength"),
    "signal_strength": ("technical", "signals", "strength"),
    "revenue_growth": ("fundamentals", "revenue_growth"),
    "margins": ("fundamentals", "margins"),
    "health_score": ("fundamentals", "health_score"),
    "put_call_ratio": ("options", "put_call_ratio"),
    "overall_sentiment": ("sentiment", "overall_sentiment"),
    "risk_environment": ("macro", "risk_environment"),
    "yield_curve": ("macro", "yield_curve_slope"),
    "yield_curve_slope": ("macro", "yield_curve_slope"),
}


def resolve_indicator_value(proxy_signal: str, agent_results: Dict[str, Any]) -> Optional[str]:
    """Resolve a proxy_signal to its current value from agent_results. Returns string or None."""
    path = _SIGNAL_MAP.get(proxy_signal)
    if not path:
        return None
    agent_key = path[0]
    agent_data = (agent_results.get(agent_key) or {}).get("data") or {}
    value = agent_data
    for key in path[1:]:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return str(value) if value is not None else None


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _compute_drift(baseline: str, current: str) -> Dict[str, Any]:
    if _is_numeric(baseline) and _is_numeric(current):
        b = float(baseline)
        c = float(current)
        if abs(b) < 1e-9:
            drift_pct = 0.0 if abs(c) < 1e-9 else 100.0
        else:
            drift_pct = abs(c - b) / abs(b) * 100.0
        if drift_pct <= 10.0:
            status = "stable"
        elif drift_pct <= 25.0:
            status = "drifting"
        else:
            status = "breached"
        return {"drift_pct": round(drift_pct, 2), "status": status}
    else:
        changed = str(baseline).strip().lower() != str(current).strip().lower()
        return {"drift_pct": None, "status": "breached" if changed else "stable"}


def evaluate_thesis_health(
    *,
    thesis_card: Dict[str, Any],
    agent_results: Dict[str, Any],
    previous_health: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate thesis health for a ticker. Returns ThesisHealthReport."""
    indicators = thesis_card.get("health_indicators") or []
    load_bearing = str(thesis_card.get("load_bearing_assumption") or "").lower()
    ticker = thesis_card.get("ticker", "")

    evaluated = []
    baselines_updated = 0

    for ind in indicators:
        proxy = ind.get("proxy_signal", "")
        name = ind.get("name", proxy)
        baseline = ind.get("baseline_value")
        current_str = resolve_indicator_value(proxy, agent_results)
        if current_str is None:
            continue
        if baseline is None or str(baseline).strip() == "":
            baseline = current_str
            baselines_updated += 1
        drift_info = _compute_drift(baseline, current_str)
        evaluated.append({
            "name": name, "proxy_signal": proxy,
            "baseline_value": str(baseline), "current_value": current_str,
            "drift_pct": drift_info["drift_pct"], "status": drift_info["status"],
        })

    statuses = [e["status"] for e in evaluated]
    breached_count = statuses.count("breached")
    drifting_count = statuses.count("drifting")

    load_bearing_breached = False
    if load_bearing:
        for e in evaluated:
            if e["status"] == "breached":
                ind_name = e["name"].lower()
                # Match if the indicator name appears in the load-bearing assumption,
                # or if the load-bearing assumption appears in the indicator name.
                if ind_name in load_bearing or load_bearing in ind_name:
                    load_bearing_breached = True
                    break

    if breached_count >= 2 or load_bearing_breached:
        overall = "BROKEN"
    elif breached_count == 1:
        overall = "DETERIORATING"
    elif drifting_count > 0:
        overall = "WATCHING"
    else:
        overall = "INTACT"

    health_changed = previous_health is not None and overall != previous_health

    return {
        "ticker": ticker, "overall_health": overall,
        "previous_health": previous_health, "health_changed": health_changed,
        "indicators": evaluated, "baselines_updated": baselines_updated,
    }
