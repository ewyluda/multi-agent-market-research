"""API routes for inflection tracking and perception time-series."""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/inflections", tags=["inflections"])


def _get_perception_repo():
    from ..repositories.perception_repo import PerceptionRepository
    import src.api as api_module
    return PerceptionRepository(api_module.db_manager)


@router.get("/{ticker}")
async def get_inflection_history(ticker: str, limit: int = Query(default=50, le=200)):
    repo = _get_perception_repo()
    return repo.get_inflection_history(ticker.upper(), limit=limit)


@router.get("/{ticker}/timeseries")
async def get_timeseries(
    ticker: str,
    kpis: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=1000),
):
    repo = _get_perception_repo()
    kpi_list = [k.strip() for k in kpis.split(",")] if kpis else None
    return repo.get_timeseries(ticker.upper(), kpis=kpi_list, limit=limit)
