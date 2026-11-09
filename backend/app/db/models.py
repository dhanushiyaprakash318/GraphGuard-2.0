from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PredictionRecord(Base):
    __tablename__ = "prediction_records"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            "model_version",
            name="uq_transaction_model_version",
        ),
        Index("ix_prediction_records_created_at", "created_at"),
        Index("ix_prediction_records_risk_category", "risk_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    fraud_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_category: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_amt: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_cd: Mapped[str | None] = mapped_column(String(16), nullable=True)
