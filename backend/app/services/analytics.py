from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import PredictionRecord


def get_summary(db: Session) -> dict:
    total = int(db.scalar(select(func.count()).select_from(PredictionRecord)) or 0)
    fraud = int(
        db.scalar(
            select(func.count()).select_from(PredictionRecord).where(
                PredictionRecord.predicted_fraud.is_(True)
            )
        )
        or 0
    )
    legitimate = total - fraud
    rate = round((fraud / total), 6) if total else 0.0

    risk_rows = db.execute(
        select(PredictionRecord.risk_category, func.count())
        .group_by(PredictionRecord.risk_category)
    ).all()
    risk_distribution = {str(name): int(count) for name, count in risk_rows}
    for key in ("Low", "Medium", "High", "Critical"):
        risk_distribution.setdefault(key, 0)

    return {
        "total_analyzed": total,
        "fraud_predictions": fraud,
        "legitimate_predictions": legitimate,
        "fraud_prediction_rate": rate,
        "risk_distribution": risk_distribution,
    }


def get_trends(db: Session, *, bucket: str = "day", days: int = 30) -> dict:
    bucket = bucket if bucket in {"hour", "day"} else "day"
    days = min(max(days, 1), 365)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        trunc_unit = "hour" if bucket == "hour" else "day"
        period_expr = func.date_trunc(trunc_unit, PredictionRecord.created_at)
    else:
        # SQLite: truncate to day or hour via strftime
        fmt = "%Y-%m-%d %H:00:00" if bucket == "hour" else "%Y-%m-%d"
        period_expr = func.strftime(fmt, PredictionRecord.created_at)

    fraud_count = func.sum(
        case((PredictionRecord.predicted_fraud.is_(True), 1), else_=0)
    )
    total_count = func.count()

    rows = db.execute(
        select(
            period_expr.label("period"),
            total_count.label("total"),
            fraud_count.label("fraud"),
        )
        .where(PredictionRecord.created_at >= since)
        .group_by(period_expr)
        .order_by(period_expr)
    ).all()

    points = []
    for period, total, fraud in rows:
        total_i = int(total or 0)
        fraud_i = int(fraud or 0)
        period_str = period.isoformat() if isinstance(period, datetime) else str(period)
        points.append(
            {
                "period": period_str,
                "total": total_i,
                "fraud": fraud_i,
                "legitimate": total_i - fraud_i,
                "fraud_rate": round(fraud_i / total_i, 6) if total_i else 0.0,
            }
        )

    return {"bucket": bucket, "points": points}


def get_probability_bins(db: Session, bins: int = 10) -> list[dict]:
    """Optional helper for analytics charts."""
    bins = min(max(bins, 2), 20)
    rows = db.scalars(select(PredictionRecord.fraud_probability)).all()
    if not rows:
        return [
            {"bin_start": i / bins, "bin_end": (i + 1) / bins, "count": 0}
            for i in range(bins)
        ]

    counts = [0] * bins
    for value in rows:
        idx = min(int(value * bins), bins - 1)
        counts[idx] += 1

    return [
        {
            "bin_start": round(i / bins, 4),
            "bin_end": round((i + 1) / bins, 4),
            "count": counts[i],
        }
        for i in range(bins)
    ]
