import json

import pytest

from app.services.event_parser import (
    EventParseError,
    extract_transaction_dict,
    parse_incoming_event,
    validate_transaction_for_model,
)


def test_extract_raw_transaction():
    raw = {"TransactionID": 2987000, "TransactionAmt": 68.5, "ProductCD": "W"}
    out = extract_transaction_dict(raw)
    assert out["TransactionID"] == 2987000
    assert out["TransactionAmt"] == 68.5


def test_extract_json_string_payload():
    raw = json.dumps({"TransactionID": 1, "TransactionAmt": 10.0})
    out = extract_transaction_dict(raw)
    assert out["TransactionID"] == 1


def test_extract_cloudevents_data_envelope():
    envelope = {
        "specversion": "1.0",
        "type": "GraphGuard_Transaction_Schema",
        "source": "/graphguard/transactions",
        "id": "abc-123",
        "data": {"TransactionID": 42, "TransactionAmt": 9.99, "ProductCD": "C"},
    }
    out = extract_transaction_dict(envelope)
    assert out["TransactionID"] == 42
    assert "specversion" not in out
    assert "type" not in out


def test_extract_cloudevents_data_as_json_string():
    envelope = {
        "cloudEvents:type": "GraphGuard_Transaction_Schema",
        "data": json.dumps({"TransactionID": 7, "TransactionAmt": 1.0}),
    }
    out = extract_transaction_dict(envelope)
    assert out["TransactionID"] == 7


def test_strips_prediction_fields():
    raw = {
        "TransactionID": 5,
        "TransactionAmt": 1.0,
        "fraud_probability": 0.9,
        "predicted_fraud": 1,
        "isFraud": 1,
    }
    out = extract_transaction_dict(raw)
    assert "fraud_probability" not in out
    assert "isFraud" not in out


def test_transaction_id_alias_normalized():
    out = validate_transaction_for_model(
        extract_transaction_dict({"transaction_id": "99", "TransactionAmt": 2})
    )
    assert out["TransactionID"] == 99


def test_validate_rejects_non_numeric_transaction_id():
    with pytest.raises(EventParseError, match="numeric"):
        validate_transaction_for_model({"TransactionID": "abc", "TransactionAmt": 1})


def test_parse_incoming_event_from_payload_column():
    event = {
        "transaction_id": 1001,
        "event_timestamp": "2026-11-09T00:00:00Z",
        "payload": json.dumps(
            {"TransactionID": 1001, "TransactionAmt": 12.5, "ProductCD": "W"}
        ),
    }
    parsed = parse_incoming_event(event)
    assert parsed["transaction_id"] == "1001"
    assert parsed["transaction"]["TransactionAmt"] == 12.5


def test_parse_incoming_event_flat_row_without_payload():
    event = {
        "TransactionID": 55,
        "TransactionAmt": 3.0,
        "ProductCD": "H",
        "EventProcessedUtcTime": "2026-11-09T12:00:00Z",
    }
    parsed = parse_incoming_event(event)
    assert parsed["transaction_id"] == "55"
    assert parsed["transaction"]["ProductCD"] == "H"


def test_parse_incoming_event_fills_tid_from_row_column():
    event = {
        "transaction_id": 777,
        "payload": json.dumps({"TransactionAmt": 8.0, "ProductCD": "W"}),
    }
    parsed = parse_incoming_event(event)
    assert parsed["transaction_id"] == "777"
    assert parsed["transaction"]["TransactionID"] == 777


def test_parse_rejects_empty_payload():
    with pytest.raises(EventParseError):
        parse_incoming_event({"payload": "{}"})
