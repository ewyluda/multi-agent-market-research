"""Formatting utilities for the agent API.

Transforms raw analysis records from DatabaseManager into
token-efficient shapes suitable for LLM consumption.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def format_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten an analysis record into a token-efficient summary (~200 tokens)."""
    analysis = record.get("analysis") or {}
    price_targets = analysis.get("price_targets") or {}
    timestamp = record.get("timestamp", "")

    reasoning = (
        record.get("rationale_summary")
        or analysis.get("rationale_summary")
        or analysis.get("reasoning")
        or record.get("solution_agent_reasoning")
        or ""
    )

    risks = analysis.get("risks") or []
    opportunities = analysis.get("opportunities") or []

    return clean_for_agent({
        "ticker": record.get("ticker"),
        "timestamp": timestamp,
        "data_age_minutes": _data_age_minutes(timestamp),
        "recommendation": record.get("recommendation") or analysis.get("recommendation"),
        "score": _to_int(record.get("score") or analysis.get("score")),
        "confidence": record.get("confidence_score") or analysis.get("confidence"),
        "confidence_calibrated": record.get("confidence_calibrated") or analysis.get("confidence_calibrated"),
        "ev_score_7d": record.get("ev_score_7d") or analysis.get("ev_score_7d"),
        "data_quality": _to_int(record.get("data_quality_score") or analysis.get("data_quality_score")),
        "regime": record.get("regime_label") or analysis.get("regime_label"),
        "entry": price_targets.get("entry"),
        "target": price_targets.get("target"),
        "stop_loss": price_targets.get("stop_loss"),
        "position_size": analysis.get("position_size"),
        "time_horizon": analysis.get("time_horizon"),
        "reasoning_short": truncate_text(reasoning, 100),
        "top_risks": risks[:5],
        "top_opportunities": opportunities[:5],
        "sentiment": record.get("overall_sentiment_score"),
    })


