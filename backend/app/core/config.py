from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "graphguard_prediction_bundle.joblib"
)

DEFAULT_CORS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:3000,http://127.0.0.1:3000"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GraphGuard 2.0"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    model_version: str = "graphguard-lgbm-v1"
    model_path: str = str(DEFAULT_MODEL_PATH)
    batch_max_size: int = 100
    max_request_body_bytes: int = 2_097_152

    # Comma-separated origins (string avoids JSON env parsing issues)
    cors_origins: str = DEFAULT_CORS

    database_url: str = "sqlite:///./graphguard.db"

    fabric_sql_endpoint: str = ""
    fabric_database: str = ""
    fabric_client_id: str = ""
    fabric_client_secret: str = ""
    fabric_tenant_id: str = ""
    fabric_eventstream_url: str = ""
    fabric_timeout_seconds: int = 10
    fabric_max_retries: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def fabric_configured(self) -> bool:
        has_sql = bool(self.fabric_sql_endpoint and self.fabric_database)
        has_auth = bool(
            self.fabric_client_id
            and self.fabric_client_secret
            and self.fabric_tenant_id
        )
        return has_sql and has_auth


@lru_cache
def get_settings() -> Settings:
    return Settings()
