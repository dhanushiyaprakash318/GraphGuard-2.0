from app.db.url import normalize_database_url


def test_normalize_adds_psycopg2_and_supabase_ssl():
    url = normalize_database_url(
        "postgresql://postgres.abc:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert url.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in url


def test_normalize_preserves_local_compose_url():
    url = normalize_database_url(
        "postgresql+psycopg2://graphguard:graphguard@db:5432/graphguard"
    )
    assert "sslmode" not in url
    assert url.startswith("postgresql+psycopg2://")


def test_normalize_postgres_scheme():
    url = normalize_database_url("postgres://user:pass@localhost:5432/db")
    assert url.startswith("postgresql+psycopg2://")
