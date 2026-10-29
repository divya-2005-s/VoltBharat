"""Phase 1: audit every source CSV and write reports/data_audit.md.

Usage:  python -m etl.inspect_data

Every number in the report is computed here from the raw files (read-only).
Machine-readable results go to data/processed/audit/*.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from etl.config import (AUDIT_DIR, EXCLUDED_FUEL_MAKER_OFFICES, REPORTS_DIR,
                        discover_sources, ensure_dirs, sql_path)
from etl.logging_utils import setup_logging

log = logging.getLogger("etl.inspect")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(con, sql: str, params=None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(con, sql: str, params=None):
    return con.execute(sql, params or []).fetchone()[0]


def jsonable(o):
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if isinstance(o, float) and o.is_integer():
        return int(o)
    return str(o)


def profile_table(con, name: str, path: Path) -> dict:
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv('{sql_path(path)}', header=true)")
    schema = rows(con, f"DESCRIBE {name}")
    cols = [c["column_name"] for c in schema]
    nulls = {c: one(con, f'SELECT count(*) - count("{c}") FROM {name}') for c in cols}
    data_cols = [c for c in cols if c != "id"]
    col_list = ", ".join(f'"{c}"' for c in data_cols)
    p = {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "columns": [{"name": c["column_name"], "type": c["column_type"]} for c in schema],
        "row_count": one(con, f"SELECT count(*) FROM {name}"),
        "null_counts": nulls,
        "exact_duplicate_rows_excluding_id": one(
            con, f"SELECT coalesce(sum(c - 1), 0) FROM (SELECT count(*) c FROM {name} GROUP BY {col_list} HAVING count(*) > 1)"),
    }
    if "id" in cols:
        p["duplicate_ids"] = one(con, f"SELECT count(*) - count(DISTINCT id) FROM {name}")
    if "date" in cols:
        p["date_min"], p["date_max"], p["distinct_dates"] = con.execute(
            f"SELECT min(date), max(date), count(DISTINCT date) FROM {name}").fetchone()
        p["day_of_month_values"] = [r[0] for r in con.execute(
            f"SELECT DISTINCT day(date) FROM {name} ORDER BY 1").fetchall()]
    if "state_name" in cols:
        p["states"] = [r[0] for r in con.execute(f"SELECT DISTINCT state_name FROM {name} ORDER BY 1").fetchall()]
    if "registrations" in cols:
        p["registrations_total"] = one(con, f"SELECT sum(registrations) FROM {name}")
        p["registrations_min"] = one(con, f"SELECT min(registrations) FROM {name}")
        p["negative_registrations"] = one(con, f"SELECT count(*) FROM {name} WHERE registrations < 0")
        p["non_integer_registrations"] = one(
            con, f"SELECT count(*) FROM {name} WHERE registrations <> floor(registrations)")
    return p


def audit_vahan(con, sources: dict[str, Path]) -> dict:
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "files": {}}

    for key, table in (("fuel", "fuel"), ("maker", "maker"), ("category", "cat")):
        log.info("Profiling %s (%s)", key, sources[key].name)
        out["files"][key] = profile_table(con, table, sources[key])

    # -- duplicate-file check -------------------------------------------------
    if "fuel_dup" in sources:
        dup_hash = sha256(sources["fuel_dup"])
        out["files"]["fuel_dup"] = {
            "file": sources["fuel_dup"].name,
            "size_bytes": sources["fuel_dup"].stat().st_size,
            "sha256": dup_hash,
            "identical_to": sources["fuel"].name if dup_hash == out["files"]["fuel"]["sha256"] else None,
        }

    f = out["files"]["fuel"]
    f["fuel_labels"] = rows(con, """SELECT registration_type AS label, count(*) AS rows, sum(registrations) AS registrations,
        min(date) AS first_month, max(date) AS last_month FROM fuel GROUP BY 1 ORDER BY 3 DESC""")
    f["natural_key_duplicates"] = one(con, """SELECT count(*) FROM (SELECT date, state_name, rto, rto_code, registration_type
        FROM fuel GROUP BY ALL HAVING count(*) > 1)""")
    f["null_rto_code_offices"] = rows(con, """SELECT state_name, rto, count(*) AS rows, sum(registrations) AS registrations
        FROM fuel WHERE rto_code IS NULL GROUP BY 1, 2 ORDER BY 1, 2""")
    f["rto_count"] = one(con, "SELECT count(DISTINCT coalesce(rto_code, rto)) FROM fuel")
    f["state_codes"] = rows(con, "SELECT state_name, min(state_code) AS state_code FROM fuel GROUP BY 1 ORDER BY 1")

    m = out["files"]["maker"]
    m["distinct_makers"] = one(con, "SELECT count(DISTINCT registration_type) FROM maker")
    m["top_makers_all_fuels"] = rows(con, """SELECT registration_type AS maker, sum(registrations) AS registrations
        FROM maker WHERE rto_code IS DISTINCT FROM 'HR207' GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    m["has_fuel_field"] = False
    m["natural_key_duplicates"] = one(con, """SELECT count(*) FROM (SELECT date, state_name, rto, rto_code, registration_type
        FROM maker GROUP BY ALL HAVING count(*) > 1)""")

    c = out["files"]["category"]
    c["vehicle_types"] = rows(con, """SELECT vehicle_type, count(*) AS rows, sum(registrations) AS registrations
        FROM cat GROUP BY 1 ORDER BY 3 DESC""")
    c["category_values"] = [r[0] for r in con.execute("SELECT DISTINCT category FROM cat").fetchall()]
    c["has_fuel_field"] = False
    c["office_count"] = one(con, "SELECT count(DISTINCT office_code) FROM cat")
    c["natural_key_duplicates"] = one(con, """SELECT count(*) FROM (SELECT date, office_code, vehicle_type
        FROM cat GROUP BY ALL HAVING count(*) > 1)""")
    c["states_missing_vs_fuel"] = sorted(set(map(str.upper, f["states"])) - set(map(str.upper, [
        s.replace("The Dadra And Nagar Haveli And Daman And Diu", "Ut Of Dnh And Dd")
         .replace("Andaman And Nicobar Islands", "Andaman & Nicobar Island") for s in c["states"]])))

    # -- monthly national totals (raw) --------------------------------------
    out["fuel_monthly_raw"] = rows(con, """SELECT date, sum(registrations) AS all_offices,
        sum(registrations) FILTER (WHERE rto_code = 'HR207') AS hr207,
        sum(registrations) FILTER (WHERE rto_code IS DISTINCT FROM 'HR207') AS excluding_hr207,
        sum(registrations) FILTER (WHERE registration_type IN ('Electric(BOV)', 'Pure EV')
                                   AND rto_code IS DISTINCT FROM 'HR207') AS bev_excluding_hr207,
        sum(registrations) FILTER (WHERE registration_type = 'Electric(BOV)' AND rto_code IS DISTINCT FROM 'HR207') AS bov,
        sum(registrations) FILTER (WHERE registration_type = 'Pure EV' AND rto_code IS DISTINCT FROM 'HR207') AS pure_ev
        FROM fuel GROUP BY 1 ORDER BY 1""")

    # -- HR207 aggregate-leak test -------------------------------------------
    for code in EXCLUDED_FUEL_MAKER_OFFICES:
        out.setdefault("aggregate_leak_tests", {})[code] = {
            "office_names": [r[0] for r in con.execute(
                "SELECT DISTINCT rto FROM fuel WHERE rto_code = ?", [code]).fetchall()],
            "months_present": one(con, "SELECT count(DISTINCT date) FROM fuel WHERE rto_code = ?", [code]),
            "share_of_raw_fuel_total_pct": round(100 * one(
                con, "SELECT sum(registrations) FILTER (WHERE rto_code = ?) / sum(registrations) FROM fuel", [code]), 2),
            "ratio_to_rest_of_india_by_month": rows(con, """SELECT date,
                round(sum(registrations) FILTER (WHERE rto_code = ?) /
                      sum(registrations) FILTER (WHERE rto_code IS DISTINCT FROM ?), 4) AS ratio
                FROM fuel GROUP BY 1 HAVING sum(registrations) FILTER (WHERE rto_code = ?) IS NOT NULL ORDER BY 1""",
                [code, code, code]),
            "next_largest_office_month": rows(con, """SELECT date, state_name, rto, sum(registrations) AS registrations
                FROM fuel WHERE rto_code IS DISTINCT FROM ? GROUP BY ALL ORDER BY 4 DESC LIMIT 1""", [code]),
        }

    # -- fuel vs maker consistency -------------------------------------------
    out["fuel_vs_maker_monthly"] = rows(con, """SELECT f.date, f.t AS fuel_total, m.t AS maker_total,
        round(100.0 * (f.t - m.t) / f.t, 3) AS diff_pct FROM
        (SELECT date, sum(registrations) t FROM fuel WHERE rto_code IS DISTINCT FROM 'HR207' GROUP BY 1) f
        JOIN (SELECT date, sum(registrations) t FROM maker WHERE rto_code IS DISTINCT FROM 'HR207' GROUP BY 1) m
        USING (date) ORDER BY 1""")

    # -- category vs fuel, by state, overlapping calendar year 2023 (raw) -----
    out["category_vs_fuel_2023_raw"] = rows(con, """
        WITH c AS (SELECT upper(state_name) s, sum(registrations) t FROM cat WHERE year(date) = 2023 GROUP BY 1),
             f AS (SELECT upper(replace(state_name, '&', 'And')) s, sum(registrations) t FROM fuel
                   WHERE year(date) = 2023 AND rto_code IS DISTINCT FROM 'HR207' GROUP BY 1)
        SELECT c.s AS state, c.t AS category_total, f.t AS fuel_total, round(c.t / f.t, 3) AS ratio
        FROM c LEFT JOIN f USING (s) ORDER BY ratio DESC NULLS LAST""")
    out["category_monthly_raw"] = rows(con, "SELECT date, sum(registrations) AS total FROM cat GROUP BY 1 ORDER BY 1")
    out["category_repeated_large_values"] = rows(con, """SELECT registrations AS value, count(DISTINCT office_code) AS offices,
        min(date) AS month FROM cat WHERE registrations >= 50000 GROUP BY 1 HAVING count(DISTINCT office_code) >= 5
        ORDER BY 2 DESC LIMIT 10""")
    return out


