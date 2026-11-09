from tests.conftest import EXPECTED_PROBABILITY, PROBABILITY_TOLERANCE


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "GraphGuard" in data["message"]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["model_loaded"] is True
    assert data["model_type"] == "LGBMClassifier"
    assert data["feature_count"] == 438
    assert data["threshold"] == 0.1
    assert data["fabric"]["status"] == "not_configured"
    assert data["database"]["status"] == "ok"


def test_predict_valid_transaction(client, sample_transaction):
    response = client.post("/predict", json={"transaction": sample_transaction})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["transaction_id"] == "2987000"
    pred = data["prediction"]
    assert abs(pred["fraud_probability"] - EXPECTED_PROBABILITY) <= PROBABILITY_TOLERANCE
    assert pred["predicted_fraud"] == 0
    assert pred["risk_category"] == "Low"
    assert pred["threshold"] == 0.1


def test_predict_persists_and_lists(client, sample_transaction):
    client.post("/predict", json={"transaction": sample_transaction})
    response = client.get("/transactions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["transaction_id"] == "2987000" for item in data["items"])


def test_predict_batch(client, sample_transaction):
    second = dict(sample_transaction)
    second["TransactionID"] = 2987001
    response = client.post(
        "/predict/batch",
        json={"transactions": [sample_transaction, second]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0


def test_batch_limit(client, sample_transaction):
    # Override via env is not easy mid-test; send oversized relative to default 100
    oversized = [dict(sample_transaction, TransactionID=i) for i in range(101)]
    response = client.post("/predict/batch", json={"transactions": oversized})
    assert response.status_code == 400
    assert "exceeds limit" in response.json()["detail"]


def test_analytics_summary_and_trends(client, sample_transaction):
    client.post("/predict", json={"transaction": sample_transaction})
    summary = client.get("/analytics/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_analyzed"] >= 1
    assert "risk_distribution" in body

    trends = client.get("/analytics/trends?bucket=day&days=30")
    assert trends.status_code == 200
    assert trends.json()["bucket"] == "day"


def test_transactions_filter(client, sample_transaction):
    client.post("/predict", json={"transaction": sample_transaction})
    response = client.get("/transactions", params={"search": "2987000", "risk_category": "Low"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_predict_rejects_non_object(client):
    response = client.post("/predict", json={"transaction": ["not", "an", "object"]})
    assert response.status_code == 422
