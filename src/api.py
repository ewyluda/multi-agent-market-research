"""FastAPI application for multi-agent market research."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import json
import logging
import io
import csv
import re
from datetime import datetime, timezone
import asyncio

from .models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisHistoryResponse,
    BatchAnalysisRequest,
    HealthCheckResponse,
    WatchlistCreate,
    WatchlistTickerAdd,
    WatchlistRename,
    ScheduleCreate,
    ScheduleUpdate,
    PortfolioProfileUpdate,
    PortfolioHoldingCreate,
    PortfolioHoldingUpdate,
    AlertRuleCreate,
    AlertRuleUpdate,
)
from .orchestrator import Orchestrator
from .config import Config
from .database import DatabaseManager
from .av_rate_limiter import AVRateLimiter
from .av_cache import AVCache
from .rollout_metrics import compute_phase7_rollout_status
from .portfolio_engine import PortfolioEngine

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    """Startup/shutdown lifecycle for the FastAPI application."""
    # Startup: start the scheduler if enabled
    if Config.SCHEDULER_ENABLED:
        from .scheduler import AnalysisScheduler
        scheduler = AnalysisScheduler(
            db_manager=db_manager,
            rate_limiter=av_rate_limiter,
            av_cache=av_cache,
        )
        app.state.scheduler = scheduler
        await scheduler.start()
    yield
    # Shutdown: stop the scheduler if running
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Market Research API",
    description="AI-powered stock market analysis using specialized agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db_manager = DatabaseManager(Config.DATABASE_PATH)

# Initialize shared AV infrastructure (persists across requests)
av_rate_limiter = AVRateLimiter(
    requests_per_minute=Config.AV_RATE_LIMIT_PER_MINUTE,
    requests_per_day=Config.AV_RATE_LIMIT_PER_DAY,
)
av_cache = AVCache()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Market Research API",
        "version": "0.2.0",
        "endpoints": {
            "analyze": "POST /api/analyze/{ticker}",
            "stream": "GET /api/analyze/{ticker}/stream",
            "latest": "GET /api/analysis/{ticker}/latest",
            "history": "GET /api/analysis/{ticker}/history",
            "history_detailed": "GET /api/analysis/{ticker}/history/detailed",
            "tickers": "GET /api/analysis/tickers",
            "export_csv": "GET /api/analysis/{ticker}/export/csv",
            "export_pdf": "GET /api/analysis/{ticker}/export/pdf",
            "watchlists": "GET /api/watchlists",
            "watchlist_analyze": "POST /api/watchlists/{id}/analyze",
            "watchlist_opportunities": "GET /api/watchlists/{id}/opportunities",
            "schedules": "POST/GET /api/schedules",
            "schedule_runs": "GET /api/schedules/{id}/runs",
            "portfolio": "GET /api/portfolio",
            "macro_events": "GET /api/macro-events",
            "calibration_summary": "GET /api/calibration/summary",
            "calibration_reliability": "GET /api/calibration/reliability",
            "rollout_phase7_status": "GET /api/rollout/phase7/status",
            "alerts": "POST/GET /api/alerts",
            "alert_notifications": "GET /api/alerts/notifications",
            "health": "GET /health"
        }
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    config_valid = Config.validate_config()

    # Test database connection
    db_connected = False
    try:
        db_manager.get_latest_analysis("TEST")
        db_connected = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    return HealthCheckResponse(
        status="healthy" if (config_valid and db_connected) else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database_connected=db_connected,
        config_valid=config_valid
    )


@app.post("/api/analyze/batch")
async def batch_analyze_tickers(body: BatchAnalysisRequest):
    """
    Batch-analyze a list of tickers via SSE stream.

    Accepts a JSON body with tickers list and optional agents string.
    Returns SSE events: 'result' per ticker, 'error' on failure, 'done' at end.
    """
    tickers = [t.upper() for t in body.tickers]

    if not tickers:
        raise HTTPException(status_code=400, detail="No tickers provided")
    if len(tickers) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 tickers per batch")

    # Validate ticker formats
    for t in tickers:
        if not re.match(r"^[A-Z]{1,5}$", t):
            raise HTTPException(status_code=400, detail=f"Invalid ticker format: {t}")

    # Parse agents
    requested_agents = None
    if body.agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options", "leadership"}
        requested_agents = [a.strip().lower() for a in body.agents.split(",") if a.strip()]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}",
            )

    async def batch_generator():
        concurrency = 4
        semaphore = asyncio.Semaphore(concurrency)

        async def _analyze_one(ticker: str) -> Dict[str, Any]:
            async with semaphore:
                orchestrator = Orchestrator(
                    db_manager=db_manager,
                    rate_limiter=av_rate_limiter,
                    av_cache=av_cache,
                )
                result = await orchestrator.analyze_ticker(ticker, requested_agents=requested_agents)
                return {
                    "ticker": ticker,
                    "success": result.get("success", False),
                    "analysis_id": result.get("analysis_id"),
                    "recommendation": (result.get("analysis") or {}).get("recommendation"),
                    "score": (result.get("analysis") or {}).get("score"),
                    "confidence": (result.get("analysis") or {}).get("confidence"),
                    "ev_score_7d": (result.get("analysis") or {}).get("ev_score_7d"),
                    "duration_seconds": result.get("duration_seconds", 0),
                    "error": result.get("error"),
                }

        tasks = [asyncio.create_task(_analyze_one(t)) for t in tickers]
        completed = 0
        for task in asyncio.as_completed(tasks):
            completed += 1
            try:
                payload = await task
            except Exception as e:
                logger.error("Batch analysis task failed: %s", e)
                payload = {"success": False, "error": str(e), "ticker": "UNKNOWN"}

            event_type = "result" if payload.get("success") else "error"
            yield f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"

        yield f"event: done\ndata: {json.dumps({'message': 'Batch complete', 'ticker_count': len(tickers), 'completed': completed}, default=str)}\n\n"

    return StreamingResponse(
        batch_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze_ticker(
    ticker: str,
    agents: Optional[str] = Query(
        default=None,
        description="Comma-separated list of agents to run: news,sentiment,fundamentals,market,technical. Default: all.",
    ),
):
    """
    Trigger analysis for a stock ticker.

    Args:
        ticker: Stock ticker symbol (e.g., NVDA, AAPL)
        agents: Optional comma-separated agent names to run

    Returns:
        Complete analysis result
    """
    ticker = ticker.upper()

    # Validate ticker format

    if not re.match(r'^[A-Z]{1,5}$', ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    # Parse and validate agent list
    requested_agents = None
    if agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options", "leadership"}
        requested_agents = [a.strip().lower() for a in agents.split(",")]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(valid_agents))}"
            )

    logger.info(f"Starting analysis for {ticker}")

    # Create orchestrator (no progress streaming for REST endpoint; use GET /stream for SSE)
    orchestrator = Orchestrator(
        db_manager=db_manager,
        progress_callback=None,
        rate_limiter=av_rate_limiter,
        av_cache=av_cache,
    )

    try:
        # Run analysis
        result = await orchestrator.analyze_ticker(ticker, requested_agents=requested_agents)

        if result.get("success"):
            return AnalysisResponse(
                success=True,
                ticker=ticker,
                analysis_id=result.get("analysis_id"),
                analysis_schema_version=((result.get("analysis") or {}).get("analysis_schema_version")),
                analysis=result.get("analysis"),
                agent_results=result.get("agent_results"),
                duration_seconds=result.get("duration_seconds", 0.0)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Analysis failed")
            )

    except Exception as e:
        logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{ticker}/latest")
async def get_latest_analysis(ticker: str):
    """
    Get the most recent analysis for a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Latest analysis result
    """
    ticker = ticker.upper()

    try:
        latest = db_manager.get_latest_analysis(ticker)

        if latest:
            # Get full analysis with agent results
            analysis_id = latest.get("id")
            full_analysis = db_manager.get_analysis_with_agents(analysis_id)
            return full_analysis
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for {ticker}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{ticker}/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(ticker: str, limit: int = 10):
    """
    Get analysis history for a ticker.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of records to return

    Returns:
        List of historical analyses
    """
    ticker = ticker.upper()

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    try:
        history = db_manager.get_analysis_history(ticker, limit)

        return AnalysisHistoryResponse(
            ticker=ticker,
            analyses=history,
            total_count=len(history)
        )

    except Exception as e:
        logger.error(f"Failed to retrieve history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{ticker}/export/csv")
async def export_analysis_csv(
    ticker: str,
    analysis_id: Optional[int] = Query(default=None, description="Specific analysis ID to export. Default: latest."),
):
    """
    Export an analysis as a downloadable CSV file.

    Args:
        ticker: Stock ticker symbol
        analysis_id: Optional analysis ID; defaults to the most recent analysis

    Returns:
        CSV file download
    """
    ticker = ticker.upper()

    try:
        if analysis_id is None:
            latest = db_manager.get_latest_analysis(ticker)
            if not latest:
                raise HTTPException(status_code=404, detail=f"No analysis found for {ticker}")
            analysis_id = latest["id"]

        full = db_manager.get_analysis_with_agents(analysis_id)
        if not full:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

        if full["ticker"] != ticker:
            raise HTTPException(status_code=400, detail=f"Analysis {analysis_id} does not belong to {ticker}")

        output = io.StringIO()
        writer = csv.writer(output)

        # --- Section 1: Analysis Summary ---
        writer.writerow(["Section", "Field", "Value"])
        writer.writerow(["Summary", "Ticker", full["ticker"]])
        writer.writerow(["Summary", "Timestamp", full["timestamp"]])
        writer.writerow(["Summary", "Recommendation", full.get("recommendation", "")])
        writer.writerow(["Summary", "Score", full.get("score", "")])
        writer.writerow(["Summary", "Confidence Score", full.get("confidence_score", "")])
        writer.writerow(["Summary", "Sentiment Score", full.get("overall_sentiment_score", "")])
        writer.writerow(["Summary", "Duration (s)", full.get("duration_seconds", "")])
        writer.writerow(["Summary", "Reasoning", full.get("solution_agent_reasoning", "")])
        writer.writerow(["Summary", "Decision Card", json.dumps(full.get("decision_card")) if full.get("decision_card") else ""])
        writer.writerow(["Summary", "Change Summary", json.dumps(full.get("change_summary")) if full.get("change_summary") else ""])

        # --- Section 2: Agent Results ---
        writer.writerow([])
        writer.writerow(["Agent", "Success", "Duration (s)", "Data Source", "Error"])
        for agent in full.get("agents", []):
            data = agent.get("data") or {}
            data_source = data.get("data_source", "")
            writer.writerow([
                agent.get("agent_type", ""),
                agent.get("success", ""),
                agent.get("duration_seconds", ""),
                data_source,
                agent.get("error", ""),
            ])

        # --- Section 3: Sentiment Factors ---
        sentiment_factors = full.get("sentiment_factors", {})
        if sentiment_factors:
            writer.writerow([])
            writer.writerow(["Sentiment Factor", "Score", "Weight", "Contribution"])
            for factor, vals in sentiment_factors.items():
                writer.writerow([
                    factor,
                    vals.get("score", ""),
                    vals.get("weight", ""),
                    vals.get("contribution", ""),
                ])

        output.seek(0)
        filename = f"{ticker}_analysis_{full['timestamp'][:10]}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export CSV for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{ticker}/export/pdf")
async def export_analysis_pdf(
    ticker: str,
    analysis_id: Optional[int] = Query(default=None, description="Specific analysis ID to export. Default: latest."),
):
    """
    Export an analysis as a downloadable PDF report.

    Args:
        ticker: Stock ticker symbol
        analysis_id: Optional analysis ID; defaults to the most recent analysis

    Returns:
        PDF file download
    """
    from .pdf_report import PDFReportGenerator

    ticker = ticker.upper()

    try:
        if analysis_id is None:
            latest = db_manager.get_latest_analysis(ticker)
            if not latest:
                raise HTTPException(status_code=404, detail=f"No analysis found for {ticker}")
            analysis_id = latest["id"]

        full = db_manager.get_analysis_with_agents(analysis_id)
        if not full:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

        if full["ticker"] != ticker:
            raise HTTPException(status_code=400, detail=f"Analysis {analysis_id} does not belong to {ticker}")

        generator = PDFReportGenerator()
        pdf_bytes = generator.generate(full)

        filename = f"{ticker}_analysis_{full['timestamp'][:10]}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export PDF for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{ticker}/history/detailed")
async def get_detailed_history(
    ticker: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[str] = Query(default=None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(default=None, description="End date filter (ISO format)"),
    recommendation: Optional[str] = Query(default=None, description="Filter by recommendation: BUY, HOLD, SELL"),
    min_ev_score: Optional[float] = Query(default=None, description="Minimum EV score (7d)"),
    max_ev_score: Optional[float] = Query(default=None, description="Maximum EV score (7d)"),
    min_confidence_calibrated: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    max_confidence_calibrated: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    min_data_quality_score: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    regime_label: Optional[str] = Query(default=None, description="risk_on, risk_off, or transition"),
):
    """
    Get paginated, filtered analysis history for a ticker.

    Args:
        ticker: Stock ticker symbol
        limit: Max records per page (1-200)
        offset: Records to skip
        start_date: Optional start date filter
        end_date: Optional end date filter
        recommendation: Optional recommendation filter (BUY, HOLD, SELL)

    Returns:
        Paginated history with items, total_count, has_more
    """
    ticker = ticker.upper()

    if recommendation and recommendation.upper() not in ("BUY", "HOLD", "SELL"):
        raise HTTPException(status_code=400, detail="recommendation must be BUY, HOLD, or SELL")

    try:
        result = db_manager.get_analysis_history_with_filters(
            ticker=ticker,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
            recommendation=recommendation,
            min_ev_score=min_ev_score,
            max_ev_score=max_ev_score,
            min_confidence_calibrated=min_confidence_calibrated,
            max_confidence_calibrated=max_confidence_calibrated,
            min_data_quality_score=min_data_quality_score,
            regime_label=regime_label,
        )
        return {"ticker": ticker, **result}
    except Exception as e:
        logger.error(f"Failed to retrieve detailed history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/analysis/{analysis_id}")
async def delete_analysis(analysis_id: int):
    """
    Delete a specific analysis record and its associated data.

    Args:
        analysis_id: ID of the analysis to delete

    Returns:
        Success confirmation
    """
    try:
        deleted = db_manager.delete_analysis(analysis_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
        return {"success": True, "message": f"Analysis {analysis_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/tickers")
async def get_analyzed_tickers():
    """
    List all tickers that have been analyzed, with counts and latest recommendation.

    Returns:
        List of analyzed tickers with metadata
    """
    try:
        tickers = db_manager.get_all_analyzed_tickers()
        return {"tickers": tickers, "total_count": len(tickers)}
    except Exception as e:
        logger.error(f"Failed to retrieve analyzed tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Watchlist Endpoints ──────────────────────────────────────────────

@app.post("/api/watchlists")
async def create_watchlist(body: WatchlistCreate):
    """Create a new watchlist."""
    try:
        wl = db_manager.create_watchlist(body.name)
        return wl
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"Watchlist '{body.name}' already exists")
        logger.error(f"Failed to create watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/watchlists")
async def get_watchlists():
    """Get all watchlists with their tickers."""
    try:
        watchlists = db_manager.get_watchlists()
        return {"watchlists": watchlists, "total_count": len(watchlists)}
    except Exception as e:
        logger.error(f"Failed to get watchlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/watchlists/{watchlist_id}")
async def get_watchlist(watchlist_id: int):
    """Get a single watchlist with tickers and latest analyses."""
    try:
        wl = db_manager.get_watchlist(watchlist_id)
        if not wl:
            raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")
        # Enrich with latest analysis data per ticker
        analyses = db_manager.get_watchlist_latest_analyses(watchlist_id)
        wl["analyses"] = analyses
        return wl
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/watchlists/{watchlist_id}")
async def rename_watchlist(watchlist_id: int, body: WatchlistRename):
    """Rename a watchlist."""
    try:
        success = db_manager.rename_watchlist(watchlist_id, body.name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")
        return {"success": True, "message": f"Watchlist renamed to '{body.name}'"}
    except HTTPException:
        raise
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"Watchlist '{body.name}' already exists")
        logger.error(f"Failed to rename watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: int):
    """Delete a watchlist."""
    try:
        deleted = db_manager.delete_watchlist(watchlist_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")
        return {"success": True, "message": f"Watchlist {watchlist_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlists/{watchlist_id}/tickers")
async def add_ticker_to_watchlist(watchlist_id: int, body: WatchlistTickerAdd):
    """Add a ticker to a watchlist."""

    ticker = body.ticker.upper()
    if not re.match(r'^[A-Z]{1,5}$', ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    try:
        success = db_manager.add_ticker_to_watchlist(watchlist_id, ticker)
        if not success:
            raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")
        return {"success": True, "ticker": ticker, "watchlist_id": watchlist_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add {ticker} to watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/watchlists/{watchlist_id}/tickers/{ticker}")
async def remove_ticker_from_watchlist(watchlist_id: int, ticker: str):
    """Remove a ticker from a watchlist."""
    ticker = ticker.upper()
    try:
        removed = db_manager.remove_ticker_from_watchlist(watchlist_id, ticker)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} not in watchlist {watchlist_id}")
        return {"success": True, "ticker": ticker, "watchlist_id": watchlist_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove {ticker} from watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/watchlists/{watchlist_id}/analyze")
async def analyze_watchlist(
    watchlist_id: int,
    agents: Optional[str] = Query(
        default=None,
        description=(
            "Comma-separated list of agents to run per ticker: "
            "news,sentiment,fundamentals,market,technical,macro,options. Default: all."
        ),
    ),
):
    """
    Run analysis for all tickers in a watchlist.
    Returns results as they complete.
    """
    wl = db_manager.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")

    tickers = [t["ticker"] for t in wl.get("tickers", [])]
    if not tickers:
        raise HTTPException(status_code=400, detail="Watchlist has no tickers")

    requested_agents = None
    if agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options", "leadership"}
        requested_agents = [a.strip().lower() for a in agents.split(",") if a.strip()]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(valid_agents))}",
            )

    async def batch_generator():
        concurrency = 4
        semaphore = asyncio.Semaphore(concurrency)

        async def _analyze_one(ticker: str) -> Dict[str, Any]:
            async with semaphore:
                orchestrator = Orchestrator(
                    db_manager=db_manager,
                    rate_limiter=av_rate_limiter,
                    av_cache=av_cache,
                )
                result = await orchestrator.analyze_ticker(ticker, requested_agents=requested_agents)
                return {
                    "ticker": ticker,
                    "success": result.get("success", False),
                    "analysis_id": result.get("analysis_id"),
                    "analysis_schema_version": ((result.get("analysis") or {}).get("analysis_schema_version")),
                    "recommendation": (result.get("analysis") or {}).get("recommendation"),
                    "score": (result.get("analysis") or {}).get("score"),
                    "confidence": (result.get("analysis") or {}).get("confidence"),
                    "ev_score_7d": (result.get("analysis") or {}).get("ev_score_7d"),
                    "confidence_calibrated": (result.get("analysis") or {}).get("confidence_calibrated"),
                    "data_quality_score": (result.get("analysis") or {}).get("data_quality_score"),
                    "duration_seconds": result.get("duration_seconds", 0),
                    "error": result.get("error"),
                }

        tasks = [asyncio.create_task(_analyze_one(ticker)) for ticker in tickers]
        completed = 0
        for task in asyncio.as_completed(tasks):
            completed += 1
            try:
                payload = await task
            except Exception as e:
                logger.error("Watchlist analysis task failed: %s", e)
                payload = {"success": False, "error": str(e), "ticker": "UNKNOWN"}

            if payload.get("success"):
                yield f"event: result\ndata: {json.dumps(payload, default=str)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps(payload, default=str)}\n\n"

        opportunities = []
        if Config.WATCHLIST_RANKING_ENABLED:
            try:
                opportunities = db_manager.get_watchlist_opportunities(
                    watchlist_id=watchlist_id,
                    limit=max(1, len(tickers)),
                    min_quality=None,
                    min_ev=None,
                )
            except Exception as exc:
                logger.warning("Failed to compute watchlist opportunities: %s", exc)

        yield f"event: done\ndata: {json.dumps({'message': 'All analyses complete', 'ticker_count': len(tickers), 'completed': completed, 'opportunities': opportunities}, default=str)}\n\n"

    return StreamingResponse(
        batch_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/watchlists/{watchlist_id}/opportunities")
async def get_watchlist_opportunities(
    watchlist_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    min_quality: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    min_ev: Optional[float] = Query(default=None),
):
    """Return ranked watchlist opportunities from latest analyses."""
    wl = db_manager.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail=f"Watchlist {watchlist_id} not found")

    opportunities = db_manager.get_watchlist_opportunities(
        watchlist_id=watchlist_id,
        limit=limit,
        min_quality=min_quality,
        min_ev=min_ev,
    )
    return {"watchlist_id": watchlist_id, "opportunities": opportunities, "total_count": len(opportunities)}


# ─── Schedule Endpoints ─────────────────────────────────────────────

@app.post("/api/schedules")
async def create_schedule(body: ScheduleCreate):
    """Create a new schedule for recurring analysis."""

    ticker = body.ticker.upper()
    if not re.match(r'^[A-Z]{1,5}$', ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    try:
        schedule = db_manager.create_schedule(ticker, body.interval_minutes, body.agents)
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.add_schedule(schedule)
        return schedule
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"Schedule for '{ticker}' already exists")
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedules")
async def get_schedules():
    """Get all schedules."""
    try:
        schedules = db_manager.get_schedules()
        return {"schedules": schedules, "total_count": len(schedules)}
    except Exception as e:
        logger.error(f"Failed to get schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedules/{schedule_id}")
async def get_schedule(schedule_id: int):
    """Get a schedule with recent runs."""
    try:
        schedule = db_manager.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
        runs = db_manager.get_schedule_runs(schedule_id)
        schedule["runs"] = runs
        return schedule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/schedules/{schedule_id}")
async def update_schedule(schedule_id: int, body: ScheduleUpdate):
    """Update a schedule."""
    try:
        update_fields = body.model_dump(exclude_none=True)
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        success = db_manager.update_schedule(schedule_id, **update_fields)
        if not success:
            raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

        updated = db_manager.get_schedule(schedule_id)
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.update_schedule_job(updated)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int):
    """Delete a schedule."""
    try:
        deleted = db_manager.delete_schedule(schedule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.remove_schedule(schedule_id)
        return {"success": True, "message": f"Schedule {schedule_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedules/{schedule_id}/runs")
async def get_schedule_runs(schedule_id: int, limit: int = Query(default=20, ge=1, le=100)):
    """Get run history for a schedule."""
    try:
        schedule = db_manager.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
        runs = db_manager.get_schedule_runs(schedule_id, limit=limit)
        return {"schedule_id": schedule_id, "runs": runs, "total_count": len(runs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runs for schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Portfolio Endpoints ───────────────────────────────────────────────

@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio profile, holdings, and exposure snapshot."""
    try:
        profile = db_manager.get_portfolio_profile()
        holdings = db_manager.list_portfolio_holdings()
        snapshot = db_manager.get_portfolio_snapshot()
        return {
            "profile": profile,
            "holdings": holdings,
            "snapshot": snapshot,
        }
    except Exception as e:
        logger.error(f"Failed to fetch portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/portfolio/profile")
