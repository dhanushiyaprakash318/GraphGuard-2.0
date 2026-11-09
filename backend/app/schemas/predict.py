from typing import Any

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    transaction: dict[str, Any] = Field(
        ...,
        description="IEEE-CIS style transaction feature map",
    )


class PredictionDetail(BaseModel):
    fraud_probability: float
    predicted_fraud: int
    risk_category: str
    threshold: float


class PredictResponse(BaseModel):
    success: bool = True
    transaction_id: str
    prediction: PredictionDetail


class BatchPredictRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of transaction feature maps",
    )


class BatchPredictResultItem(BaseModel):
    success: bool
    transaction_id: str | None = None
    prediction: PredictionDetail | None = None
    error: str | None = None


class BatchPredictResponse(BaseModel):
    success: bool
    total: int
    succeeded: int
    failed: int
    results: list[BatchPredictResultItem]
