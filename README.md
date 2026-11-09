# GraphGuard 2.0

AI-powered fraud detection platform built on the IEEE-CIS Fraud Detection dataset, a trained LightGBM model (438 features, threshold **0.10**), FastAPI, React, PostgreSQL, and optional Microsoft Fabric integration.

## Architecture

```text
React Dashboard  -->  FastAPI  -->  LightGBM Predictor
                         |                |
                         v                v
                    PostgreSQL      (optional) Fabric Eventstream
                         |
                         v
                  Analytics / History APIs
```

- **Offline / API scoring:** upload a transaction JSON → preprocess with the saved training config → LightGBM probability → risk category → persist to PostgreSQL → dashboard analytics.
- **Fabric:** credential-gated service layer. Without env credentials the API reports `fabric.status = not_configured` and does not claim a live Lakehouse connection.
- **Realtime Eventstream:** optional publish after prediction when `FABRIC_EVENTSTREAM_URL` is set. Not advertised as verified until credentials and an ingest endpoint are provided and tested.

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
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Postgres | localhost:5432 (`graphguard` / `graphguard`) |

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

Vite proxies `/predict`, `/health`, `/transactions`, and `/analytics` to `http://127.0.0.1:8000`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App status |
| GET | `/health` | Model, DB, Fabric health |
| POST | `/predict` | Score one transaction and persist |
| POST | `/predict/batch` | Score up to `BATCH_MAX_SIZE` (default 100) |
| GET | `/transactions` | History with search / risk filter / pagination |
| GET | `/analytics/summary` | Counts, fraud rate, risk distribution |
| GET | `/analytics/trends` | Time-bucketed fraud stats |
| GET | `/analytics/probability-distribution` | Probability histogram bins |

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
- **Settings** – read-only health and configuration (no secrets)

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
| `FABRIC_EVENTSTREAM_URL` | Optional Eventstream / custom ingest HTTPS URL |
| `FABRIC_EVENTHUB_CONNECTION_STRING` | Custom endpoint connection string (secret) |
| `FABRIC_EVENTHUB_NAME` | Custom endpoint Event hub name |
| `FABRIC_INCOMING_TABLE` | Incoming Lakehouse table (default `graphguard_incoming_events_stream_v5`) |
| `FABRIC_PREDICTIONS_TABLE` | Predictions table for read-only checks |
| `FABRIC_SYNC_ENABLED` | Background Lakehouse→Postgres sync (default `true`) |
| `FABRIC_SYNC_INTERVAL_SECONDS` | Sync poll interval (default `30`) |
| `FABRIC_TIMEOUT_SECONDS` | HTTP timeout (default 10) |
| `FABRIC_MAX_RETRIES` | Retry count (default 2) |

**Known workspace assets:** `GraphGuard_Fabric_Analytics` / `GraphGuard_Lakehouse` / `ES_GraphGuard_Lakehouse`  
**Incoming destination:** set `FABRIC_INCOMING_TABLE` to the exact Fabric table (live: stream v5, raw IEEE-CIS)  
**Gold tables probed (read-only):** `gold_fraud_summary`, `gold_product_fraud_metrics`, `gold_time_fraud_metrics`, `gold_device_fraud_metrics`  

Background sync polls the incoming table, scores new IDs with LightGBM, and upserts PostgreSQL. Manual trigger: `POST /fabric/sync-incoming`. Status: `GET /fabric/sync-status`.

Until credentials are provided in local `.env` (never commit secrets):

1. `/health` → `fabric.status = "not_configured"`
2. SQL probes and gold table discovery do not run
3. Eventstream publish is skipped (`status: skipped`)
4. Power BI remains external

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
| Docker Compose (API + web + Postgres) | Prepared in-repo; verify with `docker compose up --build` |
| Cloud (Azure / Fabric hosting) | **Not deployed** — requires your cloud subscription and Fabric permissions |
| Fabric live integration | **Blocked** on credentials listed above |

## License / dataset

IEEE-CIS Fraud Detection data and the trained model are project assets; follow the original dataset license for redistribution.
