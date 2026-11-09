#!/usr/bin/env bash
# Controlled auto-sync verification (run on the host with Docker up).
# Does not print secrets.
#
# Proves:
# 1) worker is running
# 2) event reaches Lakehouse (FABRIC_INCOMING_TABLE)
# 3) after deleting the Postgres row, background sync recreates the prediction
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== rebuild api =="
docker compose up -d --build api

echo "== wait for health =="
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/gg_health.json 2>/dev/null; then
    break
  fi
  sleep 2
done
jq '{status, fabric: .fabric | {status, incoming_table, eventstream_configured}}' /tmp/gg_health.json
jq -e '.fabric.incoming_table | test("stream_v5")' /tmp/gg_health.json >/dev/null

echo "== sync status =="
curl -fsS http://127.0.0.1:8000/fabric/sync-status | tee /tmp/gg_sync_status.json | jq .
jq -e '.worker_running == true and .enabled == true' /tmp/gg_sync_status.json >/dev/null

TID="${1:-$(date +%s)}"
echo "== publish unique transaction ${TID} =="
curl -fsS http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d "$(python3 - <<PY
import json, pathlib
t = json.loads(pathlib.Path("backend/sample_transaction.json").read_text())
t["TransactionID"] = int("${TID}")
for k in ("fraud_probability","prediction","risk_level","predicted_fraud","risk_category","processed_at","isFraud"):
    t.pop(k, None)
print(json.dumps({"transaction": t}))
PY
)" | jq '{success, transaction_id, prediction}'

echo "== wait for Lakehouse row (up to ~3 min) =="
IN_LAKE=0
for i in $(seq 1 36); do
  code=$(curl -sS -o /tmp/gg_incoming.json -w '%{http_code}' \
    "http://127.0.0.1:8000/fabric/incoming/${TID}" || true)
  if [[ "${code}" == "200" ]]; then
    IN_LAKE=1
    jq '{transaction_id, payload_length}' /tmp/gg_incoming.json
    break
  fi
  sleep 5
done

if [[ "${IN_LAKE}" -ne 1 ]]; then
  echo "BLOCKED: ${TID} never appeared in Lakehouse incoming table."
  echo "Auto-sync worker is running, but Eventstream→Lakehouse lag/failure blocked the test."
  docker logs --tail 40 graphguard-20-api-1 | grep -iE "Fabric sync|${TID}|published" || true
  exit 2
fi

echo "== delete Postgres row so background sync must recreate it =="
docker compose exec -T db psql -U graphguard -d graphguard -c \
  "DELETE FROM prediction_records WHERE transaction_id = '${TID}';" >/dev/null

echo "== wait for background sync to restore prediction (up to ~90s) =="
FOUND=0
for i in $(seq 1 30); do
  COUNT=$(curl -fsS "http://127.0.0.1:8000/transactions?search=${TID}" | jq '.total')
  if [[ "${COUNT}" -ge 1 ]]; then
    FOUND=1
    break
  fi
  sleep 3
done

curl -fsS "http://127.0.0.1:8000/transactions?search=${TID}" | jq .
docker logs --tail 100 graphguard-20-api-1 | grep -iE "Fabric sync|${TID}|published|prediction generated" | tail -40 || true

if [[ "${FOUND}" -ne 1 ]]; then
  echo "FAIL: Lakehouse had ${TID}, but auto-sync did not restore Postgres prediction"
  exit 1
fi
echo "PASS: auto-sync restored prediction for ${TID}"
