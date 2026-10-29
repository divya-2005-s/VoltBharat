"""Validate processed outputs against the raw sources.

Each check yields status 'pass', 'warn' or 'fail'. Any 'fail' stops the
pipeline before the database is loaded.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from etl.config import PROCESSED_DIR, discover_sources
from etl.inspect_data import sha256

log = logging.getLogger("etl.validate")
EXPECTED_STATE_CHARGER_TOTAL = 29277  # PIB annexure, Aug-2025
FIRST_MONTH, LAST_MONTH = "2022-01-01", "2026-09-01"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    data: dict = field(default_factory=dict)


def _one(con, sql, params=None):
    return con.execute(sql, params or []).fetchone()[0]


def run(con, sources: dict[str, Path] | None = None, out_dir: Path = PROCESSED_DIR) -> list[Check]:
    sources = sources or discover_sources()
    checks: list[Check] = []

    def add(name, ok, detail, data=None, warn_only=False):
        status = "pass" if ok else ("warn" if warn_only else "fail")
        checks.append(Check(name, status, detail, data or {}))
        log.log(logging.INFO if ok else logging.WARNING, "[%s] %s: %s", status.upper(), name, detail)

    # 1. duplicate fuel file
    if "fuel_dup" in sources:
        same = sha256(sources["fuel"]) == sha256(sources["fuel_dup"])
        add("fuel_files_duplicate_detected", True,
            f"{sources['fuel_dup'].name} is {'byte-identical to' if same else 'DIFFERENT from'} {sources['fuel'].name}; "
            f"only {sources['fuel'].name} is used.", {"identical": same})

    # 2-4. reconciliation raw -> processed
    raw = _one(con, "SELECT sum(registrations) FROM stg_fuel WHERE NOT is_excluded")
    proc = _one(con, "SELECT sum(registrations) FROM fuel_state_month")
    excl = _one(con, "SELECT coalesce(sum(registrations), 0) FROM stg_fuel WHERE is_excluded")
    add("fuel_total_reconciles", raw == proc,
        f"raw (excl. HR207) {raw:,} = processed {proc:,}; excluded HR207 rows {excl:,}", {"raw": raw, "processed": proc, "excluded": excl})
    mism = con.execute("""SELECT s.fuel_label, s.t, p.t FROM
        (SELECT fuel_label, sum(registrations) t FROM stg_fuel WHERE NOT is_excluded GROUP BY 1) s
        FULL JOIN (SELECT fuel_label, sum(registrations) t FROM fuel_state_month GROUP BY 1) p USING (fuel_label)
        WHERE s.t IS DISTINCT FROM p.t""").fetchall()
    add("fuel_label_totals_reconcile", not mism, f"{len(mism)} fuel labels differ between raw and processed", {"mismatches": mism})

    raw_m = _one(con, "SELECT sum(registrations) FROM stg_maker WHERE NOT is_excluded")
    proc_m = _one(con, "SELECT sum(registrations) FROM maker_state_month")
    add("maker_total_reconciles", raw_m == proc_m, f"raw (excl. HR207) {raw_m:,} = processed {proc_m:,}")

    raw_c = _one(con, "SELECT sum(registrations) FROM stg_category")
    proc_raw_c = _one(con, "SELECT sum(registrations_raw) FROM category_state_month")
    clean_c = _one(con, "SELECT sum(registrations) FROM category_state_month")
    out_c = _one(con, "SELECT sum(registrations) FROM category_outliers")
    add("category_total_reconciles", abs(raw_c - proc_raw_c) < 0.5 and abs(clean_c + out_c - raw_c) < 0.5,
        f"raw {raw_c:,.0f} = clean {clean_c:,.0f} + removed outliers {out_c:,.0f}")

    # 5. excluded office absent from outputs; states canonical
    top_share = con.execute("""SELECT state_name, month, round(100 * t / sum(t) OVER (PARTITION BY month), 2) s FROM
        (SELECT state_name, month, sum(registrations) t FROM fuel_state_month GROUP BY 1, 2) ORDER BY s DESC LIMIT 1""").fetchone()
    add("no_aggregate_leak_in_states", top_share[2] < 40,
        f"largest single state share of a national month is {top_share[2]}% ({top_share[0]}, {top_share[1]}); "
        "an aggregate leak would push this near 50%")
    unknown = con.execute("""SELECT DISTINCT state_name FROM (
            SELECT state_name FROM fuel_state_month UNION SELECT state_name FROM maker_state_month
            UNION SELECT state_name FROM category_state_month UNION SELECT state_name FROM chargers_state_snapshot
            UNION SELECT state_name FROM chargers_omc_summary)
        WHERE state_name IS NULL OR state_name NOT IN (SELECT state_name FROM ref_states)""").fetchall()
    add("states_canonical", not unknown, f"{len(unknown)} non-canonical state names in outputs", {"unknown": unknown})
    n_fuel_states = _one(con, "SELECT count(DISTINCT state_name) FROM fuel_state_month")
    add("fuel_state_coverage", n_fuel_states == 36, f"{n_fuel_states}/36 states and UTs present in fuel data", warn_only=True)

    # 6. negatives
    neg = _one(con, """SELECT (SELECT count(*) FROM stg_fuel WHERE registrations < 0) +
                              (SELECT count(*) FROM stg_maker WHERE registrations < 0) +
                              (SELECT count(*) FROM stg_category WHERE registrations < 0)""")
    add("no_negative_registrations", neg == 0, f"{neg} negative registration values")

    # 7. month continuity
    missing_nat = con.execute(f"""SELECT m::DATE FROM generate_series(DATE '{FIRST_MONTH}', DATE '{LAST_MONTH}', INTERVAL 1 MONTH) g(m)
        WHERE m::DATE NOT IN (SELECT DISTINCT month FROM fuel_state_month)""").fetchall()
    add("fuel_months_continuous", not missing_nat, f"{len(missing_nat)} missing national months in {FIRST_MONTH}..{LAST_MONTH}")
    gaps = con.execute(f"""SELECT state_name, count(*) FROM (
            SELECT s.state_name, g.m FROM (SELECT DISTINCT state_name FROM fuel_state_month) s,
                   generate_series(DATE '{FIRST_MONTH}', DATE '{LAST_MONTH}', INTERVAL 1 MONTH) g(m)
            EXCEPT SELECT state_name, month FROM fuel_state_month) GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    add("fuel_state_months_complete", not gaps,
        f"{len(gaps)} states have months with no rows (not imputed): {gaps}", {"gaps": gaps}, warn_only=True)

    # 8. fuel vs maker
    worst = con.execute("""SELECT f.month, round(100 * abs(f.t - m.t) / f.t, 3) FROM
        (SELECT month, sum(registrations) t FROM fuel_state_month GROUP BY 1) f JOIN
        (SELECT month, sum(registrations) t FROM maker_state_month GROUP BY 1) m USING (month) ORDER BY 2 DESC LIMIT 1""").fetchone()
    add("fuel_vs_maker_within_2pct", worst[1] <= 2.0, f"largest monthly gap {worst[1]}% ({worst[0]})", warn_only=True)

    # 9. BEV series continuity across the label switch
    bev = con.execute("""SELECT month, sum(registrations) FILTER (WHERE is_bev) b FROM fuel_state_month
        WHERE month BETWEEN DATE '2024-01-01' AND DATE '2024-08-01' GROUP BY 1 ORDER BY 1""").fetchall()
    add("bev_series_spans_label_change", all(b > 0 for _, b in bev),
        "BEV (Electric(BOV) + Pure EV) monthly 2024-01..2024-08: " + ", ".join(f"{m:%b}:{b:,}" for m, b in bev))

    # 10. chargers
    tot = _one(con, "SELECT sum(public_charging_stations) FROM chargers_state_snapshot")
    add("charger_snapshot_total", tot == EXPECTED_STATE_CHARGER_TOTAL,
        f"state snapshot total {tot:,} vs published {EXPECTED_STATE_CHARGER_TOTAL:,}", warn_only=True)
    n_ch = _one(con, "SELECT count(*) FROM chargers_state_snapshot")
    add("charger_snapshot_states", n_ch == 36, f"{n_ch}/36 states in charger snapshot", warn_only=True)
    omc = con.execute("""SELECT y.state_name, sum(y.installed) fy, s.decommissioned, s.total_installed
        FROM chargers_omc_yearwise y JOIN chargers_omc_summary s USING (state_name)
        GROUP BY ALL HAVING sum(y.installed) <> s.total_installed ORDER BY 1""").fetchall()
    add("omc_fy_sum_matches_total_installed", not omc,
        f"{len(omc)} states where sum(FY installs) <> total_installed (source uses net-of-decommissioned totals there)",
        {"states": omc}, warn_only=True)

    # 11. category usability
    ok_states, all_states = con.execute(
        "SELECT count(*) FILTER (WHERE within_5pct), count(*) FROM category_state_check").fetchone()
    add("category_states_validated", ok_states == all_states,
        f"{ok_states}/{all_states} states' cleaned category totals within 5% of fuel totals (Jan-2022..May-2024); "
        "others are flagged state_validated=false", warn_only=True)

    report = {"checks": [asdict(c) for c in checks],
              "summary": {s: sum(c.status == s for c in checks) for s in ("pass", "warn", "fail")}}
    (out_dir / "validation_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return checks
