"""Agent API — LLM-optimized endpoints for AI agent consumption.

Three layers:
    Layer 1: Analysis tools (processed, token-efficient)
    Layer 2: Action tools (mutating — run analyses, CRUD)
    Layer 3: Raw data tools (direct data provider access)
"""

import re
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .agent_formatters import (
    format_summary,
    format_analysis,
    format_changes,
    clean_for_agent,
    agent_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _get_db():
    import src.api as api_module
    return api_module.db_manager


def _get_data_provider():
    import src.api as api_module
    return api_module.data_provider


def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol. Raises HTTPException on invalid."""
    ticker = ticker.upper()
    if not re.match(r"^[A-Z]{1,5}$", ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    return ticker


# ---- Static routes first (must precede /{ticker}/* to avoid route shadowing) ----


@router.get("/compare")
async def compare_tickers(
    tickers: str = Query(description="Comma-separated tickers (max 5)"),
):
    """Side-by-side comparison of multiple tickers."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers")
    if len(ticker_list) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 tickers for comparison")

    db = _get_db()
    results = []
    for t in ticker_list:
        if not re.match(r"^[A-Z]{1,5}$", t):
            results.append({"ticker": t, "error": "Invalid ticker format"})
            continue
        latest = db.get_latest_analysis(t)
        if not latest:
            results.append({"ticker": t, "error": "No analysis found"})
            continue
        record = db.get_analysis_with_agents(latest["id"])
        if record:
            results.append(format_summary(record))
        else:
            results.append({"ticker": t, "error": "Analysis data missing"})

    return {"tickers": results, "count": len(results)}


# ---- Layer 1: Analysis Endpoints ----


@router.get("/{ticker}/summary")
async def get_ticker_summary(ticker: str):
    """Token-efficient summary of the latest analysis (~200 tokens)."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    latest = db.get_latest_analysis(ticker)
    if not latest:
        raise HTTPException(status_code=404, detail=agent_error(
            f"No analysis found for {ticker}. Run an analysis first.",
            suggestion="run_analysis",
        ))
    record = db.get_analysis_with_agents(latest["id"])
    if not record:
        raise HTTPException(status_code=404, detail=agent_error(
            f"Analysis data missing for {ticker}.",
            suggestion="run_analysis",
        ))
    return format_summary(record)


@router.get("/{ticker}/analysis")
async def get_ticker_analysis(
    ticker: str,
    detail: str = Query(default="standard", pattern="^(summary|standard|full)$"),
    sections: Optional[str] = Query(
        default=None,
        description="Comma-separated agent types to include",
    ),
):
    """Filtered analysis with configurable detail level and section filtering."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    latest = db.get_latest_analysis(ticker)
    if not latest:
        raise HTTPException(status_code=404, detail=agent_error(
            f"No analysis found for {ticker}.",
            suggestion="run_analysis",
        ))
    record = db.get_analysis_with_agents(latest["id"])
    if not record:
        raise HTTPException(status_code=404, detail=agent_error(
            f"Analysis data missing for {ticker}.",
            suggestion="run_analysis",
        ))
    section_list = [s.strip() for s in sections.split(",")] if sections else None
    return format_analysis(record, detail=detail, sections=section_list)


@router.get("/{ticker}/changes")
async def get_ticker_changes(ticker: str):
    """Delta between the two most recent analyses."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    history = db.get_analysis_history(ticker, limit=2)
    if not history:
        raise HTTPException(status_code=404, detail=agent_error(
            f"No analysis history for {ticker}.",
            suggestion="run_analysis",
        ))
    current = history[0]
    previous = history[1] if len(history) > 1 else None
    return format_changes(current, previous)


@router.get("/{ticker}/inflections")
async def get_ticker_inflections(
    ticker: str,
    limit: int = Query(default=20, le=100),
):
    """Recent inflection events for a ticker."""
    ticker = _validate_ticker(ticker)
    try:
        from src.repositories.perception_repo import PerceptionRepository
        db = _get_db()
        repo = PerceptionRepository(db)
        events = repo.get_inflection_history(ticker, limit=limit)
        return clean_for_agent({"ticker": ticker, "inflections": events, "count": len(events)})
    except Exception as e:
        logger.warning("Inflection fetch failed for %s: %s", ticker, e)
        return clean_for_agent({"ticker": ticker, "inflections": [], "count": 0})


@router.get("/{ticker}/council")
async def get_council_results(ticker: str):
    """Get the latest council investor analysis results."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    results = db.get_council_results(ticker)
    if not results:
        raise HTTPException(status_code=404, detail=agent_error(
            f"No council results for {ticker}.",
            suggestion="run_council",
        ))
    synthesis = db.get_latest_council_synthesis(ticker)
    return clean_for_agent({
        "ticker": ticker,
        "council_results": results,
        "synthesis": synthesis,
    })
