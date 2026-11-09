from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_analyzed: int
    fraud_predictions: int
    legitimate_predictions: int
    fraud_prediction_rate: float
    risk_distribution: dict[str, int]


class TrendPoint(BaseModel):
    period: str
    total: int
    fraud: int
    legitimate: int
    fraud_rate: float


class AnalyticsTrends(BaseModel):
    bucket: str
    points: list[TrendPoint]
