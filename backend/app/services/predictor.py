from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EXCLUDED_INPUT_KEYS = {"isFraud"}


class ModelNotLoadedError(RuntimeError):
    pass


class PredictorService:
    """Loads the Fabric-exported LightGBM bundle once and scores transactions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.model = None
        self.feature_columns: list[str] = []
        self.numeric_features: list[str] = []
        self.categorical_features: list[str] = []
        self.category_levels: list[list[str]] = []
        self.numeric_medians: dict[str, float] = {}
        self.threshold: float = 0.1
        self.model_type: str | None = None
        self.loaded: bool = False
        self.model_path: str | None = None

    def load(self, model_path: str | Path | None = None) -> None:
        settings = get_settings()
        path = Path(model_path or settings.model_path)
        if not path.is_absolute():
            # Resolve relative to backend/ package root (parent of app/)
            backend_root = Path(__file__).resolve().parents[2]
            path = (backend_root / path).resolve()

        with self._lock:
            logger.info("Loading prediction bundle from %s", path)
            bundle = joblib.load(path)
            self.model = bundle["model"]
            self.feature_columns = list(bundle["feature_columns"])
            self.numeric_features = list(bundle["numeric_features"])
            self.categorical_features = list(bundle["categorical_features"])
            self.category_levels = list(bundle["category_levels"])
            self.numeric_medians = dict(bundle["numeric_medians"])
            self.threshold = float(bundle["threshold"])
            self.model_type = type(self.model).__name__
            self.model_path = str(path)
            self.loaded = True
            logger.info(
                "Model loaded type=%s features=%s threshold=%s",
                self.model_type,
                len(self.feature_columns),
                self.threshold,
            )

    def ensure_loaded(self) -> None:
        if not self.loaded or self.model is None:
            raise ModelNotLoadedError("Prediction model is not loaded")

    def extract_transaction_id(self, transaction: dict[str, Any]) -> str:
        for key in ("TransactionID", "transaction_id", "transactionId"):
            if key in transaction and transaction[key] is not None:
                return str(transaction[key])
        return f"anon-{uuid.uuid4().hex[:12]}"

    def sanitize_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(transaction, dict):
            raise ValueError("Transaction must be a JSON object")
        # Never use the training target as a model input
        return {k: v for k, v in transaction.items() if k not in EXCLUDED_INPUT_KEYS}

    def _risk_category(self, probability: float) -> str:
        if probability >= 0.70:
            return "Critical"
        if probability >= 0.30:
            return "High"
        if probability >= self.threshold:
            return "Medium"
        return "Low"

    def predict(self, transaction: dict[str, Any]) -> dict[str, Any]:
        self.ensure_loaded()
        clean = self.sanitize_transaction(transaction)
        transaction_id = self.extract_transaction_id(clean)

        df = pd.DataFrame([clean])
        df = df.reindex(columns=self.feature_columns)

        for col in self.numeric_features:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(self.numeric_medians[col])

        for col, levels in zip(self.categorical_features, self.category_levels):
            df[col] = df[col].fillna("MISSING").astype(str)
            df[col] = pd.Categorical(df[col], categories=levels)

        probability = float(self.model.predict_proba(df)[0][1])
        is_fraud = probability >= self.threshold
        risk = self._risk_category(probability)

        amt = clean.get("TransactionAmt")
        try:
            transaction_amt = float(amt) if amt is not None else None
        except (TypeError, ValueError):
            transaction_amt = None

        product_cd = clean.get("ProductCD")
        if product_cd is not None:
            product_cd = str(product_cd)

        return {
            "transaction_id": transaction_id,
            "fraud_probability": round(probability, 6),
            "predicted_fraud": int(is_fraud),
            "risk_category": risk,
            "threshold": self.threshold,
            "transaction_amt": transaction_amt,
            "product_cd": product_cd,
        }

    def health_info(self) -> dict[str, Any]:
        return {
            "model_loaded": self.loaded,
            "model_type": self.model_type,
            "feature_count": len(self.feature_columns) if self.loaded else None,
            "threshold": self.threshold if self.loaded else None,
        }


predictor_service = PredictorService()


# Backward-compatible module-level accessors used by older call sites/tests
def predict_fraud(transaction: dict) -> dict:
    result = predictor_service.predict(transaction)
    return {
        "fraud_probability": result["fraud_probability"],
        "predicted_fraud": result["predicted_fraud"],
        "risk_category": result["risk_category"],
        "threshold": result["threshold"],
    }


def get_model():
    return predictor_service.model


def get_feature_columns():
    return predictor_service.feature_columns


def get_threshold():
    return predictor_service.threshold