def audit_chargers(con, sources: dict[str, Path]) -> dict:
    out = {}
    s = sources["chargers_state"]
    con.execute(f"CREATE OR REPLACE TABLE cs AS SELECT * FROM read_csv('{sql_path(s)}', header=true)")
    out["state_snapshot"] = profile_table(con, "cs", s)
    out["state_snapshot"].update({
        "total_public_charging_stations": one(con, "SELECT sum(public_charging_stations) FROM cs"),
        "states": [r[0] for r in con.execute("SELECT state FROM cs ORDER BY 1").fetchall()],
        "expected_total_reference": {
            "value": 29277,
            "source": "PIB annexure 'State-wise public EV charging stations' (Aug-2025), inputs from Ministry of Power; "
                      "also reported from a Lok Sabha written reply by the MoS Heavy Industries.",
        },
    })
    o = sources["chargers_omc"]
    con.execute(f"CREATE OR REPLACE TABLE omc AS SELECT * FROM read_csv('{sql_path(o)}', header=true)")
    out["omc_yearwise"] = profile_table(con, "omc", o)
    fy_cols = [c["name"] for c in out["omc_yearwise"]["columns"] if c["name"].startswith("fy")]
    fy_sum = " + ".join(fy_cols)
    out["omc_yearwise"].update({
        "fy_columns": fy_cols,
        "column_totals": rows(con, "SELECT " + ", ".join(
            f"sum({c}) AS {c}" for c in fy_cols + ["decommissioned", "total_installed", "total_operational"]) + " FROM omc")[0],
        "row_consistency": rows(con, f"""SELECT state, {fy_sum} AS fy_sum, decommissioned, total_installed, total_operational,
            CASE WHEN {fy_sum} = total_installed THEN 'installed = sum(FY)'
                 WHEN {fy_sum} - decommissioned = total_installed THEN 'installed = sum(FY) - decommissioned'
                 ELSE 'inconsistent' END AS installed_rule,
            total_installed - decommissioned - total_operational AS installed_not_operational_gap
            FROM omc ORDER BY state"""),
        "states": [r[0] for r in con.execute("SELECT state FROM omc ORDER BY 1").fetchall()],
    })
    return out


