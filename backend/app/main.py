from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.session import init_db
from app.services.fabric_sync_worker import fabric_sync_worker
from app.services.predictor import predictor_service

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    try:
        predictor_service.load(settings.model_path)
    except Exception:
        logger.exception("Failed to load prediction model at startup")
        raise
    try:
        init_db()
    except Exception:
        logger.exception("Failed to initialize database")
        raise
    await fabric_sync_worker.start()
    try:
        yield
    finally:
        await fabric_sync_worker.stop()
        logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="AI-powered fraud detection API for GraphGuard 2.0",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_request_body_bytes:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large"},
        )
    return await call_next(request)


app.include_router(api_router)
