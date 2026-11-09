from typing import Any

from pydantic import BaseModel, Field


class FabricHealth(BaseModel):
    status: str
    configured: bool
    sql_endpoint_set: bool = False
    eventstream_configured: bool = False
    token_ok: bool = False
    sql_ok: bool = False
    tables_found: list[str] = Field(default_factory=list)
    workspace: str | None = None
    lakehouse: str | None = None
    incoming_table: str | None = None
    predictions_table: str | None = None
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
