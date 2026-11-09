from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.fabric_consumer import process_incoming_events
from app.services.fabric_sync_lock import fabric_sync_lock

logger = get_logger(__name__)


def run_fabric_sync(
    *,
    limit: int = 50,
    source: str = "manual",
    acquire_blocking: bool = False,
) -> dict[str, Any]:
    """Run one Fabric → PostgreSQL sync under a cross-replica lock.

    Durable idempotency: prediction_records unique (transaction_id, model_version).
    Partial failures: each event is independent; failures leave others eligible.
    """
    settings = get_settings()
    started = time.perf_counter()
    logger.info(
        "Fabric sync started source=%s table=%s limit=%s",
        source,
        settings.fabric_incoming_table,
        limit,
    )

    if not settings.fabric_configured:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Fabric sync skipped source=%s reason=not_configured duration_ms=%s",
            source,
            duration_ms,
        )
        return {
            "status": "skipped",
            "reason": "fabric_not_configured",
            "source": source,
            "duration_ms": duration_ms,
            "fetched": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
        }

    db = SessionLocal()
    try:
        with fabric_sync_lock(db, blocking=acquire_blocking) as acquired:
            if not acquired:
                duration_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "Fabric sync skipped source=%s reason=lock_held duration_ms=%s",
                    source,
                    duration_ms,
                )
                return {
                    "status": "skipped",
                    "reason": "lock_held",
                    "source": source,
                    "duration_ms": duration_ms,
                    "fetched": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                }

            last_error: Exception | None = None
            result: dict[str, Any] | None = None
            attempts = max(1, settings.fabric_max_retries + 1)
            for attempt in range(attempts):
                try:
                    result = process_incoming_events(db, limit=limit)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning(
                        "Fabric sync attempt failed source=%s attempt=%s/%s error=%s",
                        source,
                        attempt + 1,
                        attempts,
                        type(exc).__name__,
                    )
                    try:
                        db.rollback()
                    except Exception:  # noqa: BLE001
                        pass
                    if attempt + 1 < attempts:
                        time.sleep(0.5 * (attempt + 1))

            duration_ms = int((time.perf_counter() - started) * 1000)
            if last_error is not None or result is None:
                logger.error(
                    "Fabric sync errors source=%s duration_ms=%s error=%s",
                    source,
                    duration_ms,
                    type(last_error).__name__ if last_error else "unknown",
                )
                return {
                    "status": "error",
                    "source": source,
                    "duration_ms": duration_ms,
                    "detail": type(last_error).__name__ if last_error else "sync_failed",
                    "fetched": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                }

            logger.info(
                "Fabric sync completed source=%s fetched=%s processed=%s "
                "skipped=%s failed=%s predictions_generated=%s duration_ms=%s",
                source,
                result.get("fetched"),
                result.get("processed"),
                result.get("skipped"),
                result.get("failed"),
                result.get("processed"),
                duration_ms,
            )
            return {
                "status": "ok",
                "source": source,
                "duration_ms": duration_ms,
                **result,
            }
    finally:
        db.close()


class FabricSyncWorker:
    """Asyncio background poller for Fabric incoming events."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._tick_lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        settings = get_settings()
        if not settings.fabric_sync_enabled:
            logger.info("Fabric sync worker not started (FABRIC_SYNC_ENABLED=false)")
            return
        if not settings.fabric_configured:
            logger.info("Fabric sync worker not started (Fabric SQL not configured)")
            return
        if self.running:
            return

        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="fabric-sync-worker")
        logger.info(
            "Fabric sync worker started interval_seconds=%s table=%s",
            settings.fabric_sync_interval_seconds,
            settings.fabric_incoming_table,
        )

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=15)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
        logger.info("Fabric sync worker stopped")

    async def _loop(self) -> None:
        settings = get_settings()
        interval = max(5, int(settings.fabric_sync_interval_seconds))
        # Short initial delay so API can finish startup and accept traffic
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=2)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            await self._safe_tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                continue

    async def _safe_tick(self) -> None:
        if self._tick_lock.locked():
            logger.info("Fabric sync tick skipped (overlap in same process)")
            return
        try:
            await asyncio.wait_for(self._tick_lock.acquire(), timeout=0.01)
        except asyncio.TimeoutError:
            logger.info("Fabric sync tick skipped (overlap in same process)")
            return
        try:
            try:
                await asyncio.to_thread(
                    run_fabric_sync,
                    limit=50,
                    source="background",
                    acquire_blocking=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Fabric sync tick crashed error=%s",
                    type(exc).__name__,
                )
        finally:
            self._tick_lock.release()


fabric_sync_worker = FabricSyncWorker()
