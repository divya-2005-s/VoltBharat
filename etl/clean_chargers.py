"""Standardise the two charging-station datasets. They stay separate measures.

Outputs (data/processed/):
  chargers_state_snapshot.csv   state, public_charging_stations (2025 snapshot)
  chargers_omc_yearwise.csv     state, fy_label, fy_order, is_partial_year, installed (long format)
  chargers_omc_summary.csv      state, decommissioned, total_installed, total_operational
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from etl.config import PROCESSED_DIR, sql_path
from etl.extract_vahan import assert_states_mapped

log = logging.getLogger("etl.clean_chargers")

STATE_SNAPSHOT_LABEL = "2025 (PIB annexure, Aug-2025)"


def fy_label(col: str) -> tuple[str, bool]:
    """'fy2020_21' -> ('FY2020-21', False); 'fy2025_26_upto_mar1' -> ('FY2025-26 (up to 1 Mar 2026)', True)."""
    m = re.fullmatch(r"fy(\d{4})_(\d{2})(_upto_(\w+))?", col)
    if not m:
        raise ValueError(f"Unrecognised financial-year column: {col}")
    label = f"FY{m.group(1)}-{m.group(2)}"
    if m.group(3):
        upto = m.group(4)
        day = re.sub(r"\D", "", upto) or "?"
        mon = re.sub(r"\d", "", upto).capitalize()
        end_year = int(m.group(1)) + 1
        return f"{label} (up to {day} {mon} {end_year})", True
    return label, False


def run(con, sources: dict[str, Path]) -> None:
    con.execute(f"""CREATE OR REPLACE TABLE stg_chargers_state AS
        SELECT trim(state) AS state_raw, public_charging_stations::INTEGER AS public_charging_stations
        FROM read_csv('{sql_path(sources["chargers_state"])}', header=true)""")
    assert_states_mapped(con, "stg_chargers_state")
    con.execute("""CREATE OR REPLACE TABLE chargers_state_snapshot AS
        SELECT m.canonical_name AS state_name, sum(public_charging_stations)::INTEGER AS public_charging_stations
        FROM stg_chargers_state s JOIN ref_state_mapping m ON m.source_name = s.state_raw
        GROUP BY 1 ORDER BY 2 DESC""")
    con.execute(f"COPY chargers_state_snapshot TO '{sql_path(PROCESSED_DIR / 'chargers_state_snapshot.csv')}' (HEADER)")

    con.execute(f"""CREATE OR REPLACE TABLE stg_chargers_omc AS
        SELECT * REPLACE (trim(state) AS state) FROM read_csv('{sql_path(sources["chargers_omc"])}', header=true)""")
    con.execute("ALTER TABLE stg_chargers_omc RENAME COLUMN state TO state_raw")
    assert_states_mapped(con, "stg_chargers_omc")
    fy_cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'stg_chargers_omc' "
        "AND column_name LIKE 'fy%' ORDER BY ordinal_position").fetchall()]
    con.execute("CREATE OR REPLACE TABLE omc_fy_labels (fy_column VARCHAR, fy_label VARCHAR, fy_order INTEGER, is_partial_year BOOLEAN)")
    con.executemany("INSERT INTO omc_fy_labels VALUES (?, ?, ?, ?)",
                    [(c, *fy_label(c)[:1], i, fy_label(c)[1]) for i, c in enumerate(fy_cols, 1)])
    con.execute(f"""CREATE OR REPLACE TABLE chargers_omc_yearwise AS
        SELECT m.canonical_name AS state_name, l.fy_label, l.fy_order, l.is_partial_year,
               sum(u.installed)::INTEGER AS installed
        FROM (UNPIVOT stg_chargers_omc ON {", ".join(fy_cols)} INTO NAME fy_column VALUE installed) u
        JOIN omc_fy_labels l USING (fy_column)
        JOIN ref_state_mapping m ON m.source_name = u.state_raw
        GROUP BY ALL ORDER BY 1, 3""")
    con.execute("""CREATE OR REPLACE TABLE chargers_omc_summary AS
        SELECT m.canonical_name AS state_name, sum(decommissioned)::INTEGER AS decommissioned,
               sum(total_installed)::INTEGER AS total_installed, sum(total_operational)::INTEGER AS total_operational,
               string_agg(DISTINCT s.state_raw, ' + ') AS source_rows
        FROM stg_chargers_omc s JOIN ref_state_mapping m ON m.source_name = s.state_raw
        GROUP BY 1 ORDER BY 1""")
    for t in ("chargers_omc_yearwise", "chargers_omc_summary"):
        con.execute(f"COPY {t} TO '{sql_path(PROCESSED_DIR / (t + '.csv'))}' (HEADER)")
    log.info("chargers: %s states in snapshot (total %s); OMC %s states x %s FY columns",
             *con.execute("SELECT count(*), sum(public_charging_stations) FROM chargers_state_snapshot").fetchone(),
             con.execute("SELECT count(*) FROM chargers_omc_summary").fetchone()[0], len(fy_cols))
