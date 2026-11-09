#!/usr/bin/env python3
"""Find a working Supabase Postgres URL and write it to .env.

Direct host db.<ref>.supabase.co often fails inside Docker (IPv6-only).
Session pooler (IPv4) is the supported fix.
"""

from __future__ import annotations

import re
import socket
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

# Common Supabase pooler regions (Session mode, port 5432)
POOLER_HOSTS = [
    "aws-0-ap-south-1.pooler.supabase.com",
    "aws-0-ap-southeast-1.pooler.supabase.com",
    "aws-0-ap-northeast-1.pooler.supabase.com",
    "aws-0-eu-central-1.pooler.supabase.com",
    "aws-0-eu-west-1.pooler.supabase.com",
    "aws-0-eu-west-2.pooler.supabase.com",
    "aws-0-us-east-1.pooler.supabase.com",
    "aws-0-us-east-2.pooler.supabase.com",
    "aws-0-us-west-1.pooler.supabase.com",
]


def load_database_url() -> str:
    text = ENV_PATH.read_text()
    m = re.search(r"^DATABASE_URL=(.*)$", text, re.M)
    if not m:
        raise SystemExit("DATABASE_URL missing in .env")
    return m.group(1).strip().strip('"').strip("'")


def parse_creds(url: str) -> tuple[str, str, str | None]:
    tmp = url
    if tmp.startswith("postgresql+psycopg2://"):
        tmp = "postgresql://" + tmp[len("postgresql+psycopg2://") :]
    elif tmp.startswith("postgres://"):
        tmp = "postgresql://" + tmp[len("postgres://") :]
    p = urlparse(tmp)
    password = unquote(p.password or "")
    if not password:
        raise SystemExit("DATABASE_URL has no password")
    host = p.hostname or ""
    ref = None
    if host.startswith("db.") and host.endswith(".supabase.co"):
        ref = host[len("db.") : -len(".supabase.co")]
    elif (p.username or "").startswith("postgres."):
        ref = (p.username or "")[len("postgres.") :]
    return password, host, ref


def build_url(user: str, password: str, host: str, port: int = 5432) -> str:
    return (
        f"postgresql+psycopg2://{user}:{quote(password, safe='')}"
        f"@{host}:{port}/postgres?sslmode=require"
    )


def try_connect(url: str) -> tuple[bool, str]:
    try:
        import psycopg2
    except ImportError:
        return False, "psycopg2 not installed (pip install psycopg2-binary)"

    dsn = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    try:
        host = urlparse(dsn).hostname or ""
        infos = socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
        families = sorted({("v6" if i[0] == socket.AF_INET6 else "v4") for i in infos})
        print(f"  DNS {host} -> {', '.join(families)}")
    except OSError as exc:
        return False, f"DNS failed: {exc}"

    try:
        conn = psycopg2.connect(dsn, connect_timeout=12)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_records (
                id SERIAL PRIMARY KEY,
                transaction_id VARCHAR(64) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                fraud_probability DOUBLE PRECISION NOT NULL,
                predicted_fraud BOOLEAN NOT NULL,
                risk_category VARCHAR(32) NOT NULL,
                model_version VARCHAR(64) NOT NULL,
                transaction_amt DOUBLE PRECISION,
                product_cd VARCHAR(16),
                CONSTRAINT uq_transaction_model_version UNIQUE (transaction_id, model_version)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_prediction_records_transaction_id "
            "ON prediction_records (transaction_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_prediction_records_created_at "
            "ON prediction_records (created_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_prediction_records_risk_category "
            "ON prediction_records (risk_category)"
        )
        conn.commit()
        conn.close()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def write_database_url(url: str) -> None:
    text = ENV_PATH.read_text()
    if not re.search(r"^DATABASE_URL=", text, re.M):
        text += f'\nDATABASE_URL="{url}"\n'
    else:
        text = re.sub(
            r"^DATABASE_URL=.*$",
            f'DATABASE_URL="{url}"',
            text,
            count=1,
            flags=re.M,
        )
    ENV_PATH.write_text(text)


def main() -> int:
    current = load_database_url()
    password, host, ref = parse_creds(current)
    print(f"Current host: {host}")
    print(f"Project ref:  {ref or '(unknown)'}")

    candidates: list[tuple[str, str]] = []
    # Keep current URL first
    candidates.append(("current .env URL", current if "sslmode=" in current else build_url("postgres", password, host)))

    if ref:
        for pooler in POOLER_HOSTS:
            user = f"postgres.{ref}"
            candidates.append((f"pooler {pooler}", build_url(user, password, pooler)))

    working: str | None = None
    for label, url in candidates:
        safe_host = urlparse(url.replace("postgresql+psycopg2://", "postgresql://", 1)).hostname
        print(f"\nTrying {label} ({safe_host})…")
        ok, detail = try_connect(url)
        if ok:
            print(f"  SUCCESS")
            working = url
            break
        print(f"  FAIL: {detail}")

    if not working:
        print(
            "\nNo working connection. Check: Supabase project is not paused, "
            "password is correct, and your network allows port 5432 outbound.",
            file=sys.stderr,
        )
        return 1

    write_database_url(working)
    host = urlparse(working.replace("postgresql+psycopg2://", "postgresql://", 1)).hostname
    print(f"\nWrote working DATABASE_URL (host={host}) to .env")
    print("Next:")
    print("  docker compose build --no-cache api")
    print("  docker compose up -d --force-recreate api web")
    print("  curl -s http://127.0.0.1:8000/health | jq '.database'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
