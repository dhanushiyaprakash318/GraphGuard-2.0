# GraphGuard 2.0 — Deployment Guide

## Verified local deployment

```bash
cp .env.example .env
# edit Fabric values in .env when available
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Postgres | localhost:5432 |

Compose includes restart policies and health checks for `db`, `api`, and `web`.

## Production checklist

1. Set strong `POSTGRES_PASSWORD` (do not use the Compose demo password in production).
2. Restrict `CORS_ORIGINS` to your real frontend origin(s).
3. Set `VITE_API_BASE_URL` to the public API HTTPS URL before building the web image.
4. Store Fabric secrets in a secret manager / Compose secrets / platform secret store — never in Git.
5. Mount or inject the model artifact securely (`graphguard_prediction_bundle.joblib`).
6. Run behind HTTPS (ingress / reverse proxy / platform TLS).
7. Keep `LOG_LEVEL=INFO` (or `WARNING`); never log full raw transactions or secrets.
8. Apply DB migrations (`alembic upgrade head`) or rely on startup `create_all` for first boot, then prefer Alembic in production.

## Recommended cloud target

**Azure Container Apps** (or App Service for Containers) is the best fit for this Compose layout:

- One container for API
- One container for web (nginx static)
- Azure Database for PostgreSQL Flexible Server
- Secrets via Key Vault / Container Apps secrets
- Optional VNet for Fabric private endpoints later

### High-level Azure steps (manual — billable)

1. Create a resource group.
2. Create Azure Database for PostgreSQL and a database named `graphguard`.
3. Push images to Azure Container Registry.
4. Create Container Apps environment + API/web apps.
5. Configure env vars / secrets (`DATABASE_URL`, Fabric vars, `CORS_ORIGINS`, `VITE_API_BASE_URL`).
6. Point a custom domain + TLS at the web app.
7. Verify `/health`, predict Tx `2987000`, and UI Settings Fabric status.

**Do not create paid Azure resources until explicitly approved.**

## Frontend production API URL

The web image bakes `VITE_API_BASE_URL` at build time.

```bash
VITE_API_BASE_URL=https://api.example.com docker compose build web
```

Do not ship a production UI that still points at `http://localhost:8000` unless browser and API are on the same developer machine.

## Model artifact

The trained bundle is ~26 MB and currently tracked in Git. For production, prefer:

- Git LFS, or
- Private artifact/blob storage mounted at deploy time

History rewrite to remove the blob requires explicit approval (force-push risk).
