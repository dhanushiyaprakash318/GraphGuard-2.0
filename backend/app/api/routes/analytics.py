from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import AnalyticsSummary, AnalyticsTrends, TrendPoint
from app.services import analytics as analytics_service

router = APIRouter()


@router.get("/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db)) -> AnalyticsSummary:
    return AnalyticsSummary(**analytics_service.get_summary(db))


@router.get("/analytics/trends", response_model=AnalyticsTrends)
def analytics_trends(
    bucket: str = Query("day", pattern="^(hour|day)$"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> AnalyticsTrends:
    data = analytics_service.get_trends(db, bucket=bucket, days=days)
    return AnalyticsTrends(
        bucket=data["bucket"],
        points=[TrendPoint(**point) for point in data["points"]],
    )


@router.get("/analytics/probability-distribution")
def probability_distribution(
    bins: int = Query(10, ge=2, le=20),
    db: Session = Depends(get_db),
) -> dict:
    return {"bins": analytics_service.get_probability_bins(db, bins=bins)}
