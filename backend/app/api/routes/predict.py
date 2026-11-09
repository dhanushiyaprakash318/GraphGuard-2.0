from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.predict import (
    BatchPredictRequest,
    BatchPredictResponse,
    BatchPredictResultItem,
    PredictionDetail,
    PredictRequest,
    PredictResponse,
)
from app.services.fabric import fabric_service
from app.services.history import save_prediction
from app.services.predictor import ModelNotLoadedError, predictor_service

router = APIRouter()
logger = get_logger(__name__)


def _to_detail(result: dict) -> PredictionDetail:
    return PredictionDetail(
        fraud_probability=result["fraud_probability"],
        predicted_fraud=result["predicted_fraud"],
        risk_category=result["risk_category"],
        threshold=result["threshold"],
    )


@router.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    settings = get_settings()
    try:
        result = predictor_service.predict(request.transaction)
    except ModelNotLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Prediction failed for request")
        raise HTTPException(
            status_code=400, detail=f"Prediction failed: {type(exc).__name__}"
        ) from exc

    try:
        save_prediction(db, result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to persist prediction: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Prediction succeeded but persistence failed"
        ) from exc

    fabric_service.publish_prediction_event(
        {
            **result,
            "model_version": settings.model_version,
        }
    )

    logger.info(
        "Predicted transaction_id=%s risk=%s fraud=%s",
        result["transaction_id"],
        result["risk_category"],
        result["predicted_fraud"],
    )

    return PredictResponse(
        success=True,
        transaction_id=result["transaction_id"],
        prediction=_to_detail(result),
    )


@router.post("/predict/batch", response_model=BatchPredictResponse)
def predict_batch(
    request: BatchPredictRequest, db: Session = Depends(get_db)
) -> BatchPredictResponse:
    settings = get_settings()
    if len(request.transactions) > settings.batch_max_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch size {len(request.transactions)} exceeds limit "
                f"{settings.batch_max_size}"
            ),
        )

    results: list[BatchPredictResultItem] = []
    succeeded = 0
    failed = 0

    for item in request.transactions:
        try:
            result = predictor_service.predict(item)
            save_prediction(db, result)
            fabric_service.publish_prediction_event(
                {**result, "model_version": settings.model_version}
            )
            results.append(
                BatchPredictResultItem(
                    success=True,
                    transaction_id=result["transaction_id"],
                    prediction=_to_detail(result),
                )
            )
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            results.append(
                BatchPredictResultItem(
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    return BatchPredictResponse(
        success=failed == 0,
        total=len(request.transactions),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
