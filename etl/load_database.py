"""Load validated processed outputs into PostgreSQL.

Usage: python -m etl.load_database   (or python -m etl.run_pipeline --load-db)

Idempotent full refresh: dimensions are upserted, and the VoltBharat fact
tables are replaced inside ONE transaction. If anything fails the transaction
rolls back and the previous data remains intact. Only VoltBharat's own tables
are touched.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime, timezone

import duckdb

from etl.config import AUDIT_DIR, PROCESSED_DIR, REFERENCE_DIR, sql_path
from etl.db import get_engine, safe_url
from etl.init_db import apply_sql
from etl.source_catalog import CATALOG

log = logging.getLogger("etl.load")
FACT_TABLES = ("fact_registrations_fuel", "fact_registrations_maker", "fact_registrations_segment",
               "fact_chargers", "fact_chargers_omc_fy", "fact_chargers_omc_status")


def date_rows(first: date, last: date):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        fy = y if m >= 4 else y - 1
        yield (y * 100 + m, date(y, m, 1), y, m, (m - 1) // 3 + 1, fy, f"FY{fy}-{str(fy + 1)[2:]}",
               date(y, m, 1).strftime("%b %Y"))
        m += 1
        if m > 12:
            y, m = y + 1, 1


def read_csv_dicts(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def source_rows(processed_at: datetime):
    audit = json.loads((AUDIT_DIR / "vahan_audit.json").read_text(encoding="utf-8"))
    ch = json.loads((AUDIT_DIR / "chargers_audit.json").read_text(encoding="utf-8"))
    profiles = {"fuel": audit["files"]["fuel"], "maker": audit["files"]["maker"],
                "category": audit["files"]["category"], "fuel_dup": audit["files"].get("fuel_dup"),
                "chargers_state": ch["state_snapshot"], "chargers_omc": ch["omc_yearwise"]}
    coverage_labels = {"chargers_state": "2025 snapshot", "chargers_omc": "FY2020-21 to FY2025-26 (up to 1 Mar 2026)"}
    for key, meta in CATALOG.items():
        p = profiles.get(key)
        if not p:
            continue
        start, end = p.get("date_min"), p.get("date_max")
        label = coverage_labels.get(key) or (f"{start[:7]} to {end[:7]}" if start else "same as fuel")
        yield dict(source_key=key, file_name=p["file"], coverage_start=start, coverage_end=end, coverage_label=label,
                   row_count=p.get("row_count"), size_bytes=p["size_bytes"], sha256=p["sha256"],
                   processed_at=processed_at, **meta)


def copy_rows(cur, table: str, columns: list[str], rows) -> int:
    n = 0
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
        for r in rows:
            cp.write_row(r)
            n += 1
    return n


def run(started_at: datetime | None = None, checks=None) -> dict:
    started_at = started_at or datetime.now(timezone.utc)
    engine = get_engine()
    log.info("Loading into %s", safe_url())
    apply_sql(engine)
    duck = duckdb.connect()

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("INSERT INTO etl_runs (started_at, status) VALUES (%s, 'running') RETURNING run_id", (started_at,))
        run_id = cur.fetchone()[0]
        raw.commit()

        counts: dict[str, int] = {}
        try:
            # ---- dimensions (upsert) -------------------------------------
            states = read_csv_dicts(REFERENCE_DIR / "states.csv")
            cur.executemany("""INSERT INTO dim_state (state_name, state_code, state_type, region) VALUES (%s, %s, %s, %s)
                ON CONFLICT (state_name) DO UPDATE SET state_code = EXCLUDED.state_code,
                state_type = EXCLUDED.state_type, region = EXCLUDED.region""",
                [(s["state_name"], s["state_code"], s["state_type"], s["region"]) for s in states])
            cur.executemany("""INSERT INTO dim_date VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date_id) DO NOTHING""", list(date_rows(date(2019, 1, 1), date(2026, 12, 1))))
            fuels = read_csv_dicts(REFERENCE_DIR / "fuel_classification.csv")
            cur.executemany("""INSERT INTO dim_fuel (fuel_label, fuel_class, is_bev) VALUES (%s, %s, %s)
                ON CONFLICT (fuel_label) DO UPDATE SET fuel_class = EXCLUDED.fuel_class, is_bev = EXCLUDED.is_bev""",
                [(f["fuel_label"], f["fuel_class"], f["is_bev"].lower() == "true") for f in fuels])
            makers = duck.execute(f"""SELECT maker, bool_or(name_identified_ev_maker) FROM
                read_parquet('{sql_path(PROCESSED_DIR / "maker_state_month.parquet")}') GROUP BY 1""").fetchall()
            cur.executemany("""INSERT INTO dim_maker (maker_name, name_identified_ev_maker) VALUES (%s, %s)
                ON CONFLICT (maker_name) DO UPDATE SET name_identified_ev_maker = EXCLUDED.name_identified_ev_maker""", makers)
            vtypes = duck.execute(f"""SELECT DISTINCT vehicle_type FROM
                read_parquet('{sql_path(PROCESSED_DIR / "category_state_month.parquet")}')""").fetchall()
            cur.executemany("INSERT INTO dim_vehicle_type (vehicle_type) VALUES (%s) ON CONFLICT DO NOTHING", vtypes)

            for s in source_rows(started_at):
                cols = list(s)
                cur.execute(f"""INSERT INTO data_sources ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})
                    ON CONFLICT (source_key) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in cols if c != 'source_key')}""",
                    [s[c] for c in cols])
            events = read_csv_dicts(REFERENCE_DIR / "policy_events.csv")
            cur.executemany("""INSERT INTO policy_events VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET name = EXCLUDED.name, short_name = EXCLUDED.short_name,
                start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date, event_type = EXCLUDED.event_type,
                description = EXCLUDED.description, source = EXCLUDED.source""",
                [(e["event_id"], e["name"], e["short_name"], e["start_date"], e["end_date"] or None,
                  e["event_type"], e["description"], e["source"]) for e in events])

            # ---- facts (replace in-transaction) --------------------------
            for t in FACT_TABLES:
                cur.execute(f"DELETE FROM {t}")

            cur.execute("CREATE TEMP TABLE tmp_fuel (month DATE, state_name TEXT, fuel_label TEXT, registrations BIGINT, source_rows INT) ON COMMIT DROP")
            copy_rows(cur, "tmp_fuel", ["month", "state_name", "fuel_label", "registrations", "source_rows"], duck.execute(
                f"SELECT month, state_name, fuel_label, registrations, source_rows FROM read_parquet('{sql_path(PROCESSED_DIR / 'fuel_state_month.parquet')}')").fetchall())
            cur.execute("""INSERT INTO fact_registrations_fuel (date_id, state_id, fuel_id, registrations, source_rows)
                SELECT d.date_id, s.state_id, f.fuel_id, t.registrations, t.source_rows FROM tmp_fuel t
                JOIN dim_date d ON d.month_start = t.month JOIN dim_state s USING (state_name) JOIN dim_fuel f USING (fuel_label)""")
            counts["fact_registrations_fuel"] = cur.rowcount

            cur.execute("CREATE TEMP TABLE tmp_maker (month DATE, state_name TEXT, maker TEXT, registrations BIGINT) ON COMMIT DROP")
            copy_rows(cur, "tmp_maker", ["month", "state_name", "maker", "registrations"], duck.execute(
                f"SELECT month, state_name, maker, registrations FROM read_parquet('{sql_path(PROCESSED_DIR / 'maker_state_month.parquet')}')").fetchall())
            cur.execute("""INSERT INTO fact_registrations_maker (date_id, state_id, maker_id, registrations)
                SELECT d.date_id, s.state_id, m.maker_id, t.registrations FROM tmp_maker t
                JOIN dim_date d ON d.month_start = t.month JOIN dim_state s USING (state_name)
                JOIN dim_maker m ON m.maker_name = t.maker""")
            counts["fact_registrations_maker"] = cur.rowcount

            cur.execute("""CREATE TEMP TABLE tmp_seg (month DATE, state_name TEXT, vehicle_type TEXT, registrations BIGINT,
                registrations_raw BIGINT, outlier_rows INT, state_validated BOOLEAN) ON COMMIT DROP""")
            copy_rows(cur, "tmp_seg", ["month", "state_name", "vehicle_type", "registrations", "registrations_raw", "outlier_rows", "state_validated"],
                      duck.execute(f"""SELECT month, state_name, vehicle_type, registrations, registrations_raw, outlier_rows,
                      coalesce(state_validated, false) FROM read_parquet('{sql_path(PROCESSED_DIR / 'category_state_month.parquet')}')""").fetchall())
            cur.execute("""INSERT INTO fact_registrations_segment
                SELECT d.date_id, s.state_id, v.vehicle_type_id, t.registrations, t.registrations_raw, t.outlier_rows, t.state_validated
                FROM tmp_seg t JOIN dim_date d ON d.month_start = t.month JOIN dim_state s USING (state_name)
                JOIN dim_vehicle_type v USING (vehicle_type)""")
            counts["fact_registrations_segment"] = cur.rowcount

            snap = read_csv_dicts(PROCESSED_DIR / "chargers_state_snapshot.csv")
            cur.executemany("""INSERT INTO fact_chargers (state_id, source_id, snapshot_label, public_charging_stations)
                SELECT s.state_id, ds.source_id, %s, %s FROM dim_state s, data_sources ds
                WHERE s.state_name = %s AND ds.source_key = 'chargers_state'""",
                [("2025", int(r["public_charging_stations"]), r["state_name"]) for r in snap])
            counts["fact_chargers"] = len(snap)

            omc = read_csv_dicts(PROCESSED_DIR / "chargers_omc_yearwise.csv")
            cur.executemany("""INSERT INTO fact_chargers_omc_fy SELECT s.state_id, %s, %s, %s, %s FROM dim_state s WHERE s.state_name = %s""",
                [(r["fy_label"], int(r["fy_order"]), r["is_partial_year"].lower() == "true", int(r["installed"]), r["state_name"]) for r in omc])
            counts["fact_chargers_omc_fy"] = len(omc)
            st = read_csv_dicts(PROCESSED_DIR / "chargers_omc_summary.csv")
            cur.executemany("""INSERT INTO fact_chargers_omc_status SELECT s.state_id, %s, %s, %s, %s FROM dim_state s WHERE s.state_name = %s""",
                [(int(r["decommissioned"]), int(r["total_installed"]), int(r["total_operational"]), r["source_rows"], r["state_name"]) for r in st])
            counts["fact_chargers_omc_status"] = len(st)

            # Reconcile loaded totals with processed files before committing.
            cur.execute("SELECT sum(registrations) FROM fact_registrations_fuel")
            db_fuel = cur.fetchone()[0]
            file_fuel = duck.execute(f"SELECT sum(registrations) FROM read_parquet('{sql_path(PROCESSED_DIR / 'fuel_state_month.parquet')}')").fetchone()[0]
            if db_fuel != file_fuel:
                raise RuntimeError(f"Loaded fuel total {db_fuel} != processed total {file_fuel}")
            cur.execute("SELECT sum(registrations) FROM fact_registrations_maker")
            db_maker = cur.fetchone()[0]
            file_maker = duck.execute(f"SELECT sum(registrations) FROM read_parquet('{sql_path(PROCESSED_DIR / 'maker_state_month.parquet')}')").fetchone()[0]
            if db_maker != file_maker:
                raise RuntimeError(f"Loaded maker total {db_maker} != processed total {file_maker}")

            validation = [{"name": c.name, "status": c.status, "detail": c.detail} for c in (checks or [])]
            if not validation and (PROCESSED_DIR / "validation_report.json").exists():
                validation = [{k: c[k] for k in ("name", "status", "detail")} for c in
                              json.loads((PROCESSED_DIR / "validation_report.json").read_text(encoding="utf-8"))["checks"]]
            cur.execute("""UPDATE etl_runs SET status = 'success', finished_at = now(), rows_loaded = %s, validation = %s
                WHERE run_id = %s""", (json.dumps(counts), json.dumps(validation), run_id))
            raw.commit()
        except Exception as exc:
            raw.rollback()
            cur.execute("UPDATE etl_runs SET status = 'failed', finished_at = now(), message = %s WHERE run_id = %s",
                        (f"{exc.__class__.__name__}: {exc}"[:2000], run_id))
            raw.commit()
            raise
    finally:
        raw.close()
        duck.close()
    log.info("Loaded rows: %s", counts)
    return counts


if __name__ == "__main__":
    from etl.logging_utils import setup_logging
    setup_logging("load")
    run()
