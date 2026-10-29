import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.cache import clear_cache
from app.db import get_engine
from app.main import app


def _db_ready() -> str | None:
    try:
        with get_engine().connect() as c:
            if not c.execute(text("SELECT count(*) FROM fact_registrations_fuel")).scalar():
                return "database is empty: run `python -m etl.run_pipeline --load-db`"
    except Exception as exc:  # noqa: BLE001
        return f"database unavailable ({exc.__class__.__name__}); set DATABASE_URL and load data"
    return None


@pytest.fixture(scope="session")
def client():
    reason = _db_ready()
    if reason:
        pytest.skip(reason)
    clear_cache()
    return TestClient(app)


@pytest.fixture(scope="session")
def db():
    reason = _db_ready()
    if reason:
        pytest.skip(reason)
    with get_engine().connect() as c:
        yield c
