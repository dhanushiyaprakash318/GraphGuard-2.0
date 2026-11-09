# Microsoft Fabric integration

Workspace: **GraphGuard_Fabric_Analytics**  
Lakehouse: **GraphGuard_Lakehouse**  
Eventstream: **ES_GraphGuard_Lakehouse**

Implementation: `fabric.py`, `event_parser.py`, `fabric_consumer.py`, `fabric_sync_worker.py`

## Status values (from `/health` → `fabric`)

| status | meaning |
|--------|---------|
| `not_configured` | Required env vars missing |
| `error` | Credentials present but token acquisition failed |
| `degraded` | Token OK but SQL probe failed |
| `connected` | Token + SQL endpoint verified |

**Secrets are never returned by the API.**

## Environment variables

| Variable | Purpose |
|----------|---------|
| `FABRIC_SQL_ENDPOINT` | SQL analytics endpoint hostname |
| `FABRIC_DATABASE` | Lakehouse SQL database name |
| `FABRIC_TENANT_ID` / `FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET` | Entra app auth |
| `FABRIC_EVENTHUB_CONNECTION_STRING` | Custom endpoint (Event Hubs SDK) |
| `FABRIC_EVENTHUB_NAME` | Event hub name |
| `FABRIC_INCOMING_TABLE` | Exact incoming Lakehouse table (default `graphguard_incoming_events_stream_v5`) |
| `FABRIC_PREDICTIONS_TABLE` | Read-only prediction table name |
| `FABRIC_SYNC_ENABLED` | Background sync worker (`true`/`false`, default `true`) |
| `FABRIC_SYNC_INTERVAL_SECONDS` | Poll interval (default `30`) |
| `FABRIC_TIMEOUT_SECONDS` / `FABRIC_MAX_RETRIES` | HTTP / sync retries |

Set `FABRIC_INCOMING_TABLE` to the **exact** Fabric table name (including any spelling used when the destination was created).

## Confirmed destination failures (historical)

1. **Delta `invariants`** on legacy `graphguard_incoming_events` — Eventstream cannot write.
2. **`TypeConversionError`** — prediction-shaped bodies vs transaction schema.
3. **v2/v3** — locked to prediction columns; do not use for raw ingest.

**Live incoming table:** `graphguard_incoming_events_stream_v5` (raw IEEE-CIS columns). Leave v2/v3 untouched.

## Application flow

```
POST /predict
  1) publish raw IEEE-CIS transaction → Eventstream (CloudEvents properties)
  2) LightGBM score
  3) persist → PostgreSQL

Background worker (FABRIC_SYNC_ENABLED) every FABRIC_SYNC_INTERVAL_SECONDS:
  → read FABRIC_INCOMING_TABLE
  → parse / validate
  → score new IDs
  → upsert PostgreSQL (idempotent on transaction_id + model_version)

Manual: POST /fabric/sync-incoming (same lock + logic)
```

### Sync safety

- In-process overlap: asyncio lock on the worker tick
- Cross-replica overlap: PostgreSQL `pg_try_advisory_lock`
- Durable idempotency: `prediction_records` unique constraint (not only memory)
- Partial failures: per-event try/except; unprocessed IDs remain eligible
- Sync runs in a thread pool so HTTP requests stay responsive

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Fabric + model + DB status |
| `POST` | `/predict` | Publish raw txn + score + Postgres |
| `POST` | `/fabric/sync-incoming` | Manual sync |
| `GET` | `/fabric/sync-status` | Worker enabled / running / interval |
| `GET` | `/fabric/incoming/{id}` | Read-only incoming lookup |
| `GET` | `/fabric/predictions/{id}` | Fabric prediction table presence |

## CloudEvents application properties

| Property | Value |
|----------|-------|
| `cloudEvents:specversion` | `1.0` |
| `cloudEvents:type` | `GraphGuard_Transaction_Schema` |
| `cloudEvents:source` | `/graphguard/transactions` |
| `cloudEvents:id` | unique UUID |

Body: IEEE-CIS transaction JSON with numeric `TransactionID`. Never prediction fields.
