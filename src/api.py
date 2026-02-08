"""FastAPI application for multi-agent market research."""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import logging
from datetime import datetime
import asyncio

from .models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisHistoryResponse,
    HealthCheckResponse,
    ProgressUpdate
)
from .orchestrator import Orchestrator
from .config import Config
from .database import DatabaseManager
from .av_rate_limiter import AVRateLimiter
from .av_cache import AVCache

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Market Research API",
    description="AI-powered stock market analysis using specialized agents",
    version="0.1.0"
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

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, ticker: str):
        """Connect a WebSocket for a ticker."""
        await websocket.accept()
        if ticker not in self.active_connections:
            self.active_connections[ticker] = []
        self.active_connections[ticker].append(websocket)
        logger.info(f"WebSocket connected for {ticker}")

    def disconnect(self, websocket: WebSocket, ticker: str):
        """Disconnect a WebSocket."""
        if ticker in self.active_connections:
            if websocket in self.active_connections[ticker]:
                self.active_connections[ticker].remove(websocket)
            if not self.active_connections[ticker]:
                del self.active_connections[ticker]
        logger.info(f"WebSocket disconnected for {ticker}")

    async def send_update(self, ticker: str, update: dict):
        """Send update to all connected clients for a ticker."""
        if ticker in self.active_connections:
            disconnected = []
            for connection in self.active_connections[ticker]:
                try:
                    await connection.send_json(update)
                except Exception as e:
                    logger.error(f"Failed to send update: {e}")
                    disconnected.append(connection)

            # Remove disconnected clients
            for connection in disconnected:
                self.disconnect(connection, ticker)


manager = ConnectionManager()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Multi-Agent Market Research API",
        "version": "0.1.0",
        "endpoints": {
            "analyze": "POST /api/analyze/{ticker}",
            "latest": "GET /api/analysis/{ticker}/latest",
            "history": "GET /api/analysis/{ticker}/history",
            "health": "GET /health",
            "websocket": "WS /ws/analysis/{ticker}"
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
        timestamp=datetime.utcnow().isoformat(),
        database_connected=db_connected,
        config_valid=config_valid
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
    import re
    if not re.match(r'^[A-Z]{1,5}$', ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol format")

    # Parse and validate agent list
    requested_agents = None
    if agents:
        valid_agents = {"news", "sentiment", "fundamentals", "market", "technical"}
        requested_agents = [a.strip().lower() for a in agents.split(",")]
        invalid = set(requested_agents) - valid_agents
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent names: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(valid_agents))}"
            )

    logger.info(f"Starting analysis for {ticker}")

    # Create progress callback for WebSocket updates
    async def progress_callback(update: dict):
        await manager.send_update(ticker, update)

    # Create orchestrator with shared AV infrastructure
    orchestrator = Orchestrator(
        db_manager=db_manager,
        progress_callback=progress_callback,
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


@app.websocket("/ws/analysis/{ticker}")
async def websocket_endpoint(websocket: WebSocket, ticker: str):
    """
    WebSocket endpoint for real-time analysis updates.

    Args:
        websocket: WebSocket connection
        ticker: Stock ticker symbol
    """
    ticker = ticker.upper()
    await manager.connect(websocket, ticker)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "ticker": ticker,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=Config.WS_HEARTBEAT_INTERVAL
                )

                # Echo back to confirm connection is alive
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, ticker)
        logger.info(f"Client disconnected from {ticker}")
    except Exception as e:
        logger.error(f"WebSocket error for {ticker}: {e}")
        manager.disconnect(websocket, ticker)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.API_RELOAD
    )
