"""Manufacturer analytics. The maker source has NO fuel field: rankings are all-fuel."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services import registrations as reg
from app.services.common import pct


@cached
def maker_totals(conn: Connection, start: int, end: int, state: str | None) -> list[dict]:
    rows = conn.execute(text("""SELECT m.maker_name, m.name_identified_ev_maker, sum(f.registrations) AS registrations
        FROM fact_registrations_maker f JOIN dim_maker m USING (maker_id) JOIN dim_state s USING (state_id)
        WHERE f.date_id BETWEEN :s AND :e AND (CAST(:state AS TEXT) IS NULL OR s.state_name = CAST(:state AS TEXT))
        GROUP BY m.maker_name, m.name_identified_ev_maker ORDER BY registrations DESC, m.maker_name"""),
        {"s": start, "e": end, "state": state}).all()
    return [{"maker": r[0], "name_identified_ev_maker": r[1], "registrations": int(r[2])} for r in rows]


def makers(conn: Connection, start: int, end: int, state: str | None, search: str | None,
           ev_named_only: bool, page: int, page_size: int) -> dict:
    allm = maker_totals(conn, start, end, state)
    grand = sum(m["registrations"] for m in allm)
    for i, m in enumerate(allm, 1):
        m["rank"] = i
        m["share_of_all_registrations_pct"] = pct(m["registrations"], grand)
    ev_named = [m for m in allm if m["name_identified_ev_maker"]]
    ev_named_total = sum(m["registrations"] for m in ev_named)
    for i, m in enumerate(ev_named, 1):
        m["rank_within_ev_named"] = i
        m["share_within_ev_named_pct"] = pct(m["registrations"], ev_named_total)
    bev = reg.totals(conn, start, end, state)["bev"]

    rows = ev_named if ev_named_only else allm
    if search:
        q = search.strip().lower()
        rows = [m for m in rows if q in m["maker"].lower()]
    total_rows = len(rows)
    page_rows = rows[(page - 1) * page_size: page * page_size]
    return {
        "ev_market_share_supported": False,
        "ev_market_share_reason": ("The maker source has no fuel field, so a manufacturer's EV registrations cannot be "
                                   "separated from its petrol/diesel/CNG registrations. Figures below are ALL-FUEL."),
        "all_fuel": {
            "total_registrations": grand,
            "maker_count": len(allm),
            "top10": allm[:10],
            "top5_share_pct": pct(sum(m["registrations"] for m in allm[:5]), grand),
            "top10_share_pct": pct(sum(m["registrations"] for m in allm[:10]), grand),
        },
        "ev_named": {
            "definition": ("Makers whose registered name contains 'Electric', 'EV', 'e-Mobility' or 'E-Motorad'. "
                           "A name-based lower bound: it misses EV-only makers without such words in their name "
                           "(and all EVs sold by mixed-fuel makers)."),
            "maker_count": len(ev_named),
            "total_registrations": ev_named_total,
            "bev_registrations_fuel_source": bev,
            "coverage_of_bev_pct": pct(ev_named_total, bev),
            "top10": ev_named[:10],
        },
        "table": {"rows": page_rows, "page": page, "page_size": page_size, "total_rows": total_rows},
    }
