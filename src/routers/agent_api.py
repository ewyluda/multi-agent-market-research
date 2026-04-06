"""Agent API — LLM-optimized endpoints for AI agent consumption.

Three layers:
    Layer 1: Analysis tools (processed, token-efficient)
    Layer 2: Action tools (mutating — run analyses, CRUD)
    Layer 3: Raw data tools (direct data provider access)
"""

import re
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.orchestrator import Orchestrator

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


# ---- Pydantic request models ----


class RunAnalysisRequest(BaseModel):
    agents: Optional[str] = None


class WatchlistCreate(BaseModel):
    name: str


class WatchlistRename(BaseModel):
    name: str


class WatchlistTickerAdd(BaseModel):
    ticker: str


class AlertCreate(BaseModel):
    ticker: str
    rule_type: str
    threshold: Optional[float] = None


class PortfolioHoldingCreate(BaseModel):
    ticker: str
    shares: float
    avg_cost: Optional[float] = None
    market_value: Optional[float] = None
    sector: Optional[str] = None
    beta: Optional[float] = None


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


# ---- Layer 2: Static Action Routes (watchlists / alerts / portfolio) ----
# These MUST remain above /{ticker}/* routes to avoid route shadowing.


@router.get("/watchlists")
async def list_watchlists():
    """List all watchlists."""
    db = _get_db()
    watchlists = db.get_watchlists()
    return clean_for_agent({"watchlists": watchlists, "count": len(watchlists)})


@router.post("/watchlists")
async def create_watchlist(body: WatchlistCreate):
    """Create a new watchlist."""
    db = _get_db()
    watchlist = db.create_watchlist(body.name)
    return clean_for_agent(watchlist)


@router.put("/watchlists/{watchlist_id}")
async def rename_watchlist(watchlist_id: int, body: WatchlistRename):
    """Rename an existing watchlist."""
    db = _get_db()
    success = db.rename_watchlist(watchlist_id, body.name)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return clean_for_agent({"success": True, "id": watchlist_id, "name": body.name})


@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: int):
    """Delete a watchlist."""
    db = _get_db()
    success = db.delete_watchlist(watchlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return clean_for_agent({"success": True, "id": watchlist_id})


@router.post("/watchlists/{watchlist_id}/tickers")
async def add_ticker_to_watchlist(watchlist_id: int, body: WatchlistTickerAdd):
    """Add a ticker to a watchlist."""
    ticker = _validate_ticker(body.ticker)
    db = _get_db()
    success = db.add_ticker_to_watchlist(watchlist_id, ticker)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found or ticker already present")
    return clean_for_agent({"success": True, "watchlist_id": watchlist_id, "ticker": ticker})


@router.delete("/watchlists/{watchlist_id}/tickers/{ticker}")
async def remove_ticker_from_watchlist(watchlist_id: int, ticker: str):
    """Remove a ticker from a watchlist."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    success = db.remove_ticker_from_watchlist(watchlist_id, ticker)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist or ticker not found")
    return clean_for_agent({"success": True, "watchlist_id": watchlist_id, "ticker": ticker})


@router.get("/alerts")
async def list_alerts(ticker: Optional[str] = Query(default=None)):
    """List alert rules, optionally filtered by ticker."""
    db = _get_db()
    if ticker:
        ticker = _validate_ticker(ticker)
    alerts = db.get_alert_rules(ticker=ticker)
    return clean_for_agent({"alerts": alerts, "count": len(alerts)})


@router.post("/alerts")
async def create_alert(body: AlertCreate):
    """Create a new alert rule."""
    ticker = _validate_ticker(body.ticker)
    db = _get_db()
    alert = db.create_alert_rule(ticker, body.rule_type, body.threshold)
    return clean_for_agent(alert)


@router.delete("/alerts/{rule_id}")
async def delete_alert(rule_id: int):
    """Delete an alert rule."""
    db = _get_db()
    success = db.delete_alert_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return clean_for_agent({"success": True, "id": rule_id})


@router.get("/portfolio")
async def get_portfolio():
    """Get portfolio snapshot and holdings list."""
    db = _get_db()
    snapshot = db.get_portfolio_snapshot()
    holdings = db.list_portfolio_holdings()
    return clean_for_agent({"snapshot": snapshot, "holdings": holdings, "count": len(holdings)})


@router.post("/portfolio")
async def add_portfolio_holding(body: PortfolioHoldingCreate):
    """Add a holding to the portfolio."""
    ticker = _validate_ticker(body.ticker)
    db = _get_db()
    holding = db.create_portfolio_holding(
        ticker,
        body.shares,
        body.avg_cost,
        body.market_value,
        body.sector,
        body.beta,
    )
    return clean_for_agent(holding)


@router.delete("/portfolio/{holding_id}")
async def delete_portfolio_holding(holding_id: int):
    """Remove a holding from the portfolio."""
    db = _get_db()
    success = db.delete_portfolio_holding(holding_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found")
    return clean_for_agent({"success": True, "id": holding_id})


# ---- Layer 2: Dynamic Ticker Action Routes ----


@router.post("/{ticker}/analyze")
async def run_analysis(ticker: str, body: RunAnalysisRequest = RunAnalysisRequest()):
    """Trigger a full analysis for a ticker. Waits up to 120s for results."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    dp = _get_data_provider()
    requested_agents = [a.strip() for a in body.agents.split(",")] if body.agents else None
    orchestrator = Orchestrator(db_manager=db, data_provider=dp)
    try:
        result = await asyncio.wait_for(
            orchestrator.analyze_ticker(ticker, requested_agents=requested_agents),
            timeout=120,
        )
    except asyncio.TimeoutError:
        return clean_for_agent({"success": False, "ticker": ticker, "error": "Analysis timed out after 120s"})
    except Exception as e:
        logger.error("Analysis error for %s: %s", ticker, e)
        return clean_for_agent({"success": False, "ticker": ticker, "error": str(e)})

    if not result.get("success"):
        return clean_for_agent({"success": False, "ticker": ticker, "error": result.get("error", "Unknown error")})

    analysis = result.get("analysis", {})
    return clean_for_agent({
        "success": True,
        "ticker": ticker,
        "analysis_id": result.get("analysis_id"),
        "recommendation": analysis.get("recommendation"),
        "score": analysis.get("score"),
        "confidence": analysis.get("confidence"),
        "reasoning": analysis.get("reasoning"),
        "risks": analysis.get("risks", []),
        "opportunities": analysis.get("opportunities", []),
        "price_targets": analysis.get("price_targets"),
        "position_size": analysis.get("position_size"),
        "time_horizon": analysis.get("time_horizon"),
        "duration_seconds": result.get("duration_seconds"),
    })


@router.post("/{ticker}/council")
async def run_council(ticker: str):
    """Trigger an investor council analysis for a ticker."""
    ticker = _validate_ticker(ticker)
    db = _get_db()
    try:
        from src.agents.council import run_council_analysis
        result = await asyncio.wait_for(
            run_council_analysis(ticker, db_manager=db),
            timeout=180,
        )
    except asyncio.TimeoutError:
        return clean_for_agent({"success": False, "ticker": ticker, "error": "Council analysis timed out"})
    except Exception as e:
        logger.error("Council error for %s: %s", ticker, e)
        return clean_for_agent({"success": False, "ticker": ticker, "error": str(e)})
    return clean_for_agent(result)