async def update_portfolio_profile(body: PortfolioProfileUpdate):
    """Update singleton portfolio profile."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        profile = db_manager.upsert_portfolio_profile(**updates)
        return profile
    except Exception as e:
        logger.error(f"Failed to update portfolio profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/holdings")
async def get_portfolio_holdings():
    """List all portfolio holdings."""
    try:
        holdings = db_manager.list_portfolio_holdings()
        return {"holdings": holdings, "total_count": len(holdings)}
    except Exception as e:
        logger.error(f"Failed to list holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/risk-summary")
async def get_portfolio_risk_summary():
    """Compute portfolio-level risk metrics across all holdings."""
    try:
        holdings = db_manager.list_portfolio_holdings()
        profile = db_manager.get_portfolio_profile()
        summary = PortfolioEngine.portfolio_risk_summary(holdings, profile)
        return summary
    except Exception as e:
        logger.error(f"Failed to compute portfolio risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/portfolio/holdings")
async def create_portfolio_holding(body: PortfolioHoldingCreate):
    """Create a portfolio holding."""

    import yfinance as yf

    ticker = body.ticker.upper()
    if not re.match(r"^[A-Z]{1,5}$", ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    market_value = body.market_value
    if market_value is None:
        inferred_price = None
        try:
            fast_info = await asyncio.to_thread(lambda: yf.Ticker(ticker).fast_info)
            inferred_price = (
                fast_info.get("lastPrice")
                or fast_info.get("regularMarketPrice")
                or fast_info.get("previousClose")
            )
        except Exception:
            inferred_price = None

        if inferred_price is None and body.avg_cost is not None:
            inferred_price = body.avg_cost
        if inferred_price is not None:
            market_value = float(inferred_price) * float(body.shares)
        else:
            market_value = 0.0

    try:
        holding = db_manager.create_portfolio_holding(
            ticker=ticker,
            shares=body.shares,
            avg_cost=body.avg_cost,
            market_value=market_value,
            sector=body.sector,
            beta=body.beta,
        )
        return holding
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(status_code=409, detail=f"Holding for {ticker} already exists")
        logger.error(f"Failed to create holding for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/portfolio/holdings/{holding_id}")
async def update_portfolio_holding(holding_id: int, body: PortfolioHoldingUpdate):
    """Update an existing portfolio holding."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "ticker" in updates:
    

        ticker = str(updates["ticker"]).upper()
        if not re.match(r"^[A-Z]{1,5}$", ticker):
            raise HTTPException(status_code=400, detail="Invalid ticker symbol format")
        updates["ticker"] = ticker

    try:
        holding = db_manager.update_portfolio_holding(holding_id, **updates)
        if not holding:
            raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
        return holding
    except HTTPException:
        raise
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            raise HTTPException(status_code=409, detail="Ticker already exists in holdings")
        logger.error(f"Failed to update holding {holding_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/portfolio/holdings/{holding_id}")
