from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable

log = logging.getLogger("app.db")
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise DatabaseUnavailable("DATABASE_URL is not configured on the server.")
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                                connect_args={"connect_timeout": 5})
    return _engine


def get_conn() -> Iterator[Connection]:
    """FastAPI dependency: a read-only connection per request."""
    try:
        conn = get_engine().connect()
    except OperationalError as exc:
        log.error("database connection failed: %s", exc.__class__.__name__)
        raise DatabaseUnavailable() from exc
    try:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        yield conn
    except OperationalError as exc:
        log.error("database error: %s", exc.__class__.__name__)
        raise DatabaseUnavailable() from exc
    except SQLAlchemyError:
        raise
    finally:
        conn.close()
