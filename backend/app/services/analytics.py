"""Overview, state and charging-gap analytics built on the fuel-type source."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services import registrations as reg
from app.services.common import Period, fuel_coverage, growth, pct, to_label, trailing_yoy_window

# States below these bases are not ranked on ratios, to avoid tiny-denominator noise.
MIN_TOTAL_FOR_SHARE_RANK = 10_000      # all-fuel registrations in the period
MIN_PREV_BEV_FOR_GROWTH_RANK = 1_000   # BEV registrations in the comparison window
SMALL_CHARGER_BASE = 25                # stations; ratios flagged as unstable below this

PRESSURE_HIGH = 2.0       # x national EVs-per-charger
PRESSURE_ELEVATED = 1.25


def yoy_block(conn: Connection, end: int, state: str | None = None) -> dict:
    w = trailing_yoy_window(conn, end)
    block = {"window": w.as_dict(), "bev_current": None, "bev_previous": None, "growth_pct": None,
             "ev_share_current_pct": None, "ev_share_previous_pct": None, "share_change_pp": None}
    if not w.available:
        block["unavailable_reason"] = ("Needs 24 months of data ending at the selected end month; "
                                       f"data starts {to_label(fuel_coverage(conn).first)}.")
        return block
    cur = reg.totals(conn, w.current_start, w.current_end, state)
    prev = reg.totals(conn, w.previous_start, w.previous_end, state)
    block.update(bev_current=cur["bev"], bev_previous=prev["bev"], growth_pct=growth(cur["bev"], prev["bev"]),
                 ev_share_current_pct=cur["ev_share_pct"], ev_share_previous_pct=prev["ev_share_pct"],
                 share_change_pp=(round(cur["ev_share_pct"] - prev["ev_share_pct"], 2)
                                  if cur["ev_share_pct"] is not None and prev["ev_share_pct"] is not None else None))
    return block


def state_table(conn: Connection, period: Period) -> list[dict]:
    """One row per state with registrations, share, growth, chargers and pressure ratio."""
    cur = reg.by_state(conn, period.start, period.end)
    chargers = reg.chargers_by_state(conn)
    w = trailing_yoy_window(conn, period.end)
    yc = reg.by_state(conn, w.current_start, w.current_end) if w.available else {}
    yp = reg.by_state(conn, w.previous_start, w.previous_end) if w.available else {}
    states = {s["state_name"]: s for s in reg.state_list(conn)}
    rows = []
    for name, meta in states.items():
        d = cur.get(name, {"bev": None, "total": None, "ev_share_pct": None})
        ch = chargers.get(name)
        prev_bev = yp.get(name, {}).get("bev")
        rows.append({
            "state_name": name, "state_code": meta["state_code"], "state_type": meta["state_type"], "region": meta["region"],
            "bev": d.get("bev"), "total_registrations": d.get("total"), "ev_share_pct": d.get("ev_share_pct"),
            "strong_hybrid": d.get("strong_hybrid"),
            "bev_last_12m": yc.get(name, {}).get("bev"), "bev_prev_12m": prev_bev,
            "yoy_growth_pct": growth(yc.get(name, {}).get("bev"), prev_bev) if w.available else None,
            "public_chargers": ch,
            "bev_per_charger": round(d["bev"] / ch, 1) if ch and d.get("bev") is not None else None,
            "share_rankable": bool(d.get("total") and d["total"] >= MIN_TOTAL_FOR_SHARE_RANK),
            "growth_rankable": bool(prev_bev and prev_bev >= MIN_PREV_BEV_FOR_GROWTH_RANK),
        })
    _rank(rows, "bev", "rank_bev", lambda r: r["bev"] is not None)
    _rank(rows, "ev_share_pct", "rank_share", lambda r: r["share_rankable"] and r["ev_share_pct"] is not None)
    _rank(rows, "yoy_growth_pct", "rank_growth", lambda r: r["growth_rankable"] and r["yoy_growth_pct"] is not None)
    return rows


def _rank(rows, key, out, ok):
    eligible = sorted((r for r in rows if ok(r)), key=lambda r: r[key], reverse=True)
    for r in rows:
        r[out] = None
    for i, r in enumerate(eligible, 1):
        r[out] = i


@cached
def overview(conn: Connection, start: int, end: int, state: str | None) -> dict:
    period = Period(start, end)
    t = reg.totals(conn, period.start, period.end, state)
    chargers = reg.chargers_by_state(conn)
    series = reg.monthly(conn, period.start, period.end, state)
    latest = series[-1] if series else None
    table = state_table(conn, period)
    by_bev = sorted([r for r in table if r["rank_bev"]], key=lambda r: r["rank_bev"])[:5]
    by_share = sorted([r for r in table if r["rank_share"]], key=lambda r: r["rank_share"])[:5]
    nat = reg.totals(conn, period.start, period.end)
    return {
        "kpis": {
            "bev_registrations": t["bev"],
            "total_registrations": t["total"],
            "ev_share_pct": t["ev_share_pct"],
            "yoy": yoy_block(conn, period.end, state),
            "public_chargers": chargers.get(state) if state else sum(chargers.values()),
            "charger_snapshot": reg.charger_snapshot_label(conn),
            "months": t["months"],
        },
        "latest_month": latest,
        "trend": series,
        "map": [{"state_name": r["state_name"], "ev_share_pct": r["ev_share_pct"], "bev": r["bev"],
                 "share_rankable": r["share_rankable"]} for r in table],
        "top_states_by_bev": [{"state_name": r["state_name"], "value": r["bev"],
                               "share_of_national_pct": pct(r["bev"], nat["bev"])} for r in by_bev],
        "top_states_by_share": [{"state_name": r["state_name"], "value": r["ev_share_pct"], "bev": r["bev"]} for r in by_share],
        "powertrain": {k: t[k] for k in reg.POWERTRAINS},
        "selected_state": state,
    }


def charging_gap(conn: Connection, period: Period) -> dict:
    table = state_table(conn, period)
    nat_bev = sum(r["bev"] or 0 for r in table)
    nat_ch = sum(r["public_chargers"] or 0 for r in table)
    nat_ratio = round(nat_bev / nat_ch, 1) if nat_ch else None
    rows = []
    for r in table:
        ratio = r["bev_per_charger"]
        small = r["public_chargers"] is not None and r["public_chargers"] < SMALL_CHARGER_BASE
        rel = round(ratio / nat_ratio, 2) if ratio is not None and nat_ratio else None
        tier = None
        if rel is not None and not small:
            tier = "high" if rel >= PRESSURE_HIGH else "elevated" if rel >= PRESSURE_ELEVATED else "typical"
        rows.append({"state_name": r["state_name"], "state_code": r["state_code"], "bev": r["bev"],
                     "public_chargers": r["public_chargers"], "bev_per_charger": ratio,
                     "relative_to_national": rel, "pressure_tier": tier, "small_charger_base": small,
                     "rankable": ratio is not None and not small,
                     "unrankable_reason": None if ratio is not None and not small else (
                         "no charger count" if not r["public_chargers"] else
                         f"fewer than {SMALL_CHARGER_BASE} stations: ratio is unstable" if small else "no registrations")})
    _rank(rows, "bev_per_charger", "rank", lambda r: r["rankable"])
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return {"national": {"bev": nat_bev, "public_chargers": nat_ch, "bev_per_charger": nat_ratio},
            "thresholds": {"high": PRESSURE_HIGH, "elevated": PRESSURE_ELEVATED, "small_charger_base": SMALL_CHARGER_BASE},
            "states": rows}


@cached
def state_detail(conn: Connection, start: int, end: int, state: str) -> dict:
    period = Period(start, end)
    row = next(r for r in state_table(conn, period) if r["state_name"] == state)
    nat = reg.totals(conn, period.start, period.end)
    makers = conn.execute(text("""SELECT m.maker_name, m.name_identified_ev_maker, sum(f.registrations) AS registrations
        FROM fact_registrations_maker f JOIN dim_maker m USING (maker_id) JOIN dim_state s USING (state_id)
        WHERE s.state_name = :state AND f.date_id BETWEEN :s AND :e
        GROUP BY m.maker_name, m.name_identified_ev_maker ORDER BY registrations DESC LIMIT 10"""),
        {"state": state, "s": period.start, "e": period.end}).mappings().all()
    omc = conn.execute(text("""SELECT o.fy_label, o.fy_order, o.is_partial_year, o.installed FROM fact_chargers_omc_fy o
        JOIN dim_state s USING (state_id) WHERE s.state_name = :state ORDER BY o.fy_order"""), {"state": state}).mappings().all()
    return {
        "summary": row,
        "national_ev_share_pct": nat["ev_share_pct"],
        "trend": reg.monthly(conn, period.start, period.end, state),
        "powertrain": {k: v for k, v in reg.totals(conn, period.start, period.end, state).items() if k in reg.POWERTRAINS},
        "yoy": yoy_block(conn, period.end, state),
        "top_makers_all_fuels": [{"maker": m["maker_name"], "registrations": int(m["registrations"]),
                                  "name_identified_ev_maker": m["name_identified_ev_maker"]} for m in makers],
        "omc_installations": [dict(o) for o in omc],
    }
