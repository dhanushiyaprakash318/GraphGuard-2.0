from datetime import datetime

from pydantic import BaseModel


class TransactionRecord(BaseModel):
    id: int
    transaction_id: str
    created_at: datetime
    fraud_probability: float
    predicted_fraud: int
    risk_category: str
    model_version: str
    transaction_amt: float | None = None
    product_cd: str | None = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TransactionRecord]
