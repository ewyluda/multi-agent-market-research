"""Deterministic guardrails for LLM output validation.

Pure functions that clamp, normalize, and cross-check LLM-generated values
against known input data. No classes, no state, no LLM calls.

Every public function returns ``(validated_result, warnings)`` where
*warnings* is a list of human-readable strings suitable for inclusion
in the analysis output JSON.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ─── Helpers ────────────────────────────────────────────────────────────────


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (ValueError, TypeError):
        return None


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ─── Price Targets ──────────────────────────────────────────────────────────


def validate_price_targets(
    targets: Dict[str, Any],
    current_price: float,
    analyst_estimates: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and clamp LLM-generated price targets against market reality.

    Rules:
        - stop_loss < entry < target
        - stop_loss >= 0.5 * current_price
        - target <= max(2.0 * current_price, analyst_target_high)

    Returns:
        (validated_targets, warnings)
    """
    warnings: List[str] = []
    validated = dict(targets)

    entry = _safe_float(validated.get("entry"))
    target = _safe_float(validated.get("target"))
    stop_loss = _safe_float(validated.get("stop_loss"))

    if entry is None:
        entry = current_price
    if target is None:
        target = entry * 1.10  # default 10% upside
    if stop_loss is None:
        stop_loss = entry * 0.93  # default 7% downside

    # Fix ordering: entry should be between stop_loss and target
    if entry > target:
        warnings.append(f"Price target entry ({entry:.2f}) > target ({target:.2f}); swapped")
        entry, target = target, entry

    if stop_loss >= entry:
        clamped = round(entry * 0.95, 2)
        warnings.append(f"Stop loss ({stop_loss:.2f}) >= entry ({entry:.2f}); clamped to {clamped:.2f}")
        stop_loss = clamped

    # Floor: stop_loss must be at least 50% of current price
    floor = current_price * 0.50
    if stop_loss < floor:
        warnings.append(f"Stop loss ({stop_loss:.2f}) below 50% of current price ({current_price:.2f}); clamped to {floor:.2f}")
        stop_loss = floor

    # Ceiling: target must be reasonable relative to current price and analyst data
    analyst_high = None
    if analyst_estimates:
        analyst_high = _safe_float(analyst_estimates.get("target_high"))
    ceiling = max(current_price * 2.0, analyst_high or 0)
    if target > ceiling:
        warnings.append(f"Price target ({target:.2f}) exceeds ceiling ({ceiling:.2f}); clamped")
        target = ceiling

    validated["entry"] = round(entry, 2)
    validated["target"] = round(target, 2)
    validated["stop_loss"] = round(stop_loss, 2)

    return validated, warnings


# ─── Sentiment ──────────────────────────────────────────────────────────────


