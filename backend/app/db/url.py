"""Normalize database URLs for SQLAlchemy + managed Postgres (Supabase)."""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    if url.startswith("sqlite"):
        return url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query, keep_blank_values=True)
    if ("supabase.co" in host or "supabase.com" in host) and "sslmode" not in query:
        query["sslmode"] = ["require"]
        parsed = parsed._replace(query=urlencode(query, doseq=True))
        url = urlunparse(parsed)
    return url
