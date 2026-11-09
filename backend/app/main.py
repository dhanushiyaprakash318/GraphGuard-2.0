
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any

from app.services.predictor import predict_fraud, model, feature_columns, threshold

app = FastAPI(
    title="GraphGuard 2.0 API",
    description="Fabric-powered AI fraud detection API",
    version="1.0.0"
)


class TransactionRequest(BaseModel):
    transaction: dict[str, Any]


@app.get("/")
def home():
    return {
        "message": "Welcome to GraphGuard 2.0",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model": type(model).__name__,
        "features": len(feature_columns),
        "threshold": threshold
    }


@app.post("/predict")
def predict(request: TransactionRequest):
    try:
        result = predict_fraud(request.transaction)
        return {
            "success": True,
            "prediction": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Prediction failed: {str(e)}"
        )
