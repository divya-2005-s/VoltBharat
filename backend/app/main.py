"""VoltBharat API.

Run locally:  uvicorn app.main:app --app-dir backend --reload
Docs:         http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.db import get_engine
from app.routers import charging, exports, insights, makers, overview, policy, segments, sources, states, trends
from app.schemas import ErrorResponse, Health

VERSION = "1.0.0"
settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("app")

app = FastAPI(
    title="VoltBharat API",
    version=VERSION,
    description="India EV adoption and charging-gap analytics. All figures come from the VoltBharat PostgreSQL "
                "database built by the ETL pipeline; nothing is fabricated when data is missing.",
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])


@app.middleware("http")
async def access_log(request: Request, call_next):
    t = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/v1"):
        response.headers.setdefault("Cache-Control", "public, max-age=60")
    log.info("request", extra={"method": request.method, "path": request.url.path, "query": str(request.url.query),
                               "status": response.status_code, "duration_ms": round((time.perf_counter() - t) * 1000, 1)})
    return response


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
async def api_error(_: Request, exc: ApiError):
    return _err(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    parts = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e["loc"] if x not in ("query", "path"))
        parts.append(f"{loc}: {e['msg']}")
    return _err(422, "invalid_request", "; ".join(parts))


@app.exception_handler(SQLAlchemyError)
async def db_error(_: Request, exc: SQLAlchemyError):
    log.error("database query failed: %s", exc.__class__.__name__, exc_info=exc)
    return _err(503, "database_error", "A database error occurred. Please retry shortly.")


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.error("unhandled error", exc_info=exc)
    return _err(500, "internal_error", "An unexpected error occurred.")


for r in (overview, trends, states, segments, makers, charging, policy, insights, exports, sources):
    app.include_router(r.router, prefix="/api/v1")


@app.get("/health", response_model=Health, tags=["health"], responses={503: {"model": Health}})
def health():
    try:
        with get_engine().connect() as c:
            last = c.execute(text("SELECT max(finished_at) FROM etl_runs WHERE status = 'success'")).scalar()
        return {"status": "ok", "database": "ok", "last_successful_etl": last.isoformat() if last else None, "version": VERSION}
    except Exception as exc:  # noqa: BLE001 - health must never raise
        log.warning("health check: database unavailable (%s)", exc.__class__.__name__)
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable",
                                                      "last_successful_etl": None, "version": VERSION})
