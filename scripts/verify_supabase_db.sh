#!/usr/bin/env bash
# Verify DATABASE_URL (Supabase or other) from the API container /health.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example and set DATABASE_URL"
  exit 1
fi

# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
source .env
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is empty in .env"
  exit 1
fi

host="$(python3 - <<'PY'
import os, re
from urllib.parse import urlparse
u = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://", 1)
u = u.replace("postgres://", "postgresql://", 1)
p = urlparse(u)
print(p.hostname or "")
PY
)"
echo "DATABASE_URL host: ${host}"
if [[ "$host" == *"supabase"* ]]; then
  echo "Looks like Supabase — good for shared history."
else
  echo "Note: host is not supabase.co (local/other Postgres is OK)."
fi

echo "Starting api (and web) against DATABASE_URL…"
docker compose up -d --build api
sleep 5
curl -fsS http://127.0.0.1:8000/health | python3 -c "
import json,sys
h=json.load(sys.stdin)
db=h.get('database') or {}
print('health.status=', h.get('status'))
print('database=', db)
sys.exit(0 if db.get('status')=='ok' else 1)
"
echo "OK — API connected to database."
