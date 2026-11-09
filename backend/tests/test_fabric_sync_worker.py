import asyncio
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.services.fabric_sync_worker import (
    FabricSyncWorker,
    run_fabric_sync,
)


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fabric_env(monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "example.datawarehouse.fabric.microsoft.com")
    monkeypatch.setenv("FABRIC_DATABASE", "GraphGuard_Lakehouse")
    monkeypatch.setenv("FABRIC_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("FABRIC_CLIENT_ID", "22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FABRIC_CLIENT_SECRET", "dummy-secret-value")
    get_settings.cache_clear()


def test_run_fabric_sync_skips_when_not_configured(monkeypatch):
    for key in (
        "FABRIC_SQL_ENDPOINT",
        "FABRIC_DATABASE",
        "FABRIC_TENANT_ID",
        "FABRIC_CLIENT_ID",
        "FABRIC_CLIENT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()

    result = run_fabric_sync(source="test")
    assert result["status"] == "skipped"
    assert result["reason"] == "fabric_not_configured"
    assert "duration_ms" in result


def test_run_fabric_sync_retries_then_succeeds(monkeypatch):
    _fabric_env(monkeypatch)
    monkeypatch.setenv("FABRIC_MAX_RETRIES", "2")
    get_settings.cache_clear()

    calls = {"n": 0}

    def flaky_process(db, limit=20):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return {
            "fetched": 1,
            "processed": 1,
            "skipped": 0,
            "failed": 0,
            "incoming_table": "graphguard_incoming_events_stream_v5",
            "results": [{"transaction_id": "1", "status": "processed"}],
        }

    @contextmanager
    def lock_ok(*_a, **_k):
        yield True

    with (
        patch(
            "app.services.fabric_sync_worker.process_incoming_events",
            side_effect=flaky_process,
        ),
        patch("app.services.fabric_sync_worker.fabric_sync_lock", lock_ok),
    ):
        result = run_fabric_sync(source="test")

    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert calls["n"] == 2


def test_run_fabric_sync_skips_when_lock_held(monkeypatch):
    _fabric_env(monkeypatch)

    @contextmanager
    def lock_held(*_a, **_k):
        yield False

    with patch("app.services.fabric_sync_worker.fabric_sync_lock", lock_held):
        with patch(
            "app.services.fabric_sync_worker.process_incoming_events"
        ) as process:
            result = run_fabric_sync(source="test")
            process.assert_not_called()

    assert result["status"] == "skipped"
    assert result["reason"] == "lock_held"


@pytest.mark.asyncio
async def test_worker_respects_disabled_flag(monkeypatch):
    monkeypatch.setenv("FABRIC_SYNC_ENABLED", "false")
    get_settings.cache_clear()
    worker = FabricSyncWorker()
    await worker.start()
    assert worker.running is False


@pytest.mark.asyncio
async def test_worker_start_stop_and_no_overlap(monkeypatch):
    _fabric_env(monkeypatch)
    monkeypatch.setenv("FABRIC_SYNC_ENABLED", "true")
    monkeypatch.setenv("FABRIC_SYNC_INTERVAL_SECONDS", "60")
    get_settings.cache_clear()

    calls = {"n": 0}
    in_flight = {"n": 0}
    max_in_flight = {"n": 0}

    def slow_sync(**_kwargs):
        calls["n"] += 1
        in_flight["n"] += 1
        max_in_flight["n"] = max(max_in_flight["n"], in_flight["n"])
        import time

        time.sleep(0.2)
        in_flight["n"] -= 1
        return {
            "status": "ok",
            "fetched": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "duration_ms": 1,
        }

    worker = FabricSyncWorker()
    with patch(
        "app.services.fabric_sync_worker.run_fabric_sync",
        side_effect=slow_sync,
    ):
        # Do not start the loop — exercise overlap on _safe_tick only
        t1 = asyncio.create_task(worker._safe_tick())
        await asyncio.sleep(0.05)
        t2 = asyncio.create_task(worker._safe_tick())
        await asyncio.gather(t1, t2)
        await worker.stop()

    assert calls["n"] == 1
    assert max_in_flight["n"] == 1


@pytest.mark.asyncio
async def test_worker_shutdown_stops_loop(monkeypatch):
    _fabric_env(monkeypatch)
    monkeypatch.setenv("FABRIC_SYNC_ENABLED", "true")
    monkeypatch.setenv("FABRIC_SYNC_INTERVAL_SECONDS", "30")
    get_settings.cache_clear()

    worker = FabricSyncWorker()
    with patch(
        "app.services.fabric_sync_worker.run_fabric_sync",
        return_value={"status": "ok", "fetched": 0, "processed": 0, "skipped": 0, "failed": 0},
    ):
        await worker.start()
        assert worker.running is True
        await worker.stop()
        assert worker.running is False


def test_duplicate_handling_uses_durable_predictions(
    db_session, loaded_model, sample_transaction
):
    from app.services.fabric_consumer import process_incoming_events
    from app.services.history import save_prediction
    from app.services.predictor import predictor_service

    tid = 9300001
    txn = dict(sample_transaction)
    txn["TransactionID"] = tid
    pred = predictor_service.predict(txn)
    save_prediction(db_session, pred)

    event = {
        "transaction_id": tid,
        "payload": __import__("json").dumps(txn),
    }
    with patch(
        "app.services.fabric_consumer.fabric_service.fetch_incoming_events",
        return_value=[event],
    ):
        result = process_incoming_events(db_session, limit=10)

    assert result["skipped"] == 1
    assert result["processed"] == 0
    assert result["results"][0]["status"] == "skipped_duplicate"
