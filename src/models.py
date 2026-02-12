"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class AnalysisRequest(BaseModel):
    """Request model for triggering analysis."""
    ticker: str = Field(..., min_length=1, max_length=5, description="Stock ticker symbol")


class AgentResult(BaseModel):
    """Model for individual agent result."""
    success: bool
    agent_type: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: float
    timestamp: str


class SentimentFactor(BaseModel):
    """Model for sentiment factor."""
    score: float
    weight: float
    contribution: float


class PriceTargets(BaseModel):
    """Model for price targets."""
    entry: Optional[float] = None
    target: Optional[float] = None
    stop_loss: Optional[float] = None


class FinalAnalysis(BaseModel):
    """Model for final analysis output."""
    recommendation: str  # BUY, HOLD, or SELL
    score: int  # -100 to +100
    confidence: float  # 0.0 to 1.0
    reasoning: str
    risks: List[str]
    opportunities: List[str]
    price_targets: Optional[PriceTargets] = None
    position_size: Optional[str] = None  # SMALL, MEDIUM, LARGE
    time_horizon: Optional[str] = None  # SHORT_TERM, MEDIUM_TERM, LONG_TERM
    summary: str


class AnalysisResponse(BaseModel):
    """Response model for analysis."""
    success: bool
    ticker: str
    analysis_id: Optional[int] = None
    analysis: Optional[FinalAnalysis] = None
    agent_results: Optional[Dict[str, AgentResult]] = None
    duration_seconds: float
    error: Optional[str] = None


class AnalysisHistoryItem(BaseModel):
    """Model for historical analysis item."""
    id: int
    ticker: str
    timestamp: str
    recommendation: str
    confidence_score: float
    overall_sentiment_score: float
    duration_seconds: float


class AnalysisHistoryResponse(BaseModel):
    """Response model for analysis history."""
    ticker: str
    analyses: List[AnalysisHistoryItem]
    total_count: int


class ProgressUpdate(BaseModel):
    """Model for progress updates via SSE."""
    stage: str
    ticker: str
    progress: int  # 0-100
    message: Optional[str] = None
    timestamp: str


class WatchlistCreate(BaseModel):
    """Request model for creating a watchlist."""
    name: str = Field(..., min_length=1, max_length=50, description="Watchlist name")


class WatchlistTickerAdd(BaseModel):
    """Request model for adding a ticker to a watchlist."""
    ticker: str = Field(..., min_length=1, max_length=5, description="Stock ticker symbol")


class WatchlistRename(BaseModel):
    """Request model for renaming a watchlist."""
    name: str = Field(..., min_length=1, max_length=50, description="New watchlist name")


class ScheduleCreate(BaseModel):
    """Request model for creating a schedule."""
    ticker: str = Field(..., min_length=1, max_length=5, description="Stock ticker symbol")
    interval_minutes: int = Field(..., ge=30, le=10080, description="Interval in minutes (30 min to 1 week)")
    agents: Optional[str] = Field(default=None, description="Comma-separated agent names, or null for all")


class ScheduleUpdate(BaseModel):
    """Request model for updating a schedule."""
    interval_minutes: Optional[int] = Field(default=None, ge=30, le=10080)
    agents: Optional[str] = None
    enabled: Optional[bool] = None


class AlertRuleCreate(BaseModel):
    """Request model for creating an alert rule."""
    ticker: str = Field(..., min_length=1, max_length=5, description="Stock ticker symbol")
    rule_type: str = Field(..., description="Alert type: recommendation_change, score_above, score_below, confidence_above, confidence_below")
    threshold: Optional[float] = Field(default=None, description="Threshold value (required for score/confidence rules)")


class AlertRuleUpdate(BaseModel):
    """Request model for updating an alert rule."""
    rule_type: Optional[str] = None
    threshold: Optional[float] = None
    enabled: Optional[bool] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    database_connected: bool
    config_valid: bool
