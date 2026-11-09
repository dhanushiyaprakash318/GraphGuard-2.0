from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.transactions import TransactionListResponse, TransactionRecord
from app.services.history import list_transactions

router = APIRouter()


@router.get("/transactions", response_model=TransactionListResponse)
def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    risk_category: str | None = Query(None),
    predicted_fraud: int | None = Query(None, ge=0, le=1),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    items, total = list_transactions(
        db,
        page=page,
        page_size=page_size,
        search=search,
        risk_category=risk_category,
        predicted_fraud=predicted_fraud,
    )
    return TransactionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            TransactionRecord(
                id=row.id,
                transaction_id=row.transaction_id,
                created_at=row.created_at,
                fraud_probability=row.fraud_probability,
                predicted_fraud=int(row.predicted_fraud),
                risk_category=row.risk_category,
                model_version=row.model_version,
                transaction_amt=row.transaction_amt,
                product_cd=row.product_cd,
            )
            for row in items
        ],
    )
