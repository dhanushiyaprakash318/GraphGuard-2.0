from __future__ import annotations

import json
import re
import struct
import time
import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EXPECTED_GOLD_TABLES = (
    "gold_fraud_summary",
    "gold_product_fraud_metrics",
    "gold_time_fraud_metrics",
    "gold_device_fraud_metrics",
)

SQL_COPT_SS_ACCESS_TOKEN = 1256

# Matches the previously verified GraphGuard Eventstream producer
CLOUDEVENTS_TYPE = "GraphGuard_Transaction_Schema"
CLOUDEVENTS_SOURCE = "/graphguard/transactions"

# Never land these on the transaction Eventstream (prediction / label leakage)
FORBIDDEN_INGEST_KEYS = frozenset(
    {
        "isFraud",
        "fraud_probability",
        "predicted_fraud",
        "prediction",
        "risk_category",
        "risk_level",
        "threshold",
        "model_version",
        "processed_at",
    }
)

_SAFE_SQL_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_transaction_ingest_payload(transaction: dict[str, Any]) -> dict[str, Any]:
    """Build IEEE-CIS JSON body for Eventstream (no prediction fields)."""
    if not isinstance(transaction, dict):
        raise ValueError("transaction must be a JSON object")

    payload = {k: v for k, v in transaction.items() if k not in FORBIDDEN_INGEST_KEYS}

    raw_id = (
        payload.get("TransactionID")
        or payload.get("transaction_id")
        or payload.get("transactionId")
    )
    try:
        transaction_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("TransactionID must be numeric for Fabric incoming table") from exc

    payload["TransactionID"] = transaction_id
    # Drop alias keys so Lakehouse schema stays TransactionID-centric
    payload.pop("transaction_id", None)
    payload.pop("transactionId", None)
    return payload

# Candidate Lakehouse column names used by Eventstream destinations
_PAYLOAD_COLUMNS = ("payload", "Payload", "body", "Body", "data", "Data")
_TID_COLUMNS = ("transaction_id", "TransactionID", "transactionId")
_TS_COLUMNS = (
    "event_timestamp",
    "EventProcessedUtcTime",
    "EventEnqueuedUtcTime",
    "event_enqueued_utc_time",
)


def quote_table_name(name: str) -> str:
    """Validate and quote a SQL table identifier (dbo.<name>)."""
    if not name or not _SAFE_SQL_IDENT.match(name):
        raise ValueError(f"Unsafe Fabric table name: {name!r}")
    return f"dbo.[{name}]"


