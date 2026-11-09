from tests.conftest import EXPECTED_PROBABILITY, PROBABILITY_TOLERANCE


def test_model_loads(loaded_model):
    assert loaded_model.loaded is True
    assert loaded_model.model_type == "LGBMClassifier"
    assert len(loaded_model.feature_columns) == 438
    assert loaded_model.threshold == 0.1


def test_parity_transaction_2987000(loaded_model, sample_transaction):
    result = loaded_model.predict(sample_transaction)
    assert result["transaction_id"] == "2987000"
    assert abs(result["fraud_probability"] - EXPECTED_PROBABILITY) <= PROBABILITY_TOLERANCE
    assert result["predicted_fraud"] == 0
    assert result["risk_category"] == "Low"
    assert result["threshold"] == 0.1


def test_ignores_is_fraud_target(loaded_model, sample_transaction):
    payload = dict(sample_transaction)
    payload["isFraud"] = 1
    result = loaded_model.predict(payload)
    assert abs(result["fraud_probability"] - EXPECTED_PROBABILITY) <= PROBABILITY_TOLERANCE


def test_missing_identity_features_use_training_defaults(loaded_model, sample_transaction):
    # Sample already omits identity features; prediction must still succeed
    result = loaded_model.predict(sample_transaction)
    assert "fraud_probability" in result


def test_unknown_category_handled(loaded_model, sample_transaction):
    payload = dict(sample_transaction)
    payload["ProductCD"] = "UNKNOWN_PRODUCT_CODE_XYZ"
    result = loaded_model.predict(payload)
    assert 0.0 <= result["fraud_probability"] <= 1.0
    assert result["risk_category"] in {"Low", "Medium", "High", "Critical"}


def test_invalid_numeric_coerced(loaded_model, sample_transaction):
    payload = dict(sample_transaction)
    payload["TransactionAmt"] = "not-a-number"
    result = loaded_model.predict(payload)
    assert 0.0 <= result["fraud_probability"] <= 1.0
