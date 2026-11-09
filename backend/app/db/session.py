from collections.abc import Generator
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Base
from app.db.url import normalize_database_url

logger = get_logger(__name__)

_settings = get_settings()
_database_url = normalize_database_url(_settings.database_url)
_connect_args: dict = {}
if _database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
elif _database_url.startswith("postgresql"):
    # Avoid hanging forever when Supabase/DNS is unreachable from Docker
    _connect_args = {"connect_timeout": 10}

engine = create_engine(
    _database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(*, retries: int = 5, delay_seconds: float = 2.0) -> None:
    """Create tables. Retries transient network failures (common with Supabase)."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables initialized")
            return
        except OperationalError as exc:
            last_exc = exc
            logger.warning(
                "Database init attempt %s/%s failed: %s",
                attempt,
                retries,
                type(exc).__name__,
            )
            if attempt < retries:
                time.sleep(delay_seconds)
    assert last_exc is not None
    raise last_exc


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "connected"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return {"status": "error", "detail": type(exc).__name__}
