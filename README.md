# GraphGuard 2.0

AI-powered fraud detection platform on the IEEE-CIS dataset: **LightGBM** (438 features, threshold **0.10**), **FastAPI**, **React**, **Supabase PostgreSQL** (operational scores / dashboard), and **Microsoft Fabric** (Eventstream ingest + Lakehouse).

## Architecture

```text
React Dashboard ──► FastAPI
                      │
                      ├─1► Fabric Eventstream (GraphGuard_API / Event Hubs)
                      │         └─► Lakehouse incoming (stream v5, raw IEEE-CIS)
                      │
                      ├─2► LightGBM score (fraud %, risk band)
                      │
                      └─3► Supabase PostgreSQL (prediction_records)
                                └─► Overview / Analytics / Transactions

Background every ~30s (optional path):
  Lakehouse incoming ──► LightGBM ──► Supabase (new IDs only, idempotent)
```

| Component | Role |
|-----------|------|
| **Supabase Postgres** | Operational source of truth — scores, history, dashboard APIs |
| **Microsoft Fabric** | Raw event ingest (Eventstream → Lakehouse); historical / Power BI analytics |
| **LightGBM** | Fraud inference (438 features, threshold 0.10) |
| **FastAPI** | Predict, publish, sync worker, analytics APIs |
| **React** | UI |

**Important:** Lakehouse incoming stores **raw** transactions. Scored results live in **Supabase** (`prediction_records`), not in the incoming table.

- `/predict` order: publish raw txn to Fabric → score → persist to Supabase (immediate).
- Sync worker: Lakehouse → score → Supabase for IDs not already stored (~30s).
- **Not implemented:** writing scores back to Fabric `realtime_fraud_predictions`.

## Repository layout

```text
backend/           FastAPI app, model bundle, tests
frontend/          React + Vite + Tailwind dashboard
docker-compose.yml
.env.example
docs/FABRIC.md
docs/DEPLOYMENT.md
scripts/           Fabric + Supabase verify helpers
```

## Prerequisites

- Docker + Docker Compose
- Or locally: Python **3.11**, Node.js 20+
- Model: `backend/app/models/graphguard_prediction_bundle.joblib` (~26 MB)
- Supabase project (recommended for shared multi-user history)
- Fabric credentials (for realtime Eventstream; optional for local score-only demos)

> **sklearn:** bundle needs scikit-learn **1.6.1**. Prefer Docker (Python 3.11); host 3.14 is unsupported for local venv.

## Quick start

