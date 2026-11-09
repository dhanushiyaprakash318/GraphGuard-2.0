# GraphGuard 2.0

AI-powered fraud detection platform built on the IEEE-CIS Fraud Detection dataset, a trained LightGBM model (438 features, threshold **0.10**), FastAPI, React, PostgreSQL, and optional Microsoft Fabric integration.

## Architecture

```text
React Dashboard --> FastAPI --> LightGBM --> PostgreSQL --> Analytics / History
                     |
                     | 1) publish raw IEEE-CIS txn (CloudEvents)
                     v
              Fabric Eventstream (GraphGuard_API)
                     |
                     v
              Lakehouse incoming table (stream v5)
                     |
                     v
              Background sync (30s) --> LightGBM --> PostgreSQL
```

- **API scoring:** upload transaction JSON → LightGBM (438 features) → risk category → PostgreSQL → dashboard.
- **Realtime Fabric:** `/predict` publishes the **raw** transaction to Eventstream **before** scoring; Lakehouse destination receives IEEE-CIS columns; a background worker polls the incoming table and upserts new scores into PostgreSQL (idempotent).
- **Without Fabric credentials:** `/health` reports `fabric.status = not_configured`; Eventstream publish is skipped; API scoring still works.
- **Not implemented:** writing prediction rows back to `realtime_fraud_predictions` (Postgres is the scoring store).

## Repository layout

```text
backend/          FastAPI app, model bundle, tests
frontend/         React + Vite + Tailwind dashboard
docker-compose.yml
.env.example
```

## Prerequisites

- Docker + Docker Compose (recommended for full stack)
- Or locally: Python **3.11**, Node.js 20+, PostgreSQL 16
- Model artifact: `backend/app/models/graphguard_prediction_bundle.joblib` (~26 MB)

> **sklearn note:** the bundle was serialized with scikit-learn **1.6.1**. Runtime dependencies are pinned to that version. Host Python 3.14 is not supported for local venv installs; use Docker (Python 3.11) or install 3.11 locally.

## Quick start (Docker Compose)

```bash
cp .env.example .env
# Shared multi-user history: set DATABASE_URL to your Supabase Postgres URI (see docs/DEPLOYMENT.md)
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Postgres | Supabase via `DATABASE_URL`, or `docker compose --profile local-db` |

Smoke check:

```bash
curl -s http://localhost:8000/health | jq
curl -s -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d "{\"transaction\": $(jq -c '. + {TransactionID: 2987000}' backend/sample_transaction.json)}"
```

Expected parity for transaction **2987000** (tolerance `1e-5`):

- `fraud_probability` ≈ `0.020889`
- `predicted_fraud` = `0`
- `risk_category` = `Low`
- `threshold` = `0.10`

## Local development (without Compose)

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./graphguard.db
export CORS_ORIGINS=http://localhost:5173
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env   # leave VITE_API_BASE_URL empty to use Vite proxy
npm install
npm run dev
```

Vite proxies `/predict`, `/health`, `/transactions`, `/analytics`, and `/fabric` to `http://127.0.0.1:8000`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App status |
| GET | `/health` | Model, DB, Fabric health |
| POST | `/predict` | Publish raw txn to Eventstream, score, persist |
| POST | `/predict/batch` | Score up to `BATCH_MAX_SIZE` (default 100) |
| GET | `/transactions` | History with search / risk filter / pagination |
| GET | `/analytics/summary` | Counts, fraud rate, risk distribution |
| GET | `/analytics/trends` | Time-bucketed fraud stats |
| GET | `/analytics/probability-distribution` | Probability histogram bins |
| POST | `/fabric/sync-incoming` | Manual Lakehouse → score → Postgres sync |
| GET | `/fabric/sync-status` | Background sync worker status |
| GET | `/fabric/incoming/{id}` | Read-only Lakehouse incoming lookup |
| GET | `/fabric/predictions/{id}` | Read-only Fabric prediction-table presence |

### Predict request

```json
{
  "transaction": {
    "TransactionID": 2987000,
    "TransactionAmt": 68.5,
    "ProductCD": "W"
  }
}
```

Missing model features (for example identity columns) are filled using the saved training medians / `"MISSING"` categorical handling. The target column `isFraud` is ignored if present.

### Predict response

```json
{
  "success": true,
  "transaction_id": "2987000",
  "prediction": {
    "fraud_probability": 0.020889,
    "predicted_fraud": 0,
    "risk_category": "Low",
    "threshold": 0.1
  }
}
```

