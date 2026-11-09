FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY sample_transaction.json .
COPY tests ./tests
COPY pytest.ini .

ENV PYTHONUNBUFFERED=1 \
    MODEL_PATH=app/models/graphguard_prediction_bundle.joblib \
    DATABASE_URL=postgresql+psycopg2://graphguard:graphguard@db:5432/graphguard

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
