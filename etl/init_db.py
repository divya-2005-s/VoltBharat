"""Create the database (if missing) and apply sql/schema.sql and sql/views.sql.

Usage: python -m etl.init_db
Non-destructive: uses CREATE ... IF NOT EXISTS / CREATE OR REPLACE VIEW only.
"""
from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from etl.config import PROJECT_ROOT
from etl.db import database_url, get_engine, safe_url
from etl.logging_utils import setup_logging

log = logging.getLogger("etl.init_db")


def ensure_database(url: str) -> None:
    u = make_url(url)
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": u.database}).scalar()
        if not exists:
            # Identifiers cannot be bound as parameters; the name comes from our own config.
            if not u.database.replace("_", "").isalnum():
                raise ValueError(f"Refusing to create database with unusual name {u.database!r}")
            c.execute(text(f'CREATE DATABASE "{u.database}"'))
            log.info("Created database %s", u.database)
    admin.dispose()


def apply_sql(engine) -> None:
    for name in ("schema.sql", "views.sql"):
        sql = (PROJECT_ROOT / "sql" / name).read_text(encoding="utf-8")
        raw = engine.raw_connection()
        try:
            # No parameters: psycopg sends the script as-is (no '%' placeholder parsing).
            raw.cursor().execute(sql)
            raw.commit()
        finally:
            raw.close()
        log.info("Applied sql/%s", name)


def run(url: str | None = None) -> None:
    url = url or database_url()
    log.info("Initialising %s", safe_url(url))
    try:
        ensure_database(url)
    except Exception as exc:  # noqa: BLE001 - lacking CREATEDB rights is fine if the DB exists
        log.warning("Could not check/create database (%s); assuming it exists.", exc.__class__.__name__)
    apply_sql(get_engine(url))


if __name__ == "__main__":
    setup_logging("init_db")
    run()