Risk bands: Low `< 0.10`, Medium `[0.10, 0.30)`, High `[0.30, 0.70)`, Critical `≥ 0.70`.

## Frontend pages

- **Overview** – live summary, trends, recent transactions, API/model status
- **Fraud Detection** – JSON upload, feature inspection, prediction result
- **Analytics** – distribution / risk / trend / probability charts
- **Transactions** – searchable, filterable, paginated history
- **Settings** – read-only health, Fabric tables, and sync worker status (no secrets)

Hardcoded IEEE dataset demo values are not used as live metrics.

## Testing

### Backend

```bash
docker build -t graphguard-api:test ./backend
docker run --rm \
  -e DATABASE_URL=sqlite:// \
  -e LOG_LEVEL=WARNING \
  -e CORS_ORIGINS=http://testserver \
  graphguard-api:test pytest -q
```

Covers model load, parity for Tx `2987000`, health, predict/batch, persistence, analytics, and validation errors.

### Frontend

```bash
cd frontend
npm test
npm run build
```

## Microsoft Fabric (optional)

Set these in `.env` (never commit real secrets):

| Variable | Purpose |
|----------|---------|
| `FABRIC_SQL_ENDPOINT` | Fabric / warehouse SQL endpoint host |
| `FABRIC_DATABASE` | Database / lakehouse SQL database name |
| `FABRIC_CLIENT_ID` | Entra app client ID |
| `FABRIC_CLIENT_SECRET` | Entra app client secret |
| `FABRIC_TENANT_ID` | Entra tenant ID |
| `FABRIC_EVENTHUB_CONNECTION_STRING` | Event Hubs custom endpoint (active producer) |
| `FABRIC_EVENTHUB_NAME` | Event hub name from the Custom endpoint |
| `FABRIC_EVENTSTREAM_URL` | Optional HTTPS ingest (unused when Event Hub is set) |
| `FABRIC_INCOMING_TABLE` | Exact Lakehouse incoming table name (must match Fabric) |
| `FABRIC_PREDICTIONS_TABLE` | Predictions table for read-only checks |
| `FABRIC_SYNC_ENABLED` | Background Lakehouse→Postgres sync (default `true`) |
| `FABRIC_SYNC_INTERVAL_SECONDS` | Sync poll interval (default `30`) |
| `FABRIC_TIMEOUT_SECONDS` | HTTP timeout (default 10) |
| `FABRIC_MAX_RETRIES` | Retry count (default 2) |

**Known workspace assets:** `GraphGuard_Fabric_Analytics` / `GraphGuard_Lakehouse` / `ES_GraphGuard_Lakehouse`  
**Producer source:** Event Hubs custom endpoint (`FABRIC_EVENTHUB_*`), UI name `GraphGuard_API`  
**Incoming table:** set `FABRIC_INCOMING_TABLE` to the **exact** Lakehouse name (verified live table uses stream v5 with raw IEEE-CIS columns; match spelling exactly)  
**Gold tables:** read-only discovery only — never modified  

Background sync polls the incoming table every `FABRIC_SYNC_INTERVAL_SECONDS`, scores new IDs, and upserts PostgreSQL. Manual: `POST /fabric/sync-incoming`. Status: `GET /fabric/sync-status`. Verify script: `scripts/verify_fabric_auto_sync.sh`.

Without credentials in local `.env` (never commit secrets):

1. `/health` → `fabric.status = "not_configured"`
2. SQL probes do not run
3. Eventstream publish is skipped (`status: skipped`)
4. Local `/predict` + Postgres still work

See [docs/FABRIC.md](docs/FABRIC.md) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Model artifact policy

The trained bundle is currently tracked in Git (~26 MB) for continuity with the existing repo history.

Recommended next step (requires maintainer approval):

1. Move the artifact to Git LFS or a private model registry
2. Document download/restore in CI
3. Optionally rewrite history to remove the blob (**force-push**; not done automatically)

Do not commit additional `.joblib` copies. Do not upload secrets or `.env` files.

## Configuration

See [`.env.example`](.env.example) for all supported variables. `.env` is gitignored.

## Deployment status

| Target | Status |
|--------|--------|
| Docker Compose (API + web + Postgres) | Supported — `docker compose up --build` |
| Cloud (Azure hosting) | **Not deployed** — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Fabric realtime ingest + auto-sync | **Verified** when `.env` Fabric credentials + Event Hub + incoming table are set |

## License / dataset

IEEE-CIS Fraud Detection data and the trained model are project assets; follow the original dataset license for redistribution.