def format_analysis(
    record: Dict[str, Any],
    detail: str = "standard",
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Format an analysis record at the requested detail level."""
    if detail == "summary":
        return format_summary(record)

    if detail == "full":
        return clean_for_agent({
            "ticker": record.get("ticker"),
            "timestamp": record.get("timestamp"),
            "data_age_minutes": _data_age_minutes(record.get("timestamp", "")),
            "analysis": record.get("analysis"),
            "agent_results": record.get("agent_results"),
        })

    # standard detail
    analysis = record.get("analysis") or {}
    agent_results = record.get("agent_results") or {}

    agents = {}
    for agent_type, agent_data in agent_results.items():
        if sections and agent_type not in sections:
            continue
        if not agent_data.get("success"):
            agents[agent_type] = {"success": False, "error": agent_data.get("error")}
            continue
        data = agent_data.get("data") or {}
        agents[agent_type] = _extract_agent_highlights(agent_type, data)

    sc = analysis.get("signal_contract_v2") or {}
    signal_highlights = None
    if sc:
        signal_highlights = {
            "expected_return_7d": (sc.get("expected_return_pct") or {}).get("7d"),
            "downside_risk_7d": (sc.get("downside_risk_pct") or {}).get("7d"),
            "risk_reward_7d": (sc.get("risk") or {}).get("risk_reward_ratio_7d"),
            "conflict_score": (sc.get("risk") or {}).get("conflict_score"),
        }

    summary = format_summary(record)

    return clean_for_agent({
        **summary,
        "signal_contract": signal_highlights,
        "scenarios": analysis.get("scenarios"),
        "agents": agents,
    })


def format_changes(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute the delta between two analysis records."""
    if previous is None:
        return clean_for_agent({
            "ticker": current.get("ticker"),
            "is_first_analysis": True,
            **format_summary(current),
        })

    return clean_for_agent({
        "ticker": current.get("ticker"),
        "is_first_analysis": False,
        "recommendation_changed": current.get("recommendation") != previous.get("recommendation"),
        "current_recommendation": current.get("recommendation"),
        "previous_recommendation": previous.get("recommendation"),
        "score_delta": _safe_sub(current.get("score"), previous.get("score")),
        "confidence_delta": _safe_sub(
            current.get("confidence_score"), previous.get("confidence_score")
        ),
        "sentiment_delta": _safe_sub(
            current.get("overall_sentiment_score"),
            previous.get("overall_sentiment_score"),
        ),
        "ev_score_delta": _safe_sub(
            current.get("ev_score_7d"), previous.get("ev_score_7d")
        ),
        "current_timestamp": current.get("timestamp"),
        "previous_timestamp": previous.get("timestamp"),
    })


def clean_for_agent(data: Any) -> Any:
    """Remove None values, round floats, flatten single-element lists."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            v = clean_for_agent(v)
            if v is None:
                continue
            cleaned[k] = v
        return cleaned
    if isinstance(data, list):
        cleaned = [clean_for_agent(item) for item in data if item is not None]
        if len(cleaned) == 1 and not isinstance(cleaned[0], (dict, list)):
            return cleaned[0]
        return cleaned
    if isinstance(data, float):
        return round(data, 4)
    return data


def agent_error(message: str, suggestion: Optional[str] = None) -> Dict[str, Any]:
    """Build a consistent error response for the agent API."""
    result: Dict[str, Any] = {"error": True, "message": message}
    if suggestion:
        result["suggestion"] = suggestion
    return result


def relative_time(timestamp_str: str) -> str:
    """Convert an ISO timestamp to a relative string if recent, else ISO date."""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - ts

        total_minutes = int(delta.total_seconds() / 60)
        if total_minutes < 1:
            return "just now"
        if total_minutes < 60:
            return f"{total_minutes} min ago"
        hours = total_minutes // 60
        if hours < 24:
            return f"{hours} hours ago"
        return timestamp_str[:10]
    except (ValueError, TypeError):
        return str(timestamp_str)


def truncate_text(text: str, max_words: int) -> str:
    """Truncate text to max_words, appending '...' if truncated."""
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _data_age_minutes(timestamp_str: str) -> Optional[int]:
    if not timestamp_str:
        return None
    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        return int(delta.total_seconds() / 60)
    except (ValueError, TypeError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (ValueError, TypeError):
        return None


def _safe_sub(a: Any, b: Any) -> Optional[float]:
    if a is None or b is None:
        return None
    try:
        return round(float(a) - float(b), 4)
    except (ValueError, TypeError):
        return None


def _extract_agent_highlights(agent_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the most important fields from an agent's output for standard detail."""
    extractors = {
        "fundamentals": lambda d: {
            "health_score": d.get("health_score"),
            "pe_ratio": d.get("financials", {}).get("pe_ratio"),
            "revenue_growth": d.get("growth_metrics", {}).get("revenue_growth_yoy"),
            "summary": d.get("summary"),
        },
        "technical": lambda d: {
            "technical_score": d.get("technical_score"),
            "signal": d.get("signals", {}).get("overall"),
            "strength": d.get("signals", {}).get("strength"),
            "rsi": d.get("indicators", {}).get("rsi", {}).get("value"),
            "summary": d.get("summary"),
        },
        "sentiment": lambda d: {
            "overall_sentiment": d.get("overall_sentiment"),
            "confidence": d.get("confidence"),
            "key_themes": (d.get("key_themes") or [])[:3],
            "summary": d.get("summary"),
        },
        "news": lambda d: {
            "article_count": len(d.get("articles") or []),
            "ai_summary": d.get("ai_summary"),
            "top_headlines": [a.get("title") for a in (d.get("articles") or [])[:3]],
        },
        "market": lambda d: {
            "price": d.get("current_price") or d.get("price"),
            "change_pct": d.get("change_pct") or d.get("change_percent"),
            "volume": d.get("volume"),
            "market_cap": d.get("market_cap"),
            "summary": d.get("summary"),
        },
        "macro": lambda d: {
            "summary": d.get("summary"),
            "fed_funds_rate": d.get("indicators", {}).get("fed_funds_rate", {}).get("value"),
        },
        "options": lambda d: {
            "put_call_ratio": d.get("put_call_ratio"),
            "implied_volatility": d.get("implied_volatility"),
            "summary": d.get("summary"),
        },
        "leadership": lambda d: {
            "summary": d.get("summary"),
        },
        "thesis": lambda d: {
            "bull_headline": d.get("bull_case", {}).get("headline"),
            "bear_headline": d.get("bear_case", {}).get("headline"),
            "conviction_level": d.get("conviction_level"),
        },
        "earnings_review": lambda d: {"summary": d.get("summary")},
        "narrative": lambda d: {"summary": d.get("summary")},
        "risk_diff": lambda d: {"summary": d.get("summary")},
        "tag_extractor": lambda d: {"tags": d.get("tags")},
    }
    extractor = extractors.get(agent_type, lambda d: {"summary": d.get("summary")})
    return extractor(data)
