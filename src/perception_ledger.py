"""Perception Ledger — declarative KPI extraction from agent results.

Extracts normalized KPI snapshots from the structured output of each agent.
Returns plain dicts suitable for PerceptionRepository.insert_snapshots().
"""

from typing import Any, Dict, List, Optional


# ── Guidance helpers ──────────────────────────────────────────────────────────

def _extract_guidance(data: Dict[str, Any], field: str) -> Optional[float]:
    """Extract a numeric guidance value from transcript_metrics.

    field="revenue"  → data["transcript_metrics"]["revenue_guidance"]["low"]
    field="eps"      → data["transcript_metrics"]["eps_guidance"]["low"]
    field="capex"    → data["transcript_metrics"]["capex"]["value"]

    Returns None if any part of the path is missing.
    """
    tm = data.get("transcript_metrics")
    if not tm or not isinstance(tm, dict):
        return None

    if field == "revenue":
        rg = tm.get("revenue_guidance")
        if isinstance(rg, dict):
            return rg.get("low")
    elif field == "eps":
        eg = tm.get("eps_guidance")
        if isinstance(eg, dict):
            return eg.get("low")
    elif field == "capex":
        cx = tm.get("capex")
        if isinstance(cx, dict):
            return cx.get("value")

    return None


# ── KPI extractor registry ────────────────────────────────────────────────────
# Structure:
#   KPI_EXTRACTORS[agent_type][kpi_name] = (category, extractor_fn)
# extractor_fn receives agent data dict and returns a numeric value or None.

KPI_EXTRACTORS: Dict[str, Dict[str, tuple]] = {
    "fundamentals": {
        # Valuation
        "forward_pe":        ("valuation", lambda d: d.get("forward_pe")),
        "price_to_sales":    ("valuation", lambda d: d.get("price_to_sales")),
        "pe_ratio":          ("valuation", lambda d: d.get("pe_ratio")),
        "price_to_book":     ("valuation", lambda d: d.get("price_to_book")),
        "peg_ratio":         ("valuation", lambda d: d.get("peg_ratio")),
        # Margins
        "profit_margins":    ("margins",   lambda d: d.get("profit_margins")),
        "operating_margins": ("margins",   lambda d: d.get("operating_margins")),
        # Efficiency
        "return_on_equity":  ("efficiency", lambda d: d.get("return_on_equity")),
        "return_on_assets":  ("efficiency", lambda d: d.get("return_on_assets")),
        # Leverage
        "debt_to_equity":    ("leverage",  lambda d: d.get("debt_to_equity")),
        # Growth
        "revenue_growth":    ("growth",    lambda d: d.get("revenue_growth")),
        "earnings_growth":   ("growth",    lambda d: d.get("earnings_growth")),
        # Analyst targets
        "analyst_target_median": ("analyst", lambda d: d.get("target_median_price")),
        "analyst_target_high":   ("analyst", lambda d: d.get("target_high_price")),
        "analyst_target_low":    ("analyst", lambda d: d.get("target_low_price")),
        "analyst_count":         ("analyst", lambda d: d.get("number_of_analyst_opinions")),
        # Transcript guidance
        "revenue_guidance": ("guidance", lambda d: _extract_guidance(d, "revenue")),
        "eps_guidance":     ("guidance", lambda d: _extract_guidance(d, "eps")),
        "capex_outlook":    ("guidance", lambda d: _extract_guidance(d, "capex")),
    },
    "technical": {
        "rsi": (
            "technical",
            lambda d: (d.get("indicators", {}).get("rsi") or {}).get("value")
            if isinstance(d.get("indicators", {}).get("rsi"), dict)
            else d.get("indicators", {}).get("rsi"),
        ),
        "macd_signal": (
            "technical",
            lambda d: (d.get("indicators", {}).get("macd") or {}).get("signal_line"),
        ),
        "ma_50": (
            "technical",
            lambda d: d.get("indicators", {}).get("ma_50"),
        ),
        "ma_20": (
            "technical",
            lambda d: d.get("indicators", {}).get("ma_20"),
        ),
        "ma_10": (
            "technical",
            lambda d: d.get("indicators", {}).get("ma_10"),
        ),
    },
    "sentiment": {
        "overall_sentiment": ("sentiment", lambda d: d.get("overall_sentiment")),
    },
    "macro": {
        "fed_funds_rate": (
            "macro",
            lambda d: (d.get("indicators", {}).get("federal_funds_rate") or {}).get("current"),
        ),
        "cpi_yoy": (
            "macro",
            lambda d: (d.get("indicators", {}).get("cpi") or {}).get("current"),
        ),
        "gdp_growth": (
            "macro",
            lambda d: (d.get("indicators", {}).get("real_gdp") or {}).get("current"),
        ),
        "unemployment_rate": (
            "macro",
            lambda d: (d.get("indicators", {}).get("unemployment") or {}).get("current"),
        ),
        "yield_spread": (
            "macro",
            lambda d: (d.get("yield_curve") or {}).get("spread"),
        ),
    },
    "options": {
        "put_call_ratio": ("options", lambda d: d.get("put_call_ratio")),
        "max_pain":       ("options", lambda d: d.get("max_pain")),
    },
}


# ── Public extraction function ────────────────────────────────────────────────

def extract_kpi_snapshots(
    agent_results: Dict[str, Dict[str, Any]],
    confidence: float = 0.8,
) -> List[Dict[str, Any]]:
    """Extract KPI snapshots from a set of agent result dicts.

    Args:
        agent_results: Mapping of agent_type → agent result dict.
                       Each result dict is expected to have "success" (bool)
                       and "data" (dict of agent analysis output).
        confidence:    Confidence score to attach to every snapshot.

    Returns:
        List of snapshot dicts, each containing:
            kpi_name, kpi_category, value, source_agent, source_detail, confidence
    """
    snapshots: List[Dict[str, Any]] = []

    for agent_type, extractors in KPI_EXTRACTORS.items():
        result = agent_results.get(agent_type)
        if result is None:
            continue

        # Skip failed agents
        if not result.get("success", False):
            continue

        data = result.get("data") or {}
        source_detail = data.get("data_source", "unknown")

        for kpi_name, (category, extractor_fn) in extractors.items():
            try:
                value = extractor_fn(data)
            except Exception:
                value = None

            if value is None:
                continue

            snapshots.append({
                "kpi_name":     kpi_name,
                "kpi_category": category,
                "value":        value,
                "source_agent": agent_type,
                "source_detail": source_detail,
                "confidence":   confidence,
            })

    return snapshots