class FabricService:
    """Credential-gated Microsoft Fabric integration.

    Eventstream custom endpoint expects raw IEEE-CIS transaction JSON with
    CloudEvents application properties (not prediction rows).

    Incoming Lakehouse table is configurable via FABRIC_INCOMING_TABLE because
    the legacy ``graphguard_incoming_events`` Delta table has unsupported
    writer features (``invariants``).
    """

    def health(self) -> dict[str, Any]:
        settings = get_settings()
        eventstream = settings.fabric_eventstream_configured
        base = {
            "configured": False,
            "sql_endpoint_set": bool(settings.fabric_sql_endpoint),
            "eventstream_configured": eventstream,
            "token_ok": False,
            "sql_ok": False,
            "tables_found": [],
            "workspace": settings.fabric_workspace or None,
            "lakehouse": settings.fabric_lakehouse or None,
            "incoming_table": settings.fabric_incoming_table or None,
            "predictions_table": settings.fabric_predictions_table or None,
        }

        if not settings.fabric_configured:
            return {
                **base,
                "status": "not_configured",
                "detail": (
                    "Set FABRIC_SQL_ENDPOINT, FABRIC_DATABASE, FABRIC_CLIENT_ID, "
                    "FABRIC_TENANT_ID, and the Entra application credential in .env "
                    "to enable Fabric."
                ),
            }

        base["configured"] = True

        try:
            token = self._get_access_token()
            if not token:
                return {
                    **base,
                    "status": "error",
                    "detail": "Unable to acquire Fabric access token",
                }
            base["token_ok"] = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fabric token acquisition failed: %s", type(exc).__name__)
            return {
                **base,
                "status": "error",
                "detail": f"Token acquisition failed: {type(exc).__name__}",
            }

        try:
            sql_result = self.check_sql_connection(token=token)
            base["sql_ok"] = bool(sql_result.get("ok"))
            base["tables_found"] = sql_result.get("tables_found", [])
            if not base["sql_ok"]:
                return {
                    **base,
                    "status": "degraded",
                    "detail": sql_result.get("detail") or "SQL endpoint unreachable",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fabric SQL health check failed: %s", type(exc).__name__)
            return {
                **base,
                "status": "degraded",
                "detail": f"SQL check failed: {type(exc).__name__}",
            }

        return {
            **base,
            "status": "connected",
            "detail": "Token and SQL endpoint verified",
        }

    def _get_access_token(self) -> str | None:
        settings = get_settings()
        if not settings.fabric_configured:
            return None

        url = (
            f"https://login.microsoftonline.com/{settings.fabric_tenant_id}"
            "/oauth2/v2.0/token"
        )
        data = {
            "client_id": settings.fabric_client_id,
            "client_secret": settings.fabric_client_secret,
            "scope": "https://database.windows.net/.default",
            "grant_type": "client_credentials",
        }

        last_error: Exception | None = None
        for attempt in range(settings.fabric_max_retries + 1):
            try:
                with httpx.Client(timeout=settings.fabric_timeout_seconds) as client:
                    response = client.post(url, data=data)
                    if response.status_code >= 400:
                        raise RuntimeError(f"token_http_{response.status_code}")
                    token = response.json().get("access_token")
                    if not token:
                        raise RuntimeError("token_missing_in_response")
                    return token
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.25 * (attempt + 1))
        if last_error:
            raise last_error
        return None

    def _build_token_struct(self, token: str) -> bytes:
        token_bytes = token.encode("UTF-16-LE")
        return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    def _sql_connect(self, token: str):
        import pyodbc

        settings = get_settings()
        server = settings.fabric_sql_endpoint.strip()
        if "," not in server and ":" not in server:
            server = f"{server},1433"
        conn_str = (
            "Driver={ODBC Driver 18 for SQL Server};"
            f"Server={server};"
            f"Database={settings.fabric_database};"
            "Encrypt=yes;"
            "TrustServerCertificate=no;"
        )
        return pyodbc.connect(
            conn_str,
            attrs_before={SQL_COPT_SS_ACCESS_TOKEN: self._build_token_struct(token)},
            timeout=settings.fabric_timeout_seconds,
        )

    def check_sql_connection(self, token: str | None = None) -> dict[str, Any]:
        settings = get_settings()
        if not settings.fabric_sql_endpoint or not settings.fabric_database:
            return {"ok": False, "detail": "SQL endpoint or database not set", "tables_found": []}

        access_token = token or self._get_access_token()
        if not access_token:
            return {"ok": False, "detail": "No access token", "tables_found": []}

        try:
            import pyodbc  # noqa: F401
        except ImportError:
            return {
                "ok": False,
                "detail": "pyodbc not installed in runtime image",
                "tables_found": [],
            }

        try:
            conn = self._sql_connect(access_token)
        except Exception as exc:  # noqa: BLE001
            err_text = str(exc)
            logger.warning("Fabric SQL connect failed: %s", type(exc).__name__)
            if "18456" in err_text or "authentication failed" in err_text.lower():
                detail = (
                    "SQL authentication failed (18456). Add the Entra app "
                    f"({settings.fabric_client_id}) to Fabric workspace "
                    f"'{settings.fabric_workspace}' with at least Contributor access."
                )
            else:
                detail = f"SQL connect failed: {type(exc).__name__}"
            return {"ok": False, "detail": detail, "tables_found": []}

        tables_found: list[str] = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            # Probe gold tables + configured incoming / predictions tables (read-only)
            watch = list(EXPECTED_GOLD_TABLES) + [
                settings.fabric_incoming_table,
                settings.fabric_predictions_table,
                "graphguard_incoming_events",  # legacy (do not write)
            ]
            watch = [t for t in watch if t and _SAFE_SQL_IDENT.match(t)]
            placeholders = ",".join("?" for _ in watch)
            cursor.execute(
                f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                  AND TABLE_NAME IN ({placeholders})
                ORDER BY TABLE_NAME
                """,
                watch,
            )
            tables_found = [str(row[0]) for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fabric SQL probe query failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "detail": f"SQL probe failed: {type(exc).__name__}",
                "tables_found": [],
            }
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

        return {
            "ok": True,
            "detail": "SQL endpoint reachable",
            "tables_found": tables_found,
        }

    def _list_columns(self, cursor, table_name: str) -> list[str]:
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            table_name,
        )
        return [str(row[0]) for row in cursor.fetchall()]

    def _pick_column(self, columns: list[str], candidates: tuple[str, ...]) -> str | None:
        lower_map = {c.lower(): c for c in columns}
        for name in candidates:
            if name in columns:
                return name
            if name.lower() in lower_map:
                return lower_map[name.lower()]
        return None

    def _normalize_incoming_row(
        self,
        columns: list[str],
        values: tuple[Any, ...],
        *,
        payload_col: str | None,
        tid_col: str | None,
        ts_col: str | None,
    ) -> dict[str, Any]:
        row = {columns[i]: values[i] for i in range(len(columns))}
        payload = row.get(payload_col) if payload_col else None
        # If Eventstream lands flat IEEE-CIS columns, serialize the feature-ish row
        if payload is None:
            # Keep full row for the parser (it strips metadata)
            payload = json.dumps(row, default=str)
        elif not isinstance(payload, str):
            payload = json.dumps(payload, default=str)

        return {
            "transaction_id": row.get(tid_col) if tid_col else None,
            "event_timestamp": row.get(ts_col) if ts_col else None,
            "payload": payload,
            "raw_row": row,
        }

    def fetch_incoming_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Read-only fetch of recent rows from FABRIC_INCOMING_TABLE."""
        settings = get_settings()
        if not settings.fabric_configured:
            return []
        token = self._get_access_token()
        if not token:
            return []

        table = settings.fabric_incoming_table
        quoted = quote_table_name(table)
        limit = min(max(int(limit), 1), 200)

        conn = self._sql_connect(token)
        try:
            cursor = conn.cursor()
            columns = self._list_columns(cursor, table)
            if not columns:
                logger.warning("Incoming table %s not found or has no columns", table)
                return []

            payload_col = self._pick_column(columns, _PAYLOAD_COLUMNS)
            tid_col = self._pick_column(columns, _TID_COLUMNS)
            ts_col = self._pick_column(columns, _TS_COLUMNS)

            order_col = ts_col or tid_col or columns[0]
            # SELECT * so we adapt when Eventstream invents new column layouts
            select_list = ", ".join(f"[{c}]" for c in columns)
            cursor.execute(
                f"""
                SELECT TOP ({limit}) {select_list}
                FROM {quoted}
                ORDER BY [{order_col}] DESC
                """
            )
            rows: list[dict[str, Any]] = []
            for values in cursor.fetchall():
                rows.append(
                    self._normalize_incoming_row(
                        columns,
                        tuple(values),
                        payload_col=payload_col,
                        tid_col=tid_col,
                        ts_col=ts_col,
                    )
                )
            return rows
        finally:
            conn.close()

    def get_incoming_by_transaction_id(self, transaction_id: int | str) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.fabric_configured:
            return None
        token = self._get_access_token()
        if not token:
            return None
        try:
            tid = int(str(transaction_id))
        except (TypeError, ValueError):
            return None

        table = settings.fabric_incoming_table
        quoted = quote_table_name(table)
        conn = self._sql_connect(token)
        try:
            cursor = conn.cursor()
            columns = self._list_columns(cursor, table)
            if not columns:
                return None
            payload_col = self._pick_column(columns, _PAYLOAD_COLUMNS)
            tid_col = self._pick_column(columns, _TID_COLUMNS)
            ts_col = self._pick_column(columns, _TS_COLUMNS)
            if not tid_col:
                # Fall back to scanning recent rows and parsing payloads
                for event in self.fetch_incoming_events(limit=100):
                    parsed_tid = event.get("transaction_id")
                    if parsed_tid is not None and int(parsed_tid) == tid:
                        return event
                    raw_payload = event.get("payload")
                    if isinstance(raw_payload, str) and str(tid) in raw_payload:
                        return event
                return None

            order_col = ts_col or tid_col
            select_list = ", ".join(f"[{c}]" for c in columns)
            cursor.execute(
                f"""
                SELECT TOP 1 {select_list}
                FROM {quoted}
                WHERE [{tid_col}] = ?
                ORDER BY [{order_col}] DESC
                """,
                tid,
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._normalize_incoming_row(
                columns,
                tuple(row),
                payload_col=payload_col,
                tid_col=tid_col,
                ts_col=ts_col,
            )
        finally:
            conn.close()

    def prediction_exists_in_fabric(self, transaction_id: int | str) -> bool:
        settings = get_settings()
        if not settings.fabric_configured:
            return False
        token = self._get_access_token()
        if not token:
            return False
        try:
            tid = int(str(transaction_id))
        except (TypeError, ValueError):
            return False
        table = quote_table_name(settings.fabric_predictions_table)
        conn = self._sql_connect(token)
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {table} WHERE transaction_id = ?",
                tid,
            )
            return int(cursor.fetchone()[0] or 0) > 0
        finally:
            conn.close()

    def publish_transaction_event(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Publish a raw IEEE-CIS transaction to the Eventstream custom endpoint.

        CloudEvents metadata goes in EventData.properties. Body is transaction
        features only — never prediction output. Predictions stay in PostgreSQL
        (and optionally FABRIC_PREDICTIONS_TABLE via a separate Fabric path).
        """
        settings = get_settings()
        if not settings.fabric_eventhub_connection_string:
            return {
                "status": "skipped",
                "detail": "FABRIC_EVENTHUB_CONNECTION_STRING not configured",
            }

        try:
            payload = build_transaction_ingest_payload(transaction)
        except ValueError as exc:
            return {"status": "error", "detail": str(exc)}

        transaction_id = int(payload["TransactionID"])
        event_id = str(uuid.uuid4())
        body = json.dumps(payload, default=str)

        last_error: Exception | None = None
        for attempt in range(settings.fabric_max_retries + 1):
            try:
                from azure.eventhub import EventData, EventHubProducerClient

                kwargs: dict[str, Any] = {
                    "conn_str": settings.fabric_eventhub_connection_string,
                }
                if settings.fabric_eventhub_name:
                    kwargs["eventhub_name"] = settings.fabric_eventhub_name

                producer = EventHubProducerClient.from_connection_string(**kwargs)
                try:
                    batch = producer.create_batch()
                    event = EventData(body)
                    event.content_type = "application/json"
                    event.properties = {
                        "cloudEvents:specversion": "1.0",
                        "cloudEvents:type": CLOUDEVENTS_TYPE,
                        "cloudEvents:source": CLOUDEVENTS_SOURCE,
                        "cloudEvents:id": event_id,
                    }
                    batch.add(event)
                    producer.send_batch(batch)
                finally:
                    producer.close()

                logger.info(
                    "Eventstream transaction published transaction_id=%s event_id=%s",
                    transaction_id,
                    event_id,
                )
                return {
                    "status": "published",
                    "transport": "eventhub",
                    "transaction_id": transaction_id,
                    "event_id": event_id,
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.25 * (attempt + 1))

        logger.warning(
            "Eventstream transaction publish failed transaction_id=%s error=%s",
            transaction_id,
            type(last_error).__name__ if last_error else "unknown",
        )
        return {
            "status": "error",
            "transaction_id": transaction_id,
            "detail": type(last_error).__name__ if last_error else "publish_failed",
        }

    def publish_prediction_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Never publish prediction rows to the transaction Eventstream.

        If a nested raw ``transaction`` is provided, forward that instead.
        Otherwise skip — keeps ingest schema separate from scoring output.
        """
        transaction = payload.get("transaction")
        if isinstance(transaction, dict):
            return self.publish_transaction_event(transaction)
        logger.info(
            "Skipping prediction-shaped Fabric publish for transaction_id=%s "
            "(Eventstream expects %s; prediction rows caused TypeConversionError)",
            payload.get("transaction_id"),
            CLOUDEVENTS_TYPE,
        )
        return {
            "status": "skipped",
            "detail": (
                "Eventstream custom endpoint expects raw transactions "
                f"({CLOUDEVENTS_TYPE}), not prediction rows"
            ),
        }


fabric_service = FabricService()
