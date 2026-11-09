#!/usr/bin/env bash
# Print why the API container is unhealthy (safe: masks passwords).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== compose ps ==="
docker compose ps -a

echo
echo "=== api logs (last 80) ==="
docker compose logs api --tail 80 || docker logs graphguard-20-api-1 --tail 80

echo
echo "=== DATABASE_URL host inside api (password masked) ==="
docker compose exec -T api printenv DATABASE_URL 2>/dev/null \
  | sed -E 's#(://[^:/@]+:)[^@/]+#\1***/' \
  || echo "(api not running)"

echo
echo "=== / and /health from host ==="
curl -fsS http://127.0.0.1:8000/ || true
echo
curl -fsS http://127.0.0.1:8000/health 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print({k:d.get(k) for k in ('status','database','fabric')})" \
  || echo "(health unreachable)"
