# Microsoft Fabric integration

Workspace: **GraphGuard_Fabric_Analytics**  
Lakehouse: **GraphGuard_Lakehouse**  
Eventstream: **ES_GraphGuard_Lakehouse**  
Producer source (UI): **GraphGuard_API** (Event Hubs–compatible custom endpoint)

Implementation: `fabric.py`, `event_parser.py`, `fabric_consumer.py`, `fabric_sync_worker.py`, `fabric_sync_lock.py`

## Status values (from `/health` → `fabric`)

| status | meaning |
|--------|---------|
| `not_configured` | Required env vars missing |
| `error` | Credentials present but token acquisition failed |
| `degraded` | Token OK but SQL probe failed |
| `connected` | Token + SQL endpoint verified |

Additional safe fields: `token_ok`, `sql_ok`, `eventstream_configured`, `incoming_table`, `predictions_table`, `tables_found`, `workspace`, `lakehouse`.

**Secrets are never returned by the API.**

## Environment variables

| Variable | Purpose |
|----------|---------|
| `FABRIC_SQL_ENDPOINT` | SQL analytics endpoint hostname |
| `FABRIC_DATABASE` | Lakehouse SQL database name |
| `FABRIC_TENANT_ID` / `FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET` | Entra app auth |
| `FABRIC_EVENTHUB_CONNECTION_STRING` | Custom endpoint (Event Hubs SDK) — **active producer** |
| `FABRIC_EVENTHUB_NAME` | Event hub name |
| `FABRIC_EVENTSTREAM_URL` | Optional HTTPS ingest URL (unused when Event Hub is set) |
| `FABRIC_INCOMING_TABLE` | Exact incoming Lakehouse table name |
| `FABRIC_PREDICTIONS_TABLE` | Read-only prediction table (`realtime_fraud_predictions`) |
| `FABRIC_SYNC_ENABLED` | Background sync worker (`true`/`false`, default `true`) |
| `FABRIC_SYNC_INTERVAL_SECONDS` | Poll interval (default `30`) |
| `FABRIC_TIMEOUT_SECONDS` / `FABRIC_MAX_RETRIES` | HTTP / sync retries |

Set `FABRIC_INCOMING_TABLE` to the **exact** Fabric table name (including any spelling used when the destination was created). Example live name used in verification: `raphguard_incoming_events_stream_v5`. Code/docs defaults use `graphguard_incoming_events_stream_v5` — **override in `.env` to match Fabric**.

## Historical destination failures (do not reuse)

1. **Delta `invariants`** on legacy `graphguard_incoming_events` — Eventstream cannot write.
2. **`TypeConversionError`** — prediction-shaped bodies vs transaction schema.
3. **v2 / v3** — locked to prediction columns (`fraud_probability`, `prediction`, `risk_level`); not for raw ingest.

Leave legacy / v2 / v3 / Gold tables untouched. Do not delete them from the app.

## Application flow (verified)

```
POST /predict
  1) publish raw IEEE-CIS transaction → Eventstream (CloudEvents app properties)
  2) LightGBM 438-feature score
  3) persist prediction → PostgreSQL

Background worker (FABRIC_SYNC_ENABLED) every FABRIC_SYNC_INTERVAL_SECONDS:
  → read FABRIC_INCOMING_TABLE
  → parse / validate
  → score new IDs only
  → upsert PostgreSQL (idempotent on transaction_id + model_version)

Manual: POST /fabric/sync-incoming (same lock + logic)
Status: GET /fabric/sync-status
```

**Not implemented:** API writeback to `realtime_fraud_predictions`. That table is read-only from the app (presence checks only). Postgres is the scoring store for the UI.

### Sync safety

- In-process overlap: asyncio lock on the worker tick
- Cross-replica overlap: PostgreSQL `pg_try_advisory_lock`
- Durable idempotency: `prediction_records` unique constraint
- Partial failures: per-event try/except; other IDs remain eligible
- Sync runs via `asyncio.to_thread` so HTTP stays responsive

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

Body: IEEE-CIS transaction JSON with numeric `TransactionID`. Never include `fraud_probability`, `prediction`, `risk_level`, or other prediction fields.

## Verification

```bash
docker compose up -d --build api
curl -sS http://127.0.0.1:8000/health | jq '.fabric'
curl -sS http://127.0.0.1:8000/fabric/sync-status | jq .
./scripts/verify_fabric_auto_sync.sh
```

UI checks: **Settings** (Fabric connected, incoming table, sync worker running), **Fraud Detection** (score a txn), **Transactions** (row appears after API score and/or auto-sync).
