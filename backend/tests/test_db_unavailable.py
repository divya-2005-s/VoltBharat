"""When the database is unreachable the API must fail clearly, never return made-up figures."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import app.db as db_module
from app.core.cache import clear_cache
from app.main import app


def test_endpoints_return_503_without_database(monkeypatch):
    dead = create_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(db_module, "_engine", dead)
    clear_cache()
    c = TestClient(app)
    r = c.get("/api/v1/overview")
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "database_unavailable"
    assert "data" not in body
    assert "nothing" not in r.text and "Traceback" not in r.text  # no credentials or stack traces leak
    h = c.get("/health")
    assert h.status_code == 503 and h.json()["database"] == "unavailable"
    clear_cache()
