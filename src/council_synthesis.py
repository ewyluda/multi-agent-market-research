"""Deterministic council consensus aggregation.

Pure functions. No classes, no state, no LLM calls.
Aggregates council investor results into stance distribution,
disagreements, top scenarios, and thesis health consensus.
"""

from collections import Counter
from typing import Any, Dict, List


_STANCE_PRIORITY = {"BULLISH": 0, "CAUTIOUS": 1, "BEARISH": 2, "PASS": 3}
_CONVICTION_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_consensus(council_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build deterministic consensus from council investor results."""
    if not council_results:
        return {
            "stance_distribution": {"bullish": 0, "cautious": 0, "bearish": 0, "pass": 0},
            "majority_stance": "PASS",
            "conviction_strength": 0.0,
            "thesis_health_consensus": "UNKNOWN",
            "disagreements": [],
            "top_scenarios": [],
        }

    stances = [r.get("stance", "PASS").upper() for r in council_results]
    dist = {"bullish": 0, "cautious": 0, "bearish": 0, "pass": 0}
    for s in stances:
        key = s.lower() if s.lower() in dist else "pass"
        dist[key] += 1

    non_pass = [(s, c) for s, c in dist.items() if s != "pass" and c > 0]
    if non_pass:
        non_pass.sort(key=lambda x: (-x[1], _STANCE_PRIORITY.get(x[0].upper(), 99)))
        majority = non_pass[0][0].upper()
        total_non_pass = sum(c for _, c in non_pass)
        majority_count = non_pass[0][1]
        conviction = round(majority_count / total_non_pass, 4) if total_non_pass > 0 else 0.0
    else:
        majority = "PASS"
        conviction = 0.0

    health_values = [
        r.get("thesis_health", "UNKNOWN").upper()
        for r in council_results
        if r.get("thesis_health", "UNKNOWN").upper() != "UNKNOWN"
    ]
    if health_values:
        health_counter = Counter(health_values)
        health_consensus = health_counter.most_common(1)[0][0]
    else:
        health_consensus = "UNKNOWN"

    disagreements = []
    for r in council_results:
        flag = r.get("disagreement_flag")
        if flag and str(flag).strip():
            disagreements.append({
                "investor": r.get("investor", "unknown"),
                "investor_name": r.get("investor_name", r.get("investor", "unknown")),
                "flag": str(flag).strip(),
            })

    all_scenarios = []
    for r in council_results:
        investor = r.get("investor", "unknown")
        for s in r.get("if_then_scenarios", []):
            scenario = dict(s) if isinstance(s, dict) else {}
            if not scenario.get("condition"):
                continue
            scenario["investor"] = investor
            all_scenarios.append(scenario)

    all_scenarios.sort(key=lambda s: _CONVICTION_ORDER.get(str(s.get("conviction", "low")).lower(), 99))

    seen_conditions = set()
    top_scenarios = []
    for s in all_scenarios:
        condition_key = str(s.get("condition", "")).strip().lower()
        if condition_key in seen_conditions:
            continue
        seen_conditions.add(condition_key)
        top_scenarios.append({
            "investor": s.get("investor", ""),
            "type": s.get("type", ""),
            "condition": s.get("condition", ""),
            "action": s.get("action", ""),
            "conviction": s.get("conviction", "low"),
        })
        if len(top_scenarios) >= 3:
            break

    return {
        "stance_distribution": dist,
        "majority_stance": majority,
        "conviction_strength": conviction,
        "thesis_health_consensus": health_consensus,
        "disagreements": disagreements,
        "top_scenarios": top_scenarios,
    }
