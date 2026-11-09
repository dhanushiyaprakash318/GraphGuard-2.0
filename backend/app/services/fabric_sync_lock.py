from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)

# Stable 64-bit-ish key for pg_try_advisory_lock (app-wide Fabric sync)
FABRIC_SYNC_ADVISORY_LOCK_KEY = 872_014_401


@contextmanager
def fabric_sync_lock(db: Session, *, blocking: bool = False) -> Iterator[bool]:
    """Cross-replica sync lock.

    PostgreSQL: session-level advisory lock (survives across API workers/replicas
    sharing the same database). SQLite: no-op acquire (True) — overlap within a
    process is handled by the worker's asyncio lock; durable idempotency still
    comes from prediction_records unique constraint.
    """
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"
    acquired = False

    try:
        if dialect == "postgresql":
            fn = "pg_advisory_lock" if blocking else "pg_try_advisory_lock"
            acquired = bool(
                db.execute(
                    text(f"SELECT {fn}(:key)"),
                    {"key": FABRIC_SYNC_ADVISORY_LOCK_KEY},
                ).scalar()
            )
            if not acquired:
                logger.info(
                    "Fabric sync lock not acquired (another worker holds it)"
                )
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass
        else:
            acquired = True

        yield acquired
    finally:
        if dialect == "postgresql" and acquired:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": FABRIC_SYNC_ADVISORY_LOCK_KEY},
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Fabric sync lock release failed error=%s",
                    type(exc).__name__,
                )
                try:
                    db.rollback()
                except Exception:  # noqa: BLE001
                    pass
