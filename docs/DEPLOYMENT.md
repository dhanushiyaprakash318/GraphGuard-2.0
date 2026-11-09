# GraphGuard 2.0 — Deployment Guide

## Verified local deployment

```bash
cp .env.example .env
# Fill Fabric SQL + Event Hub values. Set FABRIC_INCOMING_TABLE to the exact Lakehouse name.
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Postgres | localhost:5432 |

Compose includes restart policies and health checks for `db`, `api`, and `web`.

### Fabric realtime checklist

1. `FABRIC_EVENTHUB_CONNECTION_STRING` + `FABRIC_EVENTHUB_NAME` set (producer).
2. `FABRIC_INCOMING_TABLE` matches the live Lakehouse destination exactly.
3. `FABRIC_SYNC_ENABLED=true` (default) — background Lakehouse → Postgres sync.
4. Confirm: `GET /fabric/sync-status` → `worker_running: true`.
5. Optional end-to-end: `./scripts/verify_fabric_auto_sync.sh`.

See [FABRIC.md](FABRIC.md) for schema rules and CloudEvents properties.

## Production checklist

1. Set strong `POSTGRES_PASSWORD` (do not use the Compose demo password in production).
2. Restrict `CORS_ORIGINS` to your real frontend origin(s).
3. Set `VITE_API_BASE_URL` to the public API HTTPS URL before building the web image.
4. Store Fabric secrets in a secret manager — never in Git.
5. Mount or inject the model artifact securely (`graphguard_prediction_bundle.joblib`).
6. Run behind HTTPS (ingress / reverse proxy / platform TLS).
7. Keep `LOG_LEVEL=INFO` (or `WARNING`); never log full raw transactions or secrets.
8. Prefer Alembic migrations in production (`alembic upgrade head`).
9. Run **one** API replica or rely on Postgres advisory locks if scaling sync workers.

## Recommended cloud target

**Azure Container Apps** (or App Service for Containers):

- One container for API
- One container for web (nginx static)
- Azure Database for PostgreSQL Flexible Server
- Secrets via Key Vault / Container Apps secrets

### High-level Azure steps (manual — billable)

1. Create a resource group.
2. Create Azure Database for PostgreSQL and a database named `graphguard`.
3. Push images to Azure Container Registry.
4. Create Container Apps environment + API/web apps.
5. Configure env vars / secrets (`DATABASE_URL`, Fabric vars, `CORS_ORIGINS`, `VITE_API_BASE_URL`).
6. Point a custom domain + TLS at the web app.
7. Verify `/health`, `/fabric/sync-status`, predict a sample txn, and UI Settings.

**Do not create paid Azure resources until explicitly approved.**

## Frontend production API URL

The web image bakes `VITE_API_BASE_URL` at build time.

```bash
VITE_API_BASE_URL=https://api.example.com docker compose build web
```

## Model artifact

The trained bundle is ~26 MB and currently tracked in Git. For production, prefer Git LFS or private blob storage. History rewrite requires explicit approval.
