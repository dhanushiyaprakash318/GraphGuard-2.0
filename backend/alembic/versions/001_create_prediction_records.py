"""create prediction_records

Revision ID: 001
Revises:
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fraud_probability", sa.Float(), nullable=False),
        sa.Column("predicted_fraud", sa.Boolean(), nullable=False),
        sa.Column("risk_category", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("transaction_amt", sa.Float(), nullable=True),
        sa.Column("product_cd", sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transaction_id",
            "model_version",
            name="uq_transaction_model_version",
        ),
    )
    op.create_index(
        "ix_prediction_records_transaction_id",
        "prediction_records",
        ["transaction_id"],
    )
    op.create_index(
        "ix_prediction_records_created_at",
        "prediction_records",
        ["created_at"],
    )
    op.create_index(
        "ix_prediction_records_risk_category",
        "prediction_records",
        ["risk_category"],
    )


def downgrade() -> None:
    op.drop_index("ix_prediction_records_risk_category", table_name="prediction_records")
    op.drop_index("ix_prediction_records_created_at", table_name="prediction_records")
    op.drop_index("ix_prediction_records_transaction_id", table_name="prediction_records")
    op.drop_table("prediction_records")