def validate_sentiment(
    result: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and clamp LLM-generated sentiment analysis.

    Rules:
        - overall_sentiment in [-1.0, 1.0]
        - confidence in [0.0, 1.0]
        - factor scores in [-1.0, 1.0]
        - factor weights normalized to sum to 1.0
        - contribution recomputed as score * weight

    Returns:
        (validated_result, warnings)
    """
    warnings: List[str] = []
    validated = dict(result)

    # Clamp overall sentiment
    sentiment = _safe_float(validated.get("overall_sentiment"))
    if sentiment is not None:
        clamped = _clamp(sentiment, -1.0, 1.0)
        if clamped != sentiment:
            warnings.append(f"overall_sentiment ({sentiment:.3f}) outside [-1, 1]; clamped to {clamped:.3f}")
        validated["overall_sentiment"] = clamped

    # Clamp confidence
    confidence = _safe_float(validated.get("confidence"))
    if confidence is not None:
        clamped = _clamp(confidence, 0.0, 1.0)
        if clamped != confidence:
            warnings.append(f"confidence ({confidence:.3f}) outside [0, 1]; clamped to {clamped:.3f}")
        validated["confidence"] = clamped

    # Validate factors
    factors = validated.get("factors")
    if isinstance(factors, dict):
        weight_sum = 0.0
        for name, factor in factors.items():
            if not isinstance(factor, dict):
                continue
            # Clamp score
            score = _safe_float(factor.get("score"))
            if score is not None:
                clamped = _clamp(score, -1.0, 1.0)
                if clamped != score:
                    warnings.append(f"factor '{name}' score ({score:.3f}) outside [-1, 1]; clamped")
                factor["score"] = clamped
            # Accumulate weights
            w = _safe_float(factor.get("weight"))
            if w is not None:
                weight_sum += abs(w)

        # Normalize weights to sum to 1.0
        if weight_sum > 0 and abs(weight_sum - 1.0) > 0.01:
            warnings.append(f"factor weights sum to {weight_sum:.3f}; normalizing to 1.0")
            for name, factor in factors.items():
                if not isinstance(factor, dict):
                    continue
                w = _safe_float(factor.get("weight"))
                if w is not None:
                    factor["weight"] = round(abs(w) / weight_sum, 4)
                    # Recompute contribution
                    s = _safe_float(factor.get("score"))
                    if s is not None:
                        factor["contribution"] = round(s * factor["weight"], 4)

    return validated, warnings


# ─── Scenarios ──────────────────────────────────────────────────────────────


def validate_scenarios(
    scenarios: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and clamp LLM-generated scenario probabilities and returns.

    Rules:
        - Probability sum should be in [0.95, 1.05] (warn if outside)
        - expected_return_pct in [-30, +30] for 7d horizon
        - bull.return >= base.return >= bear.return (monotonicity)

    Returns:
        (validated_scenarios, warnings)
    """
    warnings: List[str] = []
    validated = dict(scenarios)

    # Check probability sum before normalization
    prob_sum = 0.0
    for name in ("bull", "base", "bear"):
        block = validated.get(name)
        if isinstance(block, dict):
            p = _safe_float(block.get("probability"))
            if p is not None:
                prob_sum += p

    if prob_sum > 0 and not (0.95 <= prob_sum <= 1.05):
        warnings.append(f"scenario probabilities sum to {prob_sum:.3f} (expected ~1.0)")

    # Clamp returns and collect for monotonicity check
    returns = {}
    for name in ("bull", "base", "bear"):
        block = validated.get(name)
        if not isinstance(block, dict):
            continue
        ret = _safe_float(block.get("expected_return_pct"))
        if ret is not None:
            clamped = _clamp(ret, -30.0, 30.0)
            if clamped != ret:
                warnings.append(f"scenario '{name}' return ({ret:.1f}%) clamped to [{-30}, {30}]")
            block["expected_return_pct"] = round(clamped, 2)
            returns[name] = clamped

    # Enforce monotonicity: bull >= base >= bear
    if len(returns) == 3:
        bull_r = returns["bull"]
        base_r = returns["base"]
        bear_r = returns["bear"]

        if not (bull_r >= base_r >= bear_r):
            sorted_returns = sorted([bull_r, base_r, bear_r], reverse=True)
            warnings.append(
                f"scenario returns not monotonic (bull={bull_r:.1f}%, base={base_r:.1f}%, bear={bear_r:.1f}%); "
                f"reordered to bull={sorted_returns[0]:.1f}%, base={sorted_returns[1]:.1f}%, bear={sorted_returns[2]:.1f}%"
            )
            validated["bull"]["expected_return_pct"] = sorted_returns[0]
            validated["base"]["expected_return_pct"] = sorted_returns[1]
            validated["bear"]["expected_return_pct"] = sorted_returns[2]

    return validated, warnings


# ─── Equity Research Cross-Validation ───────────────────────────────────────


def validate_equity_research(
    report: Dict[str, Any],
    input_metrics: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Cross-check LLM equity research claims against known input metrics.

    Scans report text fields for numeric claims (P/E, revenue, etc.) and
    compares against actual input data. Warns on >20% deviation.

    Does NOT modify the report — warnings only.

    Returns:
        (report, warnings)
    """
    warnings: List[str] = []

    if not report or not input_metrics:
        return report, warnings

    # Collect all text from report for scanning
    text_fields = [
        report.get("executive_summary", ""),
        report.get("overall_assessment", ""),
    ]
    # Nested fields
    fhc = report.get("financial_health_check") or {}
    text_fields.append(fhc.get("fcf_analysis", ""))
    text_fields.append(fhc.get("valuation_analysis", ""))

    all_text = " ".join(str(t) for t in text_fields if t).lower()

    if not all_text:
        return report, warnings

    # Cross-check P/E ratio
    _cross_check_metric(
        all_text,
        pattern=r'p/?e\s*(?:ratio)?\s*(?:of|at|is|around|near|approximately)?\s*~?(\d+(?:\.\d+)?)',
        input_value=_safe_float(input_metrics.get("pe_ratio")),
        metric_name="P/E ratio",
        warnings=warnings,
    )

    # Cross-check profit margin (as percentage)
    _cross_check_metric(
        all_text,
        pattern=r'(?:profit|net)\s*margin\s*(?:of|at|is|around)?\s*~?(\d+(?:\.\d+)?)\s*%',
        input_value=_pct(_safe_float(input_metrics.get("profit_margins"))),
        metric_name="profit margin",
        warnings=warnings,
    )

    # Cross-check ROE (as percentage)
    _cross_check_metric(
        all_text,
        pattern=r'(?:roe|return on equity)\s*(?:of|at|is|around)?\s*~?(\d+(?:\.\d+)?)\s*%',
        input_value=_pct(_safe_float(input_metrics.get("return_on_equity"))),
        metric_name="ROE",
        warnings=warnings,
    )

    return report, warnings


def _pct(val: Optional[float]) -> Optional[float]:
    """Convert a ratio (0.27) to a percentage (27.0) if <1, else pass through."""
    if val is None:
        return None
    return val * 100 if abs(val) < 1 else val


def _cross_check_metric(
    text: str,
    pattern: str,
    input_value: Optional[float],
    metric_name: str,
    warnings: List[str],
    tolerance: float = 0.20,
) -> None:
    """Check if a metric claimed in text deviates from the known input value."""
    if input_value is None or input_value == 0:
        return

    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return

    claimed = _safe_float(match.group(1))
    if claimed is None:
        return

    deviation = abs(claimed - input_value) / abs(input_value)
    if deviation > tolerance:
        warnings.append(
            f"LLM claims {metric_name} ≈ {claimed:.1f} but input data shows {input_value:.1f} "
            f"({deviation:.0%} deviation)"
        )


# ─── Thesis Output ─────────────────────────────────────────────────────────


_GENERIC_CATALYSTS = {
    "time will tell", "future earnings", "remains to be seen",
    "only time will tell", "we will see", "market will decide",
    "further developments", "more data needed",
}


def validate_thesis_output(
    thesis: Dict[str, Any],
    extracted_facts: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate thesis agent output against extracted facts and agent data.

    Three checks:
        1. Evidence grounding — flag evidence not traceable to extracted facts.
        2. Catalyst specificity — flag generic resolution catalysts.
        3. Cross-reference — flag claims that contradict agent data.

    Also overrides data_completeness with deterministic value.

    Returns:
        (validated_thesis, warnings)
    """
    warnings: List[str] = []
    validated = dict(thesis)

    # Build a searchable text corpus from extracted facts
    fact_corpus = _build_fact_corpus(extracted_facts)

    # 1. Evidence grounding check
    for i, tp in enumerate(validated.get("tension_points", [])):
        for evidence_item in tp.get("evidence", []):
            if not _evidence_is_grounded(evidence_item, fact_corpus):
                warnings.append(
                    f"Tension '{tp.get('topic', i)}': ungrounded evidence — "
                    f"'{evidence_item[:80]}' not found in extracted facts"
                )

    # 2. Catalyst specificity
    for i, tp in enumerate(validated.get("tension_points", [])):
        catalyst = (tp.get("resolution_catalyst") or "").strip().lower()
        catalyst_stripped = catalyst.rstrip(".")
        if catalyst_stripped in _GENERIC_CATALYSTS or len(catalyst) < 10:
            warnings.append(
                f"Tension '{tp.get('topic', i)}': generic catalyst — "
                f"'{tp.get('resolution_catalyst', '')}'"
            )

    # 3. Cross-reference against agent data
    _cross_reference_claims(validated, agent_results, warnings)

    # Override data_completeness deterministically
    completeness_weights = {
        "fundamentals": 0.30, "news": 0.15, "earnings": 0.20,
        "leadership": 0.10, "market": 0.10, "technical": 0.05,
        "macro": 0.05, "options": 0.05,
    }
    deterministic_completeness = 0.0
    for agent_name, weight in completeness_weights.items():
        result = agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success") and result.get("data"):
            deterministic_completeness += weight
    validated["data_completeness"] = round(deterministic_completeness, 2)

    return validated, warnings


def _build_fact_corpus(extracted_facts: Dict[str, Any]) -> str:
    """Flatten extracted facts into a single searchable string."""
    parts = []
    for key, value in extracted_facts.items():
        if isinstance(value, str):
            parts.append(value.lower())
        elif isinstance(value, list):
            for item in value:
                parts.append(str(item).lower())
    return " ".join(parts)


def _evidence_is_grounded(evidence: str, fact_corpus: str) -> bool:
    """Check if an evidence string can be traced to the fact corpus.

    Uses keyword overlap: extracts significant words (3+ chars) from the
    evidence and checks if at least 40% appear in the corpus.
    """
    words = re.findall(r"[a-z0-9]+", evidence.lower())
    significant = [w for w in words if len(w) >= 3]
    if not significant:
        return True  # Can't check empty evidence
    matches = sum(1 for w in significant if w in fact_corpus)
    return (matches / len(significant)) >= 0.40


def _cross_reference_claims(
    thesis: Dict[str, Any],
    agent_results: Dict[str, Any],
    warnings: List[str],
) -> None:
    """Check thesis claims against agent data for contradictions."""
    fund_result = agent_results.get("fundamentals", {})
    fund_data = fund_result.get("data") if isinstance(fund_result, dict) else None
    if not fund_data:
        return

    rev_growth = fund_data.get("revenue_growth")
    if rev_growth is not None:
        growth_positive = rev_growth > 0
        # Check bull and bear thesis text for contradictory claims
        bull_thesis = (thesis.get("bull_case") or {}).get("thesis", "").lower()
        bear_thesis = (thesis.get("bear_case") or {}).get("thesis", "").lower()

        decline_phrases = ["revenue is declining", "revenue declining", "falling revenue", "revenue shrink"]
        growth_phrases = ["revenue is growing rapidly", "accelerating revenue", "surging revenue"]

        if growth_positive:
            for phrase in decline_phrases:
                if phrase in bull_thesis or phrase in bear_thesis:
                    warnings.append(
                        f"Contradiction: thesis claims '{phrase}' but fundamentals show "
                        f"revenue growth of {rev_growth * 100:.1f}%"
                    )
        else:
            for phrase in growth_phrases:
                if phrase in bull_thesis or phrase in bear_thesis:
                    warnings.append(
                        f"Contradiction: thesis claims '{phrase}' but fundamentals show "
                        f"revenue decline of {rev_growth * 100:.1f}%"
                    )


# ─── Earnings Review Output ────────────────────────────────────────────────


def validate_earnings_review_output(
    review: Dict[str, Any],
    agent_results: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate earnings review agent output.

    Checks:
        1. Beat/miss sanity — verdict matches surprise_pct direction.
        2. KPI value validation — flag unreasonable values.
        3. Guidance/tone consistency — flag raised guidance with defensive tone.
        4. Data completeness override — deterministic recalculation.

    Returns:
        (validated_review, warnings)
    """
    warnings: List[str] = []
    validated = dict(review)

    # 1. Beat/miss sanity
    for bm in validated.get("beat_miss", []):
        surprise = bm.get("surprise_pct")
        verdict = bm.get("verdict", "")
        if surprise is not None:
            expected_verdict = "beat" if surprise > 1.0 else "miss" if surprise < -1.0 else "inline"
            if verdict != expected_verdict:
                warnings.append(
                    f"Beat/miss verdict mismatch for {bm.get('metric', '?')}: "
                    f"verdict='{verdict}' but surprise={surprise:.1f}% implies '{expected_verdict}'"
                )

    # 2. KPI value validation
    for kpi in validated.get("kpi_table", []):
        value_str = (kpi.get("value") or "").strip()
        metric_lower = kpi.get("metric", "").lower()
        # Check percentage values > 100% for margin-type metrics
        if "margin" in metric_lower or "retention" in metric_lower:
            pct_match = re.search(r"([\d.]+)\s*%", value_str)
            if pct_match:
                pct_val = float(pct_match.group(1))
                # Net Revenue Retention can exceed 100%, margins generally shouldn't exceed ~80%
                if "retention" not in metric_lower and pct_val > 100:
                    warnings.append(
                        f"Unreasonable KPI value: {kpi['metric']} = {value_str} (margin > 100%)"
                    )

    # 3. Guidance/tone consistency
    guidance_deltas = validated.get("guidance_deltas", [])
    has_raised = any(g.get("direction") == "raised" for g in guidance_deltas)
    earnings_result = agent_results.get("earnings", {})
    earnings_data = earnings_result.get("data") if isinstance(earnings_result, dict) else None
    if earnings_data and has_raised:
        tone = earnings_data.get("tone", "")
        if tone in ("defensive", "evasive"):
            warnings.append(
                f"Guidance/tone contradiction: guidance raised but EarningsAgent tone is '{tone}'"
            )

    # 4. Data completeness override
    completeness_weights = {"earnings": 0.50, "fundamentals": 0.30, "market": 0.20}
    deterministic_completeness = 0.0
    for agent_name, weight in completeness_weights.items():
        result = agent_results.get(agent_name, {})
        if isinstance(result, dict) and result.get("success") and result.get("data"):
            if agent_name == "earnings":
                data = result.get("data", {})
                highlights = data.get("highlights", [])
                data_source = data.get("data_source", "")
                if len(highlights) > 0 and data_source != "none":
                    deterministic_completeness += weight
                else:
                    deterministic_completeness += 0.15
            else:
                deterministic_completeness += weight
    validated["data_completeness"] = round(deterministic_completeness, 2)

    return validated, warnings
