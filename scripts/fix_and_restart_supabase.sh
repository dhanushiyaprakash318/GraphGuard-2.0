#!/usr/bin/env bash
# Fix Supabase connectivity, then rebuild/restart API against the working URL.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing psycopg2-binary if needed"
python3 -m pip install --user -q psycopg2-binary 2>/dev/null \
  || pip3 install --user -q psycopg2-binary 2>/dev/null \
  || true

# Prefer project venv if present
PY=python3
if [[ -x backend/.venv/bin/python ]]; then
  backend/.venv/bin/pip install -q psycopg2-binary
  PY=backend/.venv/bin/python
elif [[ -x /tmp/gg-pg-venv/bin/python ]]; then
  PY=/tmp/gg-pg-venv/bin/python
fi

echo "==> Probing Supabase (direct + session poolers)"
"$PY" scripts/fix_supabase_connection.py

echo "==> Rebuilding API without cache (pick up DB URL + code)"
docker compose build --no-cache api

echo "==> Restarting api + web"
docker compose up -d --force-recreate api web

echo "==> Waiting for API"
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/gg_health.json 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "==> Health database field"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/gg_health.json")
if not p.exists():
    raise SystemExit("API health not reachable — check: docker compose logs api --tail 80")
h = json.loads(p.read_text())
print("status:", h.get("status"))
print("database:", h.get("database"))
db = h.get("database") or {}
raise SystemExit(0 if db.get("status") == "ok" else 1)
PY
