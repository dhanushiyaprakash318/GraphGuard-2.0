from typing import Any

from pydantic import BaseModel


class FabricHealth(BaseModel):
    status: str
    configured: bool
    sql_endpoint_set: bool = False
    eventstream_configured: bool = False
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    backend: str
    model_loaded: bool
    model_type: str | None = None
    feature_count: int | None = None
    threshold: float | None = None
    model_version: str
    app_version: str
    database: dict[str, Any]
    fabric: FabricHealth


class RootResponse(BaseModel):
    message: str
    status: str
    version: str
    docs: str = "/docs"
