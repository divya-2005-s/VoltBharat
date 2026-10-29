"""Core EV registration queries over v_ev_state_month (fuel-type source only)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services.common import pct, to_int, to_label

POWERTRAINS = ("bev", "strong_hybrid", "plugin_hybrid", "fcev", "other_hybrid")
_SUMS = ", ".join(f"coalesce(sum({c}), 0) AS {c}" for c in POWERTRAINS) + ", coalesce(sum(total_all_fuels), 0) AS total"
_STATE_FILTER = "(CAST(:state AS TEXT) IS NULL OR state_name = CAST(:state AS TEXT))"


def _clean(row) -> dict:
    return {k: to_int(v) if k in POWERTRAINS + ("total",) else v for k, v in dict(row).items()}


@cached
def totals(conn: Connection, start: int, end: int, state: str | None = None) -> dict:
    row = conn.execute(text(f"""SELECT {_SUMS}, count(DISTINCT date_id) AS months FROM v_ev_state_month
        WHERE date_id BETWEEN :s AND :e AND {_STATE_FILTER}"""), {"s": start, "e": end, "state": state}).mappings().one()
    out = _clean(row)
    out["ev_share_pct"] = pct(out["bev"], out["total"])
    return out


@cached
def by_state(conn: Connection, start: int, end: int) -> dict[str, dict]:
    rows = conn.execute(text(f"""SELECT state_name, {_SUMS} FROM v_ev_state_month
        WHERE date_id BETWEEN :s AND :e GROUP BY state_name"""), {"s": start, "e": end}).mappings().all()
    out = {}
    for r in rows:
        d = _clean(r)
        d["ev_share_pct"] = pct(d["bev"], d["total"])
        out[d.pop("state_name")] = d
    return out


@cached
def monthly(conn: Connection, start: int, end: int, state: str | None = None) -> list[dict]:
    """Monthly series with same-month-previous-year growth (computed over all data, then filtered)."""
    rows = conn.execute(text(f"""
        WITH m AS (
            SELECT date_id, {_SUMS} FROM v_ev_state_month WHERE {_STATE_FILTER} GROUP BY date_id)
        SELECT m.*, p.bev AS bev_prev_year, p.total AS total_prev_year
        FROM m LEFT JOIN m p ON p.date_id = m.date_id - 100
        WHERE m.date_id BETWEEN :s AND :e ORDER BY m.date_id"""), {"s": start, "e": end, "state": state}).mappings().all()
    out = []
    for r in rows:
        d = _clean(r)
        prev = to_int(d.pop("bev_prev_year"))
        prev_total = to_int(d.pop("total_prev_year"))
        bev, total = d["bev"], d["total"]
        out.append({
            "month": to_label(d.pop("date_id")), **d,
            "ev_share_pct": pct(bev, total),
            "bev_prev_year": prev,
            "bev_yoy_pct": None if not prev else round(100.0 * (bev - prev) / prev, 1),
            "ev_share_prev_year_pct": pct(prev, prev_total),
        })
    return out


@cached
def chargers_by_state(conn: Connection) -> dict[str, int]:
    return {r[0]: int(r[1]) for r in conn.execute(text(
        "SELECT state_name, public_charging_stations FROM v_state_chargers WHERE public_charging_stations IS NOT NULL"))}


@cached
def charger_snapshot_label(conn: Connection) -> str:
    row = conn.execute(text("""SELECT ds.coverage_label, ds.title FROM data_sources ds WHERE ds.source_key = 'chargers_state'""")).first()
    return row[0] if row else "2025 snapshot"


@cached
def state_list(conn: Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        "SELECT state_name, state_code, state_type, region FROM dim_state ORDER BY state_name")).mappings()]