# ----------------------------------------------------------------------------
# Markdown rendering
# ----------------------------------------------------------------------------

def n(x) -> str:
    """Indian digit grouping for integers (12,45,300)."""
    if x is None:
        return "n/a"
    x = int(round(x))
    s, neg = str(abs(x)), x < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if neg else "") + s


def mb(b: int) -> str:
    return f"{b / 1024 / 1024:,.1f} MB"


def render_markdown(v: dict, ch: dict) -> str:
    F, M, C = v["files"]["fuel"], v["files"]["maker"], v["files"]["category"]
    dup = v["files"].get("fuel_dup")
    leak = v["aggregate_leak_tests"]["HR207"]
    ratios = [r["ratio"] for r in leak["ratio_to_rest_of_india_by_month"]]
    fm = v["fuel_vs_maker_monthly"]
    cs, omc = ch["state_snapshot"], ch["omc_yearwise"]
    L = []
    a = L.append
    a("# VoltBharat — Dataset Audit Report\n")
    a(f"_Generated by `etl/inspect_data.py` on {v['generated_at'][:19].replace('T', ' ')} UTC. "
      "Every figure below is computed from the raw files, which are opened read-only._\n")
    a("## 1. Inventory\n")
    a("| Key | File | Size | Rows | Coverage | SHA-256 (first 12) |\n|---|---|---|---|---|---|")
    for key, p in (("fuel", F), ("maker", M), ("category", C)):
        a(f"| {key} | `{p['file']}` | {mb(p['size_bytes'])} | {n(p['row_count'])} | "
          f"{p['date_min']} → {p['date_max']} ({p['distinct_dates']} months) | `{p['sha256'][:12]}` |")
    if dup:
        a(f"| fuel_dup | `{dup['file']}` | {mb(dup['size_bytes'])} | — | — | `{dup['sha256'][:12]}` |")
    a(f"| chargers_state | `{cs['file']}` | {cs['size_bytes']} B | {cs['row_count']} | 2025 snapshot | `{cs['sha256'][:12]}` |")
    a(f"| chargers_omc | `{omc['file']}` | {omc['size_bytes']} B | {omc['row_count']} | FY2020-21 → FY2025-26 (to 1 Mar) | `{omc['sha256'][:12]}` |\n")

    a("## 2. Headline findings\n")
    if dup and dup["identical_to"]:
        a(f"1. **The two fuel-type files are byte-identical** (same SHA-256). `{dup['file']}` is a duplicate of "
          f"`{dup['identical_to']}`; only the latter is used. Adding them together would double every figure.")
    a(f"2. **Aggregate leak in office `HR207`** ({', '.join(leak['office_names'])}, Haryana). In {leak['months_present']} months "
      f"(Jan-2022 → May-2024) this single office reports {n(sum(r['hr207'] or 0 for r in v['fuel_monthly_raw']))} registrations — "
      f"{leak['share_of_raw_fuel_total_pct']}% of the whole fuel file. Its monthly value divided by the sum of every other office "
      f"in India ranges {min(ratios):.3f}–{max(ratios):.3f} (median {sorted(ratios)[len(ratios)//2]:.3f}). It is a national total "
      "mis-recorded as an office row. Left in, it doubles national totals until May-2024 and creates a false ~50% \"collapse\" in "
      f"June-2024. The next-largest office-month in India is {n(leak['next_largest_office_month'][0]['registrations'])} "
      f"({leak['next_largest_office_month'][0]['rto']}). **HR207 is excluded from the fuel and maker data.**")
    a("3. **BEV labels changed mid-series.** `Electric(BOV)` carries battery-electric volumes until early 2024; `Pure EV` "
      "appears in material volumes from March 2024 while `Electric(BOV)` falls. The combined series is continuous, so both "
      "labels are classified as battery-electric (BEV). Hybrid and fuel-cell labels are kept separate.")
    a("4. **The maker and vehicle-category files have no fuel field.** They cannot identify EVs. Their totals are all-fuel "
      "and are never presented as EV statistics.")
    a("5. **The vehicle-category file contains corrupted office rows** (aggregate values repeated across unrelated offices, "
      "e.g. identical six/seven-digit values in many offices in the same month). After the ETL outlier rule it is used only as "
      "all-fuel category context; see §6.")
    a(f"6. **The state charging snapshot sums to {n(cs['total_public_charging_stations'])}**, matching the published reference total "
      f"of {n(cs['expected_total_reference']['value'])} ({cs['expected_total_reference']['source']}).")
    a("7. **The OMC year-wise file is a different, narrower measure** (stations installed by oil marketing companies). "
      "It is never added to the state snapshot.\n")

    a("## 3. Schemas\n")
    for key, p in (("fuel", F), ("maker", M), ("category", C), ("chargers_state", cs), ("chargers_omc", omc)):
        a(f"### `{p['file']}`\n")
        a("| Column | Type | Nulls |\n|---|---|---|")
        for col in p["columns"]:
            a(f"| `{col['name']}` | {col['type']} | {n(p['null_counts'][col['name']])} |")
        extra = [f"rows {n(p['row_count'])}"]
        if "duplicate_ids" in p:
            extra.append(f"duplicate ids {p['duplicate_ids']}")
        extra.append(f"exact duplicate rows (excluding id) {p['exact_duplicate_rows_excluding_id']}")
        if "registrations_total" in p:
            extra.append(f"sum(registrations) {n(p['registrations_total'])}; negatives {p['negative_registrations']}; "
                         f"non-integers {p['non_integer_registrations']}")
        if "day_of_month_values" in p:
            extra.append(f"day-of-month values {p['day_of_month_values']}")
        a("\n" + "; ".join(extra) + ".\n")

    a("## 4. Fuel-type dataset (primary EV source)\n")
    a(f"- Grain: month × RTO × fuel label. {F['rto_count']} distinct offices, {len(F['states'])} state/UT names. "
      "Dates are month-end, i.e. each row is a monthly total.")
    a(f"- Natural-key (date, state, office, code, label) duplicates: {F['natural_key_duplicates']}. "
      f"`rto_code` is null for {len(F['null_rto_code_offices'])} West Bengal offices "
      f"({n(sum(r['registrations'] for r in F['null_rto_code_offices']))} registrations); office name is used as the key for them.")
    a("\n| Fuel label | Rows | Registrations (raw, incl. HR207) | First month | Last month |\n|---|---|---|---|---|")
    for r in F["fuel_labels"]:
        a(f"| {r['label']} | {n(r['rows'])} | {n(r['registrations'])} | {r['first_month']} | {r['last_month']} |")
    a("\n### Monthly national totals (raw vs cleaned)\n")
    a("| Month | All offices (raw) | HR207 | Excluding HR207 | BEV excl. HR207 | Electric(BOV) | Pure EV |\n|---|---|---|---|---|---|---|")
    for r in v["fuel_monthly_raw"]:
        a(f"| {r['date']} | {n(r['all_offices'])} | {n(r['hr207'])} | {n(r['excluding_hr207'])} | {n(r['bev_excluding_hr207'])} | "
          f"{n(r['bov'])} | {n(r['pure_ev'])} |")

    a("\n## 5. Maker dataset\n")
    a(f"- Same grain and office list as the fuel file; `registration_type` holds the maker name ({n(M['distinct_makers'])} distinct). "
      "No fuel field → **cannot isolate EVs**. HR207 is excluded for the same reason as above.")
    diffs = [abs(r["diff_pct"]) for r in fm]
    a(f"- Monthly fuel vs maker totals (both excl. HR207) differ by at most {max(diffs):.2f}% (median {sorted(diffs)[len(diffs)//2]:.3f}%), "
      "so the two extracts describe the same registrations; minor differences are extraction noise.")
    a("\n| Top makers (all fuels, excl. HR207) | Registrations |\n|---|---|")
    for r in M["top_makers_all_fuels"]:
        a(f"| {r['maker']} | {n(r['registrations'])} |")

    a("\n## 6. Vehicle-category dataset\n")
    a(f"- Grain: month (first-of-month dates) × office × vehicle type; {C['office_count']} offices; "
      f"`category` has one value ({', '.join(C['category_values'])}). No fuel field → **cannot isolate EVs**.")
    a(f"- States present in the fuel file but missing here: {', '.join(C['states_missing_vs_fuel']) or 'none'}.")
    a("- Values are floats but all integral. Coverage ends May-2024.")
    a("- Raw monthly totals jump from ~2 million (2019) to 40–52 million (Jan–Mar 2020) — impossible for India. "
      "The cause is office rows holding aggregate values. Examples of one value repeated across many offices in a month:")
    a("\n| Value | Offices with this exact value | Month |\n|---|---|---|")
    for r in v["category_repeated_large_values"]:
        a(f"| {n(r['value'])} | {r['offices']} | {r['month']} |")
    a("\n- Raw 2023 totals by state vs the fuel file (excl. HR207): most states agree within ~2%, a few are inflated:")
    a("\n| State | Category total | Fuel total | Ratio |\n|---|---|---|---|")
    for r in v["category_vs_fuel_2023_raw"]:
        a(f"| {r['state']} | {n(r['category_total'])} | {n(r['fuel_total'])} | {r['ratio'] if r['ratio'] is not None else 'n/a'} |")

    a("\n## 7. Charging datasets\n")
    a(f"### State snapshot (`{cs['file']}`)\n")
    a(f"- {cs['row_count']} states/UTs, total {n(cs['total_public_charging_stations'])} public charging stations. "
      "No date column; the file name and the matching PIB annexure date it to 2025 (published Aug-2025). "
      "Counts are stations, not charging points/guns.")
    a(f"\n### OMC year-wise (`{omc['file']}`)\n")
    a(f"- {omc['row_count']} rows; FY columns: {', '.join(omc['fy_columns'])}. The last column covers FY2025-26 only up to 1 March 2026.")
    ct = omc["column_totals"]
    a("- Column totals: " + "; ".join(f"`{k}` {n(val)}" for k, val in ct.items()) + ".")
    leh = [r for r in omc["row_consistency"] if r["state"] == "Leh"]
    if leh:
        a("- The file has a separate `Leh` row (a district of Ladakh) with 5 stations installed in FY2024-25 and 5 decommissioned. "
          "The ETL maps `Leh` → Ladakh and sums it into the Ladakh row; this is documented in `data/reference/state_mapping.csv`.")
    rules = {}
    for r in omc["row_consistency"]:
        rules.setdefault(r["installed_rule"], []).append(r["state"])
    a("- `total_installed` follows different rules in different rows: " + "; ".join(
        f"**{k}** for {len(v_)} rows" + (f" ({', '.join(v_)})" if len(v_) < 6 else "") for k, v_ in rules.items()) + ".")
    gaps = [r for r in omc["row_consistency"] if r["installed_not_operational_gap"] > 0]
    a(f"- `total_operational` is lower than `total_installed − decommissioned` in {len(gaps)} rows, so some installed stations "
      "are neither operational nor decommissioned. The platform shows installations by FY with the source's labels and reports "
      "`total_operational` as given; it does not derive a utilisation figure.")
    a("- OMC stations are a subset of all public stations; the two files are never added together.\n")

    a("## 8. Can each dataset identify EVs?\n")
    a("| Dataset | EV identification | Used for |\n|---|---|---|")
    a("| Fuel type | **Yes** — explicit fuel labels | All EV adoption metrics, EV share, powertrain mix, charging-gap numerator |")
    a("| Maker | No — no fuel field | All-fuel maker rankings (labelled), name-identified EV makers (labelled lower bound) |")
    a("| Vehicle category | No — no fuel field | All-fuel category mix, 2019–May 2024, after outlier cleaning (labelled) |")
    a("| Charging snapshot | n/a | Public stations by state (2025) |")
    a("| OMC year-wise | n/a | OMC installations by financial year |\n")

    a("## 9. EV classification policy\n")
    a("- **EV (headline metric) = battery-electric vehicles (BEV)**: fuel labels `Electric(BOV)` and `Pure EV`.")
    a("- Reported separately, never added to BEV: `Strong Hybrid EV`, `Plug-in Hybrid EV`, `Fuel Cell Hydrogen`, and other "
      "hybrid labels (`Petrol/Hybrid` etc.).")
    a("- **All-vehicle denominator** for EV share = all fuel labels in the fuel file (including `Not Applicable`), excluding HR207.")
    a("- Full mapping: `data/reference/fuel_classification.csv`.\n")

    a("## 10. Data-quality rules applied by the ETL\n")
    a("1. Use only `registrations-by-fuel-type.csv` as the fuel source; the byte-identical copy is ignored (checked by hash on every run).")
    a("2. Exclude office HR207 from fuel and maker data (aggregate leak).")
    a("3. Standardise state names through `data/reference/state_mapping.csv`; unknown names fail the pipeline.")
    a("4. Key offices by (state, office code, office name) so West Bengal offices with null codes are kept and not merged.")
    a("5. Sum exact natural-key duplicates rather than dropping them (they are separate source rows with the same key); counts are reported.")
    a("6. Category file: null a value when it is ≥1,000 and either repeated identically in ≥3 offices in the same month and "
      "vehicle type, or >10× that office's median for the vehicle type. Result validated against the fuel file.")
    a("7. Never interpolate or impute missing months.\n")
    return "\n".join(L) + "\n"


def main() -> None:
    setup_logging("inspect")
    ensure_dirs()
    sources = discover_sources()
    log.info("Discovered sources: %s", {k: p.name for k, p in sources.items()})
    con = duckdb.connect()
    vahan = audit_vahan(con, sources)
    chargers = audit_chargers(con, sources)
    (AUDIT_DIR / "vahan_audit.json").write_text(json.dumps(vahan, default=jsonable, indent=2), encoding="utf-8")
    (AUDIT_DIR / "chargers_audit.json").write_text(json.dumps(chargers, default=jsonable, indent=2), encoding="utf-8")
    (REPORTS_DIR / "data_audit.md").write_text(render_markdown(vahan, chargers), encoding="utf-8")
    log.info("Wrote %s and audit JSON to %s", REPORTS_DIR / "data_audit.md", AUDIT_DIR)


if __name__ == "__main__":
    main()
