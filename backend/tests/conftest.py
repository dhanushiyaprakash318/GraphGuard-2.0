import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test DB is configured before app imports create the engine
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ.setdefault("LOG_LEVEL", "WARNING")
# Avoid loading a host .env that may contain JSON-style list values
os.environ.setdefault("MODEL_VERSION", "graphguard-lgbm-v1")

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.services.predictor import predictor_service

get_settings.cache_clear()

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "sample_transaction.json"
EXPECTED_PROBABILITY = 0.020889
PROBABILITY_TOLERANCE = 1e-5


@pytest.fixture(scope="session")
def sample_transaction() -> dict:
    data = json.loads(SAMPLE_PATH.read_text())
    data = dict(data)
    data["TransactionID"] = 2987000
    return data


@pytest.fixture(scope="session")
def loaded_model():
    if not predictor_service.loaded:
        settings = get_settings()
        predictor_service.load(settings.model_path)
    return predictor_service


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session, loaded_model):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
