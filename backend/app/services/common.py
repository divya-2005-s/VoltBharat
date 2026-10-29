"""Shared helpers: period resolution, state lookup, metric arithmetic.

All SQL uses bound parameters; user input is never interpolated into SQL text.
Months are handled as integer date_ids (yyyymm) matching dim_date.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.core.errors import ApiError

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def to_id(month: str) -> int:
    y, m = month.split("-")
    return int(y) * 100 + int(m)


def to_label(date_id: int) -> str:
    return f"{date_id // 100:04d}-{date_id % 100:02d}"


def shift(date_id: int, months: int) -> int:
    y, m = divmod(date_id // 100 * 12 + date_id % 100 - 1 + months, 12)
    return y * 100 + m + 1


def months_between(a: int, b: int) -> int:
    """Inclusive month count from a to b."""
    return (b // 100 - a // 100) * 12 + (b % 100 - a % 100) + 1


def pct(num, den, digits: int = 2):
    if num is None or den in (None, 0):
        return None
    return round(100.0 * float(num) / float(den), digits)


def growth(cur, prev, digits: int = 1):
    if cur is None or prev in (None, 0):
        return None
    return round(100.0 * (float(cur) - float(prev)) / float(prev), digits)


def to_int(v):
    return None if v is None else int(v)


@dataclass
class Coverage:
    first: int
    last: int


@cached
def fuel_coverage(conn: Connection) -> Coverage:
    row = conn.execute(text("SELECT min(date_id), max(date_id) FROM fact_registrations_fuel")).one()
    if row[0] is None:
        raise ApiError(503, "no_data", "The registrations table is empty. Run the ETL pipeline with --load-db.")
    return Coverage(row[0], row[1])


@dataclass
class Period:
    start: int
    end: int
    notes: list[str] = field(default_factory=list)

    @property
    def months(self) -> int:
        return months_between(self.start, self.end)

    def as_dict(self) -> dict:
        return {"start": to_label(self.start), "end": to_label(self.end), "months": self.months}


def resolve_period(conn: Connection, start: str | None, end: str | None, cov: Coverage | None = None) -> Period:
    cov = cov or fuel_coverage(conn)
    s = to_id(start) if start else cov.first
    e = to_id(end) if end else cov.last
    if s > e:
        raise ApiError(422, "invalid_period", "start must be on or before end.")
    if e < cov.first or s > cov.last:
        raise ApiError(422, "period_out_of_range",
                       f"No data in the requested period. Available: {to_label(cov.first)} to {to_label(cov.last)}.")
    p = Period(max(s, cov.first), min(e, cov.last))
    if p.start != s or p.end != e:
        p.notes.append(f"Period limited to available data: {to_label(p.start)} to {to_label(p.end)}.")
    return p


@dataclass
class TrailingYoY:
    current_start: int
    current_end: int
    previous_start: int
    previous_end: int
    available: bool

    def as_dict(self) -> dict:
        return {"current": {"start": to_label(self.current_start), "end": to_label(self.current_end)},
                "previous": {"start": to_label(self.previous_start), "end": to_label(self.previous_end)},
                "available": self.available}


def trailing_yoy_window(conn: Connection, end: int) -> TrailingYoY:
    """12 months ending at `end` vs the 12 months before. Needs 24 months of data."""
    cov = fuel_coverage(conn)
    cs = shift(end, -11)
    ps, pe = shift(end, -23), shift(end, -12)
    return TrailingYoY(cs, end, ps, pe, ps >= cov.first)


@cached
def state_names(conn: Connection) -> dict[str, str]:
    """lower-case name -> canonical name."""
    return {r[0].lower(): r[0] for r in conn.execute(text("SELECT state_name FROM dim_state"))}


def resolve_state(conn: Connection, state: str | None) -> str | None:
    if not state:
        return None
    canonical = state_names(conn).get(state.strip().lower())
    if not canonical:
        raise ApiError(404, "unknown_state", f"Unknown state or union territory: {state!r}.")
    return canonical


@cached
def latest_etl_run(conn: Connection) -> dict | None:
    row = conn.execute(text("""SELECT run_id, started_at, finished_at FROM etl_runs
        WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1""")).mappings().first()
    return dict(row) if row else None


def meta(conn: Connection, period: Period | None, sources: list[str], notes: list[str] | None = None, **extra) -> dict:
    run = latest_etl_run(conn)
    cov = fuel_coverage(conn)
    m = {
        "period": period.as_dict() if period else None,
        "sources": sources,
        "notes": (period.notes if period else []) + (notes or []),
        "data_coverage": {"start": to_label(cov.first), "end": to_label(cov.last)},
        "last_processed_at": run["finished_at"].isoformat() if run else None,
    }
    m.update(extra)
    return m
