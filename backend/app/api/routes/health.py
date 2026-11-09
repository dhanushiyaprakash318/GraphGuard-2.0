from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_db_connection
from app.schemas.health import FabricHealth, HealthResponse, RootResponse
from app.services.fabric import fabric_service
from app.services.predictor import predictor_service

router = APIRouter()


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    settings = get_settings()
    return RootResponse(
        message=f"Welcome to {settings.app_name}",
        status="running",
        version=settings.app_version,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    model_info = predictor_service.health_info()
    fabric = fabric_service.health()
    db_status = check_db_connection()

    overall = "healthy"
    if not model_info["model_loaded"]:
        overall = "degraded"
    if db_status.get("status") != "ok":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        backend="ok",
        model_loaded=bool(model_info["model_loaded"]),
        model_type=model_info.get("model_type"),
        feature_count=model_info.get("feature_count"),
        threshold=model_info.get("threshold"),
        model_version=settings.model_version,
        app_version=settings.app_version,
        database=db_status,
        fabric=FabricHealth(**fabric),
    )
