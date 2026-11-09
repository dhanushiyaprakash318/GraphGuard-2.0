from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FabricService:
    """Credential-gated Microsoft Fabric integration.

    Without env credentials this service reports ``not_configured`` and never
    invents a successful connection. SQL query helpers and Eventstream publish
    activate only when configuration is present.
    """

    def health(self) -> dict[str, Any]:
        settings = get_settings()
        configured = settings.fabric_configured
        eventstream = bool(settings.fabric_eventstream_url)

        if not configured:
            return {
                "status": "not_configured",
                "configured": False,
                "sql_endpoint_set": bool(settings.fabric_sql_endpoint),
                "eventstream_configured": eventstream,
                "detail": (
                    "Set FABRIC_SQL_ENDPOINT, FABRIC_DATABASE, FABRIC_CLIENT_ID, "
                    "FABRIC_CLIENT_SECRET, and FABRIC_TENANT_ID to enable Fabric."
                ),
            }

        # Lightweight connectivity probe: obtain an Entra token when possible.
        try:
            token = self._get_access_token()
            if token:
                return {
                    "status": "configured",
                    "configured": True,
                    "sql_endpoint_set": True,
                    "eventstream_configured": eventstream,
                    "detail": "Credentials present; token acquired",
                }
            return {
                "status": "error",
                "configured": True,
                "sql_endpoint_set": True,
                "eventstream_configured": eventstream,
                "detail": "Unable to acquire Fabric access token",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fabric health check failed: %s", type(exc).__name__)
            return {
                "status": "error",
                "configured": True,
                "sql_endpoint_set": True,
                "eventstream_configured": eventstream,
                "detail": f"Health check failed: {type(exc).__name__}",
            }

    def _get_access_token(self) -> str | None:
        settings = get_settings()
        if not settings.fabric_configured:
            return None

        url = (
            f"https://login.microsoftonline.com/{settings.fabric_tenant_id}"
            "/oauth2/v2.0/token"
        )
        data = {
            "client_id": settings.fabric_client_id,
            "client_secret": settings.fabric_client_secret,
            "scope": "https://database.windows.net/.default",
            "grant_type": "client_credentials",
        }

        last_error: Exception | None = None
        for attempt in range(settings.fabric_max_retries + 1):
            try:
                with httpx.Client(timeout=settings.fabric_timeout_seconds) as client:
                    response = client.post(url, data=data)
                    response.raise_for_status()
                    return response.json().get("access_token")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.25 * (attempt + 1))
        if last_error:
            raise last_error
        return None

    def publish_prediction_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Publish a CloudEvent-style prediction to Fabric Eventstream if configured.

        Returns a status dict. Does not claim success unless HTTP accepts the event.
        """
        settings = get_settings()
        if not settings.fabric_eventstream_url:
            return {
                "status": "skipped",
                "detail": "FABRIC_EVENTSTREAM_URL not configured",
            }

        event = {
            "specversion": "1.0",
            "type": "com.graphguard.fraud.prediction",
            "source": "graphguard-api",
            "id": str(payload.get("transaction_id")),
            "time": payload.get("created_at"),
            "datacontenttype": "application/json",
            "data": {
                "transaction_id": payload.get("transaction_id"),
                "fraud_probability": payload.get("fraud_probability"),
                "predicted_fraud": payload.get("predicted_fraud"),
                "risk_category": payload.get("risk_category"),
                "model_version": payload.get("model_version"),
            },
        }

        last_error: Exception | None = None
        for attempt in range(settings.fabric_max_retries + 1):
            try:
                with httpx.Client(timeout=settings.fabric_timeout_seconds) as client:
                    response = client.post(
                        settings.fabric_eventstream_url,
                        json=event,
                        headers={"Content-Type": "application/cloudevents+json"},
                    )
                    if response.status_code < 300:
                        return {"status": "published", "http_status": response.status_code}
                    last_error = RuntimeError(f"HTTP {response.status_code}")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.25 * (attempt + 1))

        logger.warning(
            "Eventstream publish failed for tx=%s: %s",
            payload.get("transaction_id"),
            type(last_error).__name__ if last_error else "unknown",
        )
        return {
            "status": "error",
            "detail": type(last_error).__name__ if last_error else "publish_failed",
        }


fabric_service = FabricService()
