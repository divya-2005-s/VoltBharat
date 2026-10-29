"""Database helpers shared by the ETL loader and init script."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from etl.config import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and set it "
                           "(e.g. postgresql+psycopg://voltbharat:<password>@localhost:5432/voltbharat).")
    return url


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True, future=True)


def safe_url(url: str | None = None) -> str:
    """URL with the password masked, for logs."""
    return make_url(url or database_url()).render_as_string(hide_password=True)
