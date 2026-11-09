# Microsoft Fabric integration notes

GraphGuard 2.0 includes a credential-gated Fabric service in `backend/app/services/fabric.py`.

## Current status

**Not configured in this environment.** `/health` reports:

```json
"fabric": {
  "status": "not_configured",
  "configured": false
}
```

No Fabric secrets are stored in the repository.

## Required configuration

| Variable | Required for | Description |
|----------|--------------|-------------|
| `FABRIC_SQL_ENDPOINT` | SQL access | Fabric warehouse / SQL analytics endpoint hostname |
| `FABRIC_DATABASE` | SQL access | Target database name |
| `FABRIC_TENANT_ID` | Auth | Microsoft Entra tenant ID |
| `FABRIC_CLIENT_ID` | Auth | App registration client ID |
| `FABRIC_CLIENT_SECRET` | Auth | App registration client secret |
| `FABRIC_EVENTSTREAM_URL` | Optional realtime publish | HTTPS ingest URL for CloudEvents |
| `FABRIC_TIMEOUT_SECONDS` | Optional | Default `10` |
| `FABRIC_MAX_RETRIES` | Optional | Default `2` |

Permissions needed on the Entra app:

- Access to the Fabric SQL endpoint / warehouse
- Read on gold analytics tables if dashboard federation is required
- Write/ingest permission on the Eventstream custom endpoint if realtime publish is enabled

## Expected assets (verify in your workspace)

- Lakehouse tables: `bronze_transactions`, `bronze_identity`, `silver_transactions`, `silver_identity`, `silver_transaction_enriched`
- Gold metrics: `gold_fraud_summary`, `gold_product_fraud_metrics`, `gold_time_fraud_metrics`, `gold_device_fraud_metrics`
- Streaming: `graphguard_incoming_events`, `incoming_transactions`, `realtime_fraud_predictions`
- Power BI semantic model + fraud analytics report (consumed outside this React app)

## Behavior

1. Without credentials → health `not_configured`; Eventstream publish returns `skipped`
2. With credentials → health attempts token acquisition against `https://database.windows.net/.default`
3. After each successful API prediction, the service may POST a CloudEvents payload to `FABRIC_EVENTSTREAM_URL` when set
4. Receiving an HTTP success from Eventstream does **not** by itself prove Lakehouse processing completed; confirm rows in Fabric separately

## What you must provide to unblock live Fabric

1. Working SQL endpoint + database name
2. Entra app credentials with SQL access
3. Eventstream ingest URL and confirmed CloudEvents schema (if realtime is required)
4. Confirmation that the listed tables exist and are queryable
