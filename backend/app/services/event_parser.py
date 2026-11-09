from __future__ import annotations

import json
from typing import Any

# Keys that must never enter the LightGBM feature matrix
EXCLUDED_KEYS = {
    "isFraud",
    "fraud_probability",
    "predicted_fraud",
    "risk_category",
    "threshold",
    "model_version",
}

# CloudEvents / transport metadata (not model features)
METADATA_KEYS = {
    "cloudEvents:specversion",
    "cloudEvents:type",
    "cloudEvents:source",
    "cloudEvents:id",
    "cloudEvents:time",
    "cloudevents:specversion",
    "cloudevents:type",
    "cloudevents:source",
    "cloudevents:id",
    "specversion",
    "type",
    "source",
    "id",
    "time",
    "datacontenttype",
    "dataschema",
    "subject",
    "EventProcessedUtcTime",
    "PartitionId",
    "EventEnqueuedUtcTime",
    "event_timestamp",
    "event_id",
}

# Nested object keys that may wrap the IEEE-CIS transaction
NESTED_DATA_KEYS = (
    "data",
    "Data",
    "payload",
    "Payload",
    "body",
    "Body",
    "transaction",
    "Transaction",
    "properties",
    "Properties",
)


class EventParseError(ValueError):
    """Raised when an Eventstream / Lakehouse row cannot become a transaction."""


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text[0] not in "{[":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _strip_metadata(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in obj.items()
        if k not in EXCLUDED_KEYS and k not in METADATA_KEYS
    }


def extract_transaction_dict(raw: Any) -> dict[str, Any]:
    """Normalize Lakehouse / Eventstream payload into IEEE-CIS transaction fields.

    Accepts:
    - raw transaction JSON object
    - JSON string of the above
    - CloudEvents envelope with ``data`` (object or JSON string)
    - Lakehouse row dict with ``payload`` / ``Body`` / flattened columns
    """
    data = _maybe_json(raw)

    if isinstance(data, list):
        if len(data) == 1:
            data = data[0]
        else:
            raise EventParseError("payload is a list; expected a single transaction object")

    if not isinstance(data, dict):
        raise EventParseError("payload must be a JSON object")

    # Prefer nested transaction/data wrappers when present
    for key in NESTED_DATA_KEYS:
        if key not in data:
            continue
        nested = _maybe_json(data[key])
        if isinstance(nested, dict) and (
            "TransactionID" in nested
            or "TransactionAmt" in nested
            or "transaction_id" in nested
        ):
            data = nested
            break
        # CloudEvents data that is itself the feature map (no TransactionID yet)
        if isinstance(nested, dict) and key.lower() in {"data", "payload", "body"}:
            # Only unwrap if nested looks richer than outer metadata-only shell
            nested_clean = _strip_metadata(nested)
            outer_clean = _strip_metadata(data)
            if len(nested_clean) >= len(outer_clean):
                data = nested
                break

    transaction = _strip_metadata(data)

    # Normalize transaction id aliases onto TransactionID
    if "TransactionID" not in transaction:
        for alias in ("transaction_id", "transactionId", "TransactionId"):
            if alias in transaction and transaction[alias] is not None:
                transaction["TransactionID"] = transaction[alias]
                break

    if not transaction:
        raise EventParseError("no transaction fields found after stripping metadata")

    return transaction


def validate_transaction_for_model(
    transaction: dict[str, Any],
    *,
    require_transaction_id: bool = True,
) -> dict[str, Any]:
    """Light schema checks before calling the 438-feature preprocessor."""
    if not isinstance(transaction, dict):
        raise EventParseError("transaction must be a dict")

    cleaned = {k: v for k, v in transaction.items() if k not in EXCLUDED_KEYS}

    if require_transaction_id:
        tid = cleaned.get("TransactionID")
        if tid is None:
            raise EventParseError("TransactionID is required")
        try:
            cleaned["TransactionID"] = int(tid)
        except (TypeError, ValueError) as exc:
            raise EventParseError("TransactionID must be numeric") from exc

    # Useful signal fields for IEEE-CIS; missing values are median-filled later
    if "TransactionAmt" in cleaned and cleaned["TransactionAmt"] is not None:
        try:
            cleaned["TransactionAmt"] = float(cleaned["TransactionAmt"])
        except (TypeError, ValueError) as exc:
            raise EventParseError("TransactionAmt must be numeric") from exc

    return cleaned


def parse_incoming_event(event: dict[str, Any]) -> dict[str, Any]:
    """Parse a Lakehouse incoming-row dict into a model-ready transaction.

    Returns ``{"transaction": {...}, "transaction_id": str, "cloudevents_id": str|None}``.
    """
    if not isinstance(event, dict):
        raise EventParseError("event row must be a dict")

    # Prefer explicit payload/body columns; otherwise treat the whole row as JSON-ish
    candidates: list[Any] = []
    for key in ("payload", "Payload", "body", "Body", "data", "Data"):
        if key in event and event[key] is not None:
            candidates.append(event[key])
    candidates.append(event)

    last_error: Exception | None = None
    transaction: dict[str, Any] | None = None
    for candidate in candidates:
        try:
            transaction = extract_transaction_dict(candidate)
            break
        except EventParseError as exc:
            last_error = exc

    if transaction is None:
        raise EventParseError(str(last_error) if last_error else "unable to parse event")

    # Row-level transaction_id column can fill gaps
    if transaction.get("TransactionID") is None:
        for key in ("transaction_id", "TransactionID", "transactionId"):
            if event.get(key) is not None:
                transaction["TransactionID"] = event[key]
                break

    transaction = validate_transaction_for_model(transaction)

    ce_id = None
    for key in (
        "cloudEvents:id",
        "cloudevents:id",
        "event_id",
        "id",
    ):
        if event.get(key):
            ce_id = str(event[key])
            break

    return {
        "transaction": transaction,
        "transaction_id": str(transaction["TransactionID"]),
        "cloudevents_id": ce_id,
    }
