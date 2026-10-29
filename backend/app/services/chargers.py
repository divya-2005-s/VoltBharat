"""OMC charging-station installations by financial year (a separate measure from the state snapshot)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached
from app.services.common import growth


@cached
def growth_data(conn: Connection, state: str | None) -> dict:
    p = {"state": state}
    fy = conn.execute(text("""SELECT o.fy_label, o.fy_order, o.is_partial_year, sum(o.installed) AS installed
        FROM fact_chargers_omc_fy o JOIN dim_state s USING (state_id)
        WHERE CAST(:state AS TEXT) IS NULL OR s.state_name = CAST(:state AS TEXT)
        GROUP BY o.fy_label, o.fy_order, o.is_partial_year ORDER BY o.fy_order"""), p).mappings().all()
    years, cum, prev = [], 0, None
    for r in fy:
        n = int(r["installed"])
        cum += n
        years.append({"fy_label": r["fy_label"], "is_partial_year": r["is_partial_year"], "installed": n,
                      "cumulative_installed": cum,
                      # growth only between two complete financial years
                      "growth_pct": growth(n, prev["installed"]) if prev and not r["is_partial_year"] and not prev["is_partial_year"] else None})
        prev = {"installed": n, "is_partial_year": r["is_partial_year"]}
    status = conn.execute(text("""SELECT coalesce(sum(decommissioned), 0), coalesce(sum(total_installed), 0),
        coalesce(sum(total_operational), 0) FROM fact_chargers_omc_status o JOIN dim_state s USING (state_id)
        WHERE CAST(:state AS TEXT) IS NULL OR s.state_name = CAST(:state AS TEXT)"""), p).one()
    top = conn.execute(text("""SELECT s.state_name, o.total_installed, o.total_operational, o.decommissioned
        FROM fact_chargers_omc_status o JOIN dim_state s USING (state_id) ORDER BY o.total_installed DESC""")).mappings().all()
    return {
        "measure": "Charging stations installed by oil marketing companies (OMCs). Not the same as all public stations.",
        "financial_years": years,
        "status": {"decommissioned": int(status[0]), "total_installed": int(status[1]), "total_operational": int(status[2])},
        "by_state": [dict(t) for t in top],
        "notes": ["FY2025-26 covers only up to 1 March 2026 and is not compared with complete years.",
                  "'total_installed' is reported as given by the source; in a few rows it is net of decommissioned stations.",
                  "The source row 'Leh' is merged into Ladakh."],
    }