async def delete_portfolio_holding(holding_id: int):
    """Delete a portfolio holding."""
    try:
        deleted = db_manager.delete_portfolio_holding(holding_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Holding {holding_id} not found")
        return {"success": True, "deleted_id": holding_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete holding {holding_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Macro Catalyst Endpoints ──────────────────────────────────────────

@app.get("/api/macro-events")
async def get_macro_events(
    date_from: Optional[str] = Query(default=None, alias="from"),
    date_to: Optional[str] = Query(default=None, alias="to"),
):
    """List macro catalyst events over a date range."""
    try:
        events = db_manager.list_macro_events(
            date_from=date_from,
            date_to=date_to,
            enabled_only=False,
        )
        return {"events": events, "total_count": len(events)}
    except Exception as e:
        logger.error(f"Failed to get macro events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Calibration Endpoints ─────────────────────────────────────────────

@app.get("/api/calibration/summary")
async def get_calibration_summary(window_days: int = Query(default=180, ge=30, le=365)):
    """Get latest calibration metrics by horizon."""
    try:
        return db_manager.get_calibration_summary(window_days=window_days, horizons=[1, 7, 30])
    except Exception as e:
        logger.error(f"Failed to get calibration summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calibration/ticker/{ticker}")
async def get_ticker_calibration(ticker: str, limit: int = Query(default=100, ge=1, le=500)):
    """Get per-outcome calibration rows for a ticker."""
    ticker = ticker.upper()
    try:
        outcomes = db_manager.get_outcomes_for_ticker(ticker=ticker, limit=limit)
        return {"ticker": ticker, "outcomes": outcomes, "total_count": len(outcomes)}
    except Exception as e:
        logger.error(f"Failed to get ticker calibration for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calibration/reliability")
async def get_calibration_reliability(horizon_days: int = Query(default=7, ge=1, le=30)):
    """Get latest reliability bins for a horizon (supported: 1, 7, 30)."""
    if horizon_days not in {1, 7, 30}:
        raise HTTPException(status_code=400, detail="horizon_days must be 1, 7, or 30")
    try:
        return db_manager.get_confidence_reliability_summary(horizon_days=horizon_days)
    except Exception as e:
        logger.error(f"Failed to get reliability bins for {horizon_days}d: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rollout/phase7/status")
async def get_phase7_rollout_status(window_hours: int = Query(default=72, ge=1, le=720)):
    """Return rollout metrics and gate status for Phase 7 production enablement."""
    try:
        status = compute_phase7_rollout_status(
            db_manager=db_manager,
            window_hours=window_hours,
        )
        status["feature_flags"] = {
            "SIGNAL_CONTRACT_V2_ENABLED": Config.SIGNAL_CONTRACT_V2_ENABLED,
            "CALIBRATION_ECONOMICS_ENABLED": Config.CALIBRATION_ECONOMICS_ENABLED,
            "PORTFOLIO_OPTIMIZER_V2_ENABLED": Config.PORTFOLIO_OPTIMIZER_V2_ENABLED,
            "ALERTS_V2_ENABLED": Config.ALERTS_V2_ENABLED,
            "WATCHLIST_RANKING_ENABLED": Config.WATCHLIST_RANKING_ENABLED,
            "UI_PM_DASHBOARD_ENABLED": Config.UI_PM_DASHBOARD_ENABLED,
            "SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED": Config.SCHEDULED_SIGNAL_CONTRACT_V2_ENABLED,
            "SCHEDULED_CALIBRATION_ECONOMICS_ENABLED": Config.SCHEDULED_CALIBRATION_ECONOMICS_ENABLED,
            "SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED": Config.SCHEDULED_PORTFOLIO_OPTIMIZER_V2_ENABLED,
            "SCHEDULED_ALERTS_V2_ENABLED": Config.SCHEDULED_ALERTS_V2_ENABLED,
        }
        return status
    except Exception as e:
        logger.error(f"Failed to build Phase 7 rollout status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Alert Endpoints ────────────────────────────────────────────

@app.post("/api/alerts")
async def create_alert_rule(body: AlertRuleCreate):
    """Create a new alert rule."""
    ticker = body.ticker.upper()
    base_types = {
        "recommendation_change",
        "score_above",
        "score_below",
        "confidence_above",
        "confidence_below",
    }
    v2_types = {
        "ev_above",
        "ev_below",
        "regime_change",
        "data_quality_below",
        "calibration_drop",
    }
    valid_types = set(base_types)
    if Config.ALERTS_V2_ENABLED:
        valid_types.update(v2_types)
    if body.rule_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid rule_type. Valid: {', '.join(sorted(valid_types))}")
    threshold_optional_types = {"recommendation_change", "regime_change"} if Config.ALERTS_V2_ENABLED else {
        "recommendation_change"
    }
    if body.rule_type not in threshold_optional_types and body.threshold is None:
        threshold_msg = (
            "threshold required for score/confidence rules"
            if not Config.ALERTS_V2_ENABLED
            else "threshold required for score/confidence/ev/data_quality/calibration_drop rules"
        )
        raise HTTPException(
            status_code=400,
            detail=threshold_msg,
        )
    try:
        rule = db_manager.create_alert_rule(ticker, body.rule_type, body.threshold)
        return rule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_alert_rules(ticker: Optional[str] = Query(default=None)):
    """Get all alert rules, optionally filtered by ticker."""
    try:
        ticker = ticker.upper() if ticker else None
        rules = db_manager.get_alert_rules(ticker=ticker)
        return {"rules": rules, "total_count": len(rules)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts/notifications")
async def get_alert_notifications(
    unacknowledged: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get alert notifications."""
    try:
        notifications = db_manager.get_alert_notifications(unacknowledged_only=unacknowledged, limit=limit)
        return {"notifications": notifications, "total_count": len(notifications)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts/notifications/count")
async def get_unacknowledged_count():
    """Get count of unacknowledged notifications (for badge)."""
    try:
        count = db_manager.get_unacknowledged_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alerts/notifications/{notification_id}/acknowledge")
async def acknowledge_notification(notification_id: int):
    """Acknowledge a notification."""
    try:
        success = db_manager.acknowledge_alert(notification_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts/{rule_id}")
async def get_alert_rule(rule_id: int):
    """Get a specific alert rule."""
    try:
        rule = db_manager.get_alert_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/alerts/{rule_id}")
async def update_alert_rule(rule_id: int, body: AlertRuleUpdate):
    """Update an alert rule."""
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        if "rule_type" in updates:
            base_types = {
                "recommendation_change",
                "score_above",
                "score_below",
                "confidence_above",
                "confidence_below",
            }
            v2_types = {
                "ev_above",
                "ev_below",
                "regime_change",
                "data_quality_below",
                "calibration_drop",
            }
            valid_types = set(base_types)
            if Config.ALERTS_V2_ENABLED:
                valid_types.update(v2_types)
            if updates["rule_type"] not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid rule_type. Valid: {', '.join(sorted(valid_types))}",
                )
        success = db_manager.update_alert_rule(rule_id, **updates)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")
        return db_manager.get_alert_rule(rule_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/alerts/{rule_id}")
async def delete_alert_rule(rule_id: int):
    """Delete an alert rule."""
    try:
        success = db_manager.delete_alert_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert rule {rule_id} not found")
        return {"success": True, "deleted_id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyze/{ticker}/stream")
async def analyze_ticker_stream(
    ticker: str,
    agents: Optional[str] = Query(
        default=None,
        description="Comma-separated list of agents to run: news,sentiment,fundamentals,market,technical,macro. Default: all.",
    ),
):
    """
    Stream analysis progress and results via Server-Sent Events (SSE).

    Opens a long-lived HTTP connection that streams:
    - ``progress`` events as each agent starts/completes
    - ``result`` event with the final analysis
    - ``error`` event if analysis fails

    Args:
        ticker: Stock ticker symbol (e.g., NVDA, AAPL)
        agents: Optional comma-separated agent names to run
    """
    ticker = ticker.upper()


    if not re.match(r'^[A-Z]{1,5}$', ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    requested_agents = None
    if agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical", "macro", "options", "leadership"}
        requested_agents = [a.strip().lower() for a in agents.split(",")]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(valid_agents))}"
            )

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(update: dict):
            await queue.put(("progress", update))

        orchestrator = Orchestrator(
            db_manager=db_manager,
            progress_callback=progress_callback,
            rate_limiter=av_rate_limiter,
            av_cache=av_cache,
        )

        async def run_analysis():
            try:
                result = await orchestrator.analyze_ticker(ticker, requested_agents=requested_agents)
                if result.get("success"):
                    await queue.put(("result", {
                        "success": True,
                        "ticker": ticker,
                        "analysis_id": result.get("analysis_id"),
                        "analysis_schema_version": ((result.get("analysis") or {}).get("analysis_schema_version")),
                        "analysis": result.get("analysis"),
                        "agent_results": result.get("agent_results"),
                        "duration_seconds": result.get("duration_seconds", 0.0),
                    }))
                else:
                    await queue.put(("error", {
                        "error": result.get("error", "Analysis failed"),
                        "ticker": ticker,
                    }))
            except Exception as e:
                logger.error(f"SSE analysis failed for {ticker}: {e}", exc_info=True)
                await queue.put(("error", {"error": str(e), "ticker": ticker}))

        task = asyncio.create_task(run_analysis())

        try:
            while True:
                event_type, data = await queue.get()
                yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
                if event_type in ("result", "error"):
                    break
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.API_RELOAD
    )