```bash
cp .env.example .env
# 1) Set DATABASE_URL to Supabase Session pooler (see below)
# 2) Fill Fabric vars if you want Eventstream + sync
docker compose up --build -d api web
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Database | Supabase via `DATABASE_URL` |

Local Docker Postgres only (not shared across machines):

```bash
docker compose --profile local-db up --build -d
```

### Supabase `DATABASE_URL` (shared history)

1. Supabase → **Project Settings → Database → Connection string → URI**
2. Use **Session pooler** (`:5432`) — not Transaction (`:6543`), prefer over Direct `db.*` inside Docker
3. In `.env`:

```bash
DATABASE_URL="postgresql+psycopg2://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require"
```

Helpers: `./scripts/fix_and_restart_supabase.sh` · `./scripts/verify_supabase_db.sh`  
Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

**Never commit `.env`.** Share the Session-pooler URI with teammates out of band so everyone sees the same Overview.

### Smoke check

```bash
curl -s http://localhost:8000/health | jq '{status, database, fabric: .fabric | {status, incoming_table, eventstream_configured}}'
curl -s http://localhost:8000/fabric/sync-status | jq .
curl -s -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d "{\"transaction\": $(jq -c '. + {TransactionID: 2987001}' backend/sample_transaction.json)}"
curl -s http://localhost:8000/analytics/summary | jq
```

Expected parity for transaction **2987000** (tolerance `1e-5`):

- `fraud_probability` ≈ `0.020889`
- `predicted_fraud` = `0`
- `risk_category` = `Low`
- `threshold` = `0.10`

## Where scores and reports live

| Need | Where |
|------|--------|
| Fraud % / risk for one txn | Fraud Detection UI, `/predict` response, Supabase `prediction_records` |
| Ops dashboard | **Overview**, **Analytics**, **Transactions** |
| Aggregates API | `GET /analytics/summary`, `/analytics/trends`, … |
| Raw events | Fabric Lakehouse incoming table |
| Fabric Gold / Power BI | External Fabric analytics (not this UI) |

UI upload: **Fraud Detection** → upload IEEE-CIS JSON (e.g. `backend/sample_transaction.json` + unique `TransactionID`) → **Predict**.

## Local development (without Compose)

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./graphguard.db   # or your Supabase URI
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
| POST | `/predict` | Publish to Eventstream → score → Supabase |
| POST | `/predict/batch` | Score up to `BATCH_MAX_SIZE` (default 100) |
| GET | `/transactions` | History (search / risk / pagination) |
| GET | `/analytics/summary` | Counts, fraud rate, risk distribution |
| GET | `/analytics/trends` | Time-bucketed fraud stats |
| GET | `/analytics/probability-distribution` | Probability histogram |
| POST | `/fabric/sync-incoming` | Manual Lakehouse → score → Supabase |
| GET | `/fabric/sync-status` | Sync worker status |
| GET | `/fabric/incoming/{id}` | Read-only Lakehouse lookup |
| GET | `/fabric/predictions/{id}` | Fabric prediction-table presence |

### Predict request / response

```json
{
  "transaction": {
    "TransactionID": 2987000,
    "TransactionAmt": 68.5,
    "ProductCD": "W"
  }
}
```

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

Missing features are filled from training medians / `"MISSING"`. Risk bands: Low `< 0.10`, Medium `[0.10, 0.30)`, High `[0.30, 0.70)`, Critical `≥ 0.70`.

## Frontend pages

- **Overview** — summary, trends, recent scored transactions  
- **Fraud Detection** — JSON upload + prediction result  
- **Analytics** — charts from Supabase history  
- **Transactions** — searchable scored history  
- **Settings** — model / DB / Fabric / sync status (no secrets)

## Microsoft Fabric

Set in `.env` (never commit secrets). Full guide: [docs/FABRIC.md](docs/FABRIC.md).

| Variable | Purpose |
|----------|---------|
| `FABRIC_SQL_ENDPOINT` / `FABRIC_DATABASE` | Lakehouse SQL |
| `FABRIC_TENANT_ID` / `FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET` | Entra app |
| `FABRIC_EVENTHUB_CONNECTION_STRING` / `FABRIC_EVENTHUB_NAME` | Active producer |
| `FABRIC_INCOMING_TABLE` | Exact incoming table (live: `raphguard_incoming_events_stream_v5`) |
| `FABRIC_PREDICTIONS_TABLE` | Read-only checks (`realtime_fraud_predictions`) |
| `FABRIC_SYNC_ENABLED` | Background sync (default `true`) |
| `FABRIC_SYNC_INTERVAL_SECONDS` | Poll interval (default `30`) |

**Assets:** workspace `GraphGuard_Fabric_Analytics`, lakehouse `GraphGuard_Lakehouse`, eventstream `ES_GraphGuard_Lakehouse`, source `GraphGuard_API`.

Without Fabric env: `/health` → `fabric.status = not_configured`; publish skipped; scoring + Supabase still work.

Verify: `scripts/verify_fabric_auto_sync.sh`

## Testing

```bash
docker build -t graphguard-api:test ./backend
docker run --rm \
  -e DATABASE_URL=sqlite:// \
  -e LOG_LEVEL=WARNING \
  -e CORS_ORIGINS=http://testserver \
  graphguard-api:test pytest -q
```

```bash
cd frontend && npm test && npm run build
```

## Configuration

See [`.env.example`](.env.example). `.env` is gitignored.

## Deployment status

| Target | Status |
|--------|--------|
| Docker Compose (API + web) | Supported |
| Supabase shared Postgres | Supported — set `DATABASE_URL` (Session pooler) |
| Fabric ingest + auto-sync | Verified when Fabric + Event Hub + incoming table are set |
| Hosted multi-user API + auth | **Not done** (GraphGuard 3.0) |
| Cloud Azure deploy | **Not deployed** — [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |

## Model artifact policy

The trained bundle (~26 MB) is tracked in Git. Prefer Git LFS / private registry later. Do not commit extra `.joblib` files or secrets.

## License / dataset

IEEE-CIS Fraud Detection data and the trained model are project assets; follow the original dataset license for redistribution.
