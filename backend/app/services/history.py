from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import PredictionRecord

logger = get_logger(__name__)


def save_prediction(db: Session, prediction: dict) -> PredictionRecord:
    """Persist a prediction, upserting on (transaction_id, model_version)."""
    settings = get_settings()
    model_version = settings.model_version

    values = {
        "transaction_id": str(prediction["transaction_id"]),
        "fraud_probability": float(prediction["fraud_probability"]),
        "predicted_fraud": bool(prediction["predicted_fraud"]),
        "risk_category": str(prediction["risk_category"]),
        "model_version": model_version,
        "transaction_amt": prediction.get("transaction_amt"),
        "product_cd": prediction.get("product_cd"),
    }

    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
    stmt = insert_fn(PredictionRecord).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["transaction_id", "model_version"],
        set_={
            "fraud_probability": stmt.excluded.fraud_probability,
            "predicted_fraud": stmt.excluded.predicted_fraud,
            "risk_category": stmt.excluded.risk_category,
            "transaction_amt": stmt.excluded.transaction_amt,
            "product_cd": stmt.excluded.product_cd,
            "created_at": func.now(),
        },
    )
    db.execute(stmt)
    db.commit()

    record = db.scalar(
        select(PredictionRecord).where(
            PredictionRecord.transaction_id == values["transaction_id"],
            PredictionRecord.model_version == model_version,
        )
    )
    return record


def list_transactions(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    risk_category: str | None = None,
    predicted_fraud: int | None = None,
) -> tuple[list[PredictionRecord], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(PredictionRecord)
    count_query = select(func.count()).select_from(PredictionRecord)

    if search:
        pattern = f"%{search}%"
        filt = or_(
            PredictionRecord.transaction_id.ilike(pattern),
            PredictionRecord.product_cd.ilike(pattern),
        )
        query = query.where(filt)
        count_query = count_query.where(filt)

    if risk_category:
        query = query.where(PredictionRecord.risk_category == risk_category)
        count_query = count_query.where(PredictionRecord.risk_category == risk_category)

    if predicted_fraud is not None:
        flag = bool(predicted_fraud)
        query = query.where(PredictionRecord.predicted_fraud.is_(flag))
        count_query = count_query.where(PredictionRecord.predicted_fraud.is_(flag))

    total = int(db.scalar(count_query) or 0)
    items = list(
        db.scalars(
            query.order_by(PredictionRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total
