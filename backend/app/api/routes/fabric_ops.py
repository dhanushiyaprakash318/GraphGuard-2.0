from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.services.fabric import fabric_service
from app.services.fabric_sync_worker import fabric_sync_worker, run_fabric_sync

router = APIRouter(prefix="/fabric", tags=["fabric"])
logger = get_logger(__name__)


@router.post("/sync-incoming")
def sync_incoming(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Poll FABRIC_INCOMING_TABLE, score new rows, persist to PostgreSQL.

    Idempotent per (transaction_id, model_version). Uses the same cross-replica
    lock as the background worker. Does not modify Fabric tables.
    """
    settings = get_settings()
    if not settings.fabric_configured:
        raise HTTPException(
            status_code=503,
            detail="Fabric SQL credentials are not configured",
        )
    # db dependency kept for auth/lifecycle parity; sync opens its own session
    _ = db
    try:
        result = run_fabric_sync(limit=limit, source="manual", acquire_blocking=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fabric sync-incoming failed")
        raise HTTPException(
            status_code=502,
            detail=f"Fabric sync failed: {type(exc).__name__}",
        ) from exc
    if result.get("status") == "skipped" and result.get("reason") == "lock_held":
        raise HTTPException(
            status_code=409,
            detail="Fabric sync already running on another worker",
        )
    return {"success": result.get("status") in {"ok", "skipped"}, **result}


@router.get("/sync-status")
def sync_status() -> dict:
    settings = get_settings()
    return {
        "enabled": settings.fabric_sync_enabled,
        "interval_seconds": settings.fabric_sync_interval_seconds,
        "worker_running": fabric_sync_worker.running,
        "incoming_table": settings.fabric_incoming_table,
        "fabric_configured": settings.fabric_configured,
    }


@router.get("/incoming/{transaction_id}")
def get_incoming(transaction_id: str) -> dict:
    """Lookup a single incoming event row (read-only)."""
    settings = get_settings()
    if not settings.fabric_configured:
        raise HTTPException(status_code=503, detail="Fabric not configured")
    row = fabric_service.get_incoming_by_transaction_id(transaction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Incoming event not found")
    payload = row.get("payload")
    payload_preview = None
    if isinstance(payload, str):
        payload_preview = payload[:500] + ("…" if len(payload) > 500 else "")
    return {
        "transaction_id": row.get("transaction_id"),
        "event_timestamp": str(row.get("event_timestamp")),
        "payload_preview": payload_preview,
        "payload_length": len(payload) if isinstance(payload, str) else 0,
    }


@router.get("/predictions/{transaction_id}")
def fabric_prediction_exists(transaction_id: str) -> dict:
    """Check whether realtime_fraud_predictions already has this transaction."""
    settings = get_settings()
    if not settings.fabric_configured:
        raise HTTPException(status_code=503, detail="Fabric not configured")
    exists = fabric_service.prediction_exists_in_fabric(transaction_id)
    return {"transaction_id": transaction_id, "exists": exists}
