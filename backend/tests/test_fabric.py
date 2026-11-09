import json
from unittest.mock import MagicMock, patch

import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.fabric import (
    FabricService,
    build_transaction_ingest_payload,
    fabric_service,
)


def test_health_not_configured_when_fabric_env_cleared(client: TestClient, monkeypatch):
    """Isolate from Compose/.env Fabric credentials injected into the container."""
    for key in (
        "FABRIC_SQL_ENDPOINT",
        "FABRIC_DATABASE",
        "FABRIC_TENANT_ID",
        "FABRIC_CLIENT_ID",
        "FABRIC_CLIENT_SECRET",
        "FABRIC_EVENTHUB_CONNECTION_STRING",
        "FABRIC_EVENTHUB_NAME",
        "FABRIC_EVENTSTREAM_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()

    response = client.get("/health")
    assert response.status_code == 200
    fabric = response.json()["fabric"]
    assert fabric["status"] == "not_configured"
    assert fabric["configured"] is False
    assert "FABRIC_SQL_ENDPOINT" in (fabric.get("detail") or "")
    body = response.text.lower()
    assert "bearer " not in body
    assert "eyj" not in body
    assert "dummy-secret-value" not in body
    get_settings.cache_clear()


def test_fabric_health_invalid_token_is_safe_error(monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "example.datawarehouse.fabric.microsoft.com")
    monkeypatch.setenv("FABRIC_DATABASE", "GraphGuard_Lakehouse")
    monkeypatch.setenv("FABRIC_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "dummy-secret-value")
    get_settings.cache_clear()

    service = FabricService()
    with respx.mock:
        respx.post(
            "https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111/oauth2/v2.0/token"
        ).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
        result = service.health()

    assert result["configured"] is True
    assert result["status"] == "error"
    assert result["token_ok"] is False
    assert "secret" not in (result.get("detail") or "").lower()
    get_settings.cache_clear()


def test_fabric_health_connected_when_token_and_sql_ok(monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "example.datawarehouse.fabric.microsoft.com")
    monkeypatch.setenv("FABRIC_DATABASE", "GraphGuard_Lakehouse")
    monkeypatch.setenv("FABRIC_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "dummy-secret-value")
    get_settings.cache_clear()

    service = FabricService()
    with respx.mock:
        respx.post(
            "https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111/oauth2/v2.0/token"
        ).mock(return_value=httpx.Response(200, json={"access_token": "fake-token"}))
        with patch.object(
            service,
            "check_sql_connection",
            return_value={
                "ok": True,
                "detail": "SQL endpoint reachable",
                "tables_found": ["gold_fraud_summary"],
            },
        ):
            result = service.health()

    assert result["status"] == "connected"
    assert result["token_ok"] is True
    assert result["sql_ok"] is True
    assert "gold_fraud_summary" in result["tables_found"]
    get_settings.cache_clear()


def test_build_transaction_ingest_strips_prediction_fields():
    payload = build_transaction_ingest_payload(
        {
            "TransactionID": 9200002,
            "TransactionAmt": 68.5,
            "ProductCD": "W",
            "card1": 13926,
            "addr1": 315.0,
            "fraud_probability": 0.020889,
            "prediction": "Legitimate",
            "risk_level": "Legitimate",
            "predicted_fraud": 0,
            "risk_category": "Low",
            "processed_at": "2026-11-09T12:00:00Z",
            "isFraud": 0,
        }
    )
    assert payload["TransactionID"] == 9200002
    assert payload["TransactionAmt"] == 68.5
    assert payload["ProductCD"] == "W"
    assert payload["card1"] == 13926
    assert payload["addr1"] == 315.0
    for forbidden in (
        "fraud_probability",
        "prediction",
        "risk_level",
        "predicted_fraud",
        "risk_category",
        "processed_at",
        "isFraud",
    ):
        assert forbidden not in payload


def test_prediction_shaped_publish_is_skipped(monkeypatch):
    monkeypatch.setenv(
        "FABRIC_EVENTHUB_CONNECTION_STRING",
        "Endpoint=sb://example/;SharedAccessKeyName=key;SharedAccessKey=secret;EntityPath=hub",
    )
    get_settings.cache_clear()
    result = fabric_service.publish_prediction_event(
        {
            "transaction_id": "2987000",
            "fraud_probability": 0.020889,
            "predicted_fraud": 0,
            "risk_category": "Low",
            "prediction": "Legitimate",
            "risk_level": "Legitimate",
            "model_version": "graphguard-lgbm-v1",
        }
    )
    assert result["status"] == "skipped"
    assert "GraphGuard_Transaction_Schema" in (result.get("detail") or "")
    get_settings.cache_clear()


def test_eventstream_publish_skipped_without_credentials(monkeypatch):
    monkeypatch.delenv("FABRIC_EVENTSTREAM_URL", raising=False)
    monkeypatch.delenv("FABRIC_EVENTHUB_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("FABRIC_EVENTHUB_NAME", raising=False)
    get_settings.cache_clear()
    result = fabric_service.publish_transaction_event(
        {"TransactionID": 1, "TransactionAmt": 10.0}
    )
    assert result["status"] == "skipped"
    get_settings.cache_clear()


def test_eventhub_outgoing_body_is_raw_transaction_not_prediction(monkeypatch):
    """Outgoing EventData must be IEEE-CIS features + CloudEvents properties."""
    monkeypatch.setenv(
        "FABRIC_EVENTHUB_CONNECTION_STRING",
        "Endpoint=sb://example/;SharedAccessKeyName=key;SharedAccessKey=secret;EntityPath=hub",
    )
    monkeypatch.setenv("FABRIC_EVENTHUB_NAME", "hub")
    get_settings.cache_clear()

    captured: dict = {}

    class FakeBatch:
        def add(self, event):
            captured["event"] = event

    class FakeProducer:
        def create_batch(self):
            return FakeBatch()

        def send_batch(self, _batch):
            return None

        def close(self):
            return None

        @staticmethod
        def from_connection_string(**_kwargs):
            return FakeProducer()

    class FakeEventData:
        def __init__(self, body):
            self.body_raw = body
            self.content_type = None
            self.properties = {}

    with patch.dict(
        "sys.modules",
        {
            "azure": MagicMock(),
            "azure.eventhub": MagicMock(
                EventHubProducerClient=FakeProducer,
                EventData=FakeEventData,
            ),
        },
    ):
        import azure.eventhub as eh

        eh.EventHubProducerClient = FakeProducer
        eh.EventData = FakeEventData
        result = fabric_service.publish_transaction_event(
            {
                "TransactionID": 2987000,
                "TransactionAmt": 68.5,
                "ProductCD": "W",
                "card1": 13926,
                "addr1": 315.0,
                "dist1": 19.0,
                "fraud_probability": 0.9,
                "prediction": "Fraud",
                "risk_level": "Critical",
            }
        )

    assert result["status"] == "published"
    assert result["transport"] == "eventhub"
    event = captured["event"]
    assert event.properties["cloudEvents:type"] == "GraphGuard_Transaction_Schema"
    assert event.properties["cloudEvents:source"] == "/graphguard/transactions"
    assert event.properties["cloudEvents:specversion"] == "1.0"
    assert "cloudEvents:id" in event.properties

    body = json.loads(event.body_raw)
    assert body["TransactionID"] == 2987000
    assert body["TransactionAmt"] == 68.5
    assert body["ProductCD"] == "W"
    assert body["card1"] == 13926
    assert body["addr1"] == 315.0
    assert body["dist1"] == 19.0
    assert "fraud_probability" not in body
    assert "prediction" not in body
    assert "risk_level" not in body
    get_settings.cache_clear()


def test_predict_publishes_before_scoring(client: TestClient, sample_transaction, monkeypatch):
    order: list[str] = []

    def fake_publish(txn):
        order.append("publish")
        return {"status": "published", "transaction_id": txn.get("TransactionID")}

    def fake_predict(txn):
        order.append("predict")
        return {
            "transaction_id": str(txn.get("TransactionID")),
            "fraud_probability": 0.020889,
            "predicted_fraud": 0,
            "risk_category": "Low",
            "threshold": 0.1,
            "transaction_amt": 68.5,
            "product_cd": "W",
        }

    monkeypatch.setattr(
        "app.api.routes.predict.fabric_service.publish_transaction_event",
        fake_publish,
    )
    monkeypatch.setattr(
        "app.api.routes.predict.predictor_service.predict",
        fake_predict,
    )

    response = client.post(
        "/predict",
        json={"transaction": {**sample_transaction, "TransactionID": 9200099}},
    )
    assert response.status_code == 200
    assert order == ["publish", "predict"]


def test_sql_probe_handles_missing_pyodbc(monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "example.datawarehouse.fabric.microsoft.com")
    monkeypatch.setenv("FABRIC_DATABASE", "GraphGuard_Lakehouse")
    monkeypatch.setenv("FABRIC_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "dummy-secret-value")
    get_settings.cache_clear()

    service = FabricService()
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pyodbc":
            raise ImportError("no pyodbc")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        result = service.check_sql_connection(token="fake")

    assert result["ok"] is False
    assert "pyodbc" in result["detail"]
    get_settings.cache_clear()
