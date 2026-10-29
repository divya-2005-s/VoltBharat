"""Vehicle segments.

EV-specific segments: only powertrain types (BEV, strong hybrid, plug-in hybrid,
fuel cell) are identifiable, from the fuel-type source. The fuel source has no
vehicle-category field, so electric 2W/3W/car/bus splits are NOT available.

All-fuel category context comes from the category file, restricted to states
whose cleaned totals validated against the fuel file.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services import registrations as reg
from app.services.common import pct, to_label

CATEGORY_GROUPS = {
    "Two Wheeler(Nt)": "Two-wheelers", "Two Wheeler(T)": "Two-wheelers", "Two Wheeler (Invalid Carriage)": "Two-wheelers",
    "Three Wheeler(T)": "Three-wheelers", "Three Wheeler(Nt)": "Three-wheelers",
    "Light Motor Vehicle": "Light motor vehicles (cars/jeeps)", "Four Wheeler (Invalid Carriage)": "Light motor vehicles (cars/jeeps)",
    "Light Goods Vehicle": "Goods vehicles", "Medium Goods Vehicle": "Goods vehicles", "Heavy Goods Vehicle": "Goods vehicles",
    "Light Passenger Vehicle": "Passenger vehicles (buses/taxis)", "Medium Passenger Vehicle": "Passenger vehicles (buses/taxis)",
    "Heavy Passenger Vehicle": "Passenger vehicles (buses/taxis)",
    "Medium Motor Vehicle": "Other", "Heavy Motor Vehicle": "Other", "Other Than Mentioned Above": "Other",
}
POWERTRAIN_LABELS = {"bev": "Battery electric (BEV)", "strong_hybrid": "Strong hybrid", "plugin_hybrid": "Plug-in hybrid",
                     "fcev": "Fuel cell (hydrogen)"}


@cached
def category_coverage(conn: Connection) -> tuple[int, int]:
    return tuple(conn.execute(text("SELECT min(date_id), max(date_id) FROM fact_registrations_segment")).one())


@cached
def segments(conn: Connection, start: int, end: int, state: str | None) -> dict:
    series = reg.monthly(conn, start, end, state)
    totals = reg.totals(conn, start, end, state)
    ev_total = sum(totals[k] for k in POWERTRAIN_LABELS)
    powertrain = {
        "series": [{"month": r["month"], **{k: r[k] for k in POWERTRAIN_LABELS}} for r in series],
        "totals": [{"key": k, "label": v, "registrations": totals[k], "share_pct": pct(totals[k], ev_total)}
                   for k, v in POWERTRAIN_LABELS.items()],
    }

    c0, c1 = category_coverage(conn)
    s, e = max(start, c0), min(end, c1)
    cat = {"coverage": {"start": to_label(c0), "end": to_label(c1)}, "series": [], "totals": [], "available": False,
           "states_included": [], "reason": None}
    validated = [r[0] for r in conn.execute(text("""SELECT DISTINCT s.state_name FROM fact_registrations_segment f
        JOIN dim_state s USING (state_id) WHERE f.state_validated ORDER BY 1"""))]
    cat["states_included"] = validated if not state else [state] if state in validated else []
    if s > e:
        cat["reason"] = f"The category source covers {to_label(c0)} to {to_label(c1)} only; the selected period is outside it."
    elif state and state not in validated:
        cat["reason"] = (f"{state}'s category data did not validate against the fuel-type source "
                         "(or is absent), so it is not shown.")
    else:
        rows = conn.execute(text("""SELECT f.date_id, v.vehicle_type, sum(f.registrations) AS registrations
            FROM fact_registrations_segment f JOIN dim_vehicle_type v USING (vehicle_type_id) JOIN dim_state st USING (state_id)
            WHERE f.state_validated AND f.date_id BETWEEN :s AND :e
              AND (CAST(:state AS TEXT) IS NULL OR st.state_name = CAST(:state AS TEXT))
            GROUP BY f.date_id, v.vehicle_type ORDER BY f.date_id"""), {"s": s, "e": e, "state": state}).all()
        by_month: dict[str, dict] = {}
        group_tot: dict[str, int] = {}
        for date_id, vt, n in rows:
            g = CATEGORY_GROUPS.get(vt, "Other")
            n = int(n or 0)
            by_month.setdefault(to_label(date_id), {})
            by_month[to_label(date_id)][g] = by_month[to_label(date_id)].get(g, 0) + n
            group_tot[g] = group_tot.get(g, 0) + n
        grand = sum(group_tot.values())
        cat.update(available=bool(rows), period={"start": to_label(s), "end": to_label(e)},
                   series=[{"month": m, **v} for m, v in by_month.items()],
                   totals=sorted([{"group": g, "registrations": n, "share_pct": pct(n, grand)} for g, n in group_tot.items()],
                                 key=lambda x: -x["registrations"]),
                   groups=sorted(group_tot, key=lambda g: -group_tot[g]))
    return {
        "ev_category_split_supported": False,
        "ev_category_split_reason": ("The fuel-type source (the only source that identifies EVs) has no vehicle-category field, "
                                     "and the category and maker sources have no fuel field. Electric two-wheeler, "
                                     "three-wheeler, car, bus and goods-vehicle counts therefore cannot be derived."),
        "powertrain": powertrain,
        "all_fuel_categories": cat,
    }
