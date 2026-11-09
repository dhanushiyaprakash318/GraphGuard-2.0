from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import PredictionRecord
from app.services.event_parser import EventParseError, parse_incoming_event
from app.services.fabric import fabric_service
from app.services.history import save_prediction
from app.services.predictor import predictor_service

logger = get_logger(__name__)


def process_incoming_events(
    db: Session,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Poll FABRIC_INCOMING_TABLE, score new events, persist to PostgreSQL.

    Idempotent: skips transaction_ids already stored for the current model version.
    Does not modify Fabric Lakehouse tables (including Gold analytics).
    """
    settings = get_settings()
    events = fabric_service.fetch_incoming_events(limit=limit)
    logger.info(
        "Fabric sync events discovered count=%s table=%s",
        len(events),
        settings.fabric_incoming_table,
    )

    processed = 0
    skipped = 0
    failed = 0
    results: list[dict[str, Any]] = []

    for event in events:
        try:
            parsed = parse_incoming_event(event)
        except EventParseError as exc:
            failed += 1
            results.append(
                {
                    "transaction_id": str(event.get("transaction_id") or ""),
                    "status": "error",
                    "detail": f"parse:{exc}",
                }
            )
            continue

        tid = parsed["transaction_id"]
        transaction = parsed["transaction"]

        existing = db.scalar(
            select(PredictionRecord).where(
                PredictionRecord.transaction_id == str(tid),
                PredictionRecord.model_version == settings.model_version,
            )
        )
        if existing:
            skipped += 1
            logger.info("Fabric sync event skipped transaction_id=%s reason=duplicate", tid)
            results.append(
                {
                    "transaction_id": str(tid),
                    "status": "skipped_duplicate",
                }
            )
            continue

        try:
            prediction = predictor_service.predict(transaction)
            save_prediction(db, prediction)
            processed += 1
            fabric_pred = False
            try:
                fabric_pred = fabric_service.prediction_exists_in_fabric(tid)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Fabric prediction lookup failed transaction_id=%s error=%s",
                    tid,
                    type(exc).__name__,
                )
            results.append(
                {
                    "transaction_id": str(tid),
                    "status": "processed",
                    "fraud_probability": prediction["fraud_probability"],
                    "risk_category": prediction["risk_category"],
                    "fabric_prediction_row": fabric_pred,
                    "cloudevents_id": parsed.get("cloudevents_id"),
                }
            )
            logger.info(
                "Fabric sync prediction generated transaction_id=%s "
                "risk=%s processed_count=%s",
                tid,
                prediction["risk_category"],
                processed,
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning(
                "Fabric sync event error transaction_id=%s error=%s",
                tid,
                type(exc).__name__,
            )
            results.append(
                {
                    "transaction_id": str(tid),
                    "status": "error",
                    "detail": type(exc).__name__,
                }
            )

    logger.info(
        "Fabric sync batch summary fetched=%s processed=%s skipped=%s failed=%s",
        len(events),
        processed,
        skipped,
        failed,
    )
    return {
        "fetched": len(events),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "incoming_table": settings.fabric_incoming_table,
        "results": results,
        "notes": (
            "PostgreSQL persistence is authoritative for API scoring. "
            "A new Eventstream destination table does not by itself fix "
            "payload TypeConversionError — body must remain IEEE-CIS JSON "
            "with CloudEvents application properties. "
            "Legacy identical probabilities (~0.0030197) in "
            "realtime_fraud_predictions are unreliable vs this LightGBM bundle."
        ),
    }
