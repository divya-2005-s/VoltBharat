"""Extract the VAHAN CSVs into standardised staging tables (DuckDB).

Output: data/processed/staging.duckdb with tables
  stg_fuel, stg_maker, stg_category  -- office-level rows, standardised columns
  ref_state_mapping, ref_fuel_class  -- reference tables
Raw CSVs are only read. The staging database is rebuilt on every run.
"""
from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from etl.config import (EXCLUDED_FUEL_MAKER_OFFICES, PROCESSED_DIR, REFERENCE_DIR,
                        discover_sources, sql_path)

log = logging.getLogger("etl.extract")
STAGING_DB = PROCESSED_DIR / "staging.duckdb"


class UnknownStateError(ValueError):
    pass


def connect_staging(path: Path = STAGING_DB) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def load_reference(con) -> None:
    con.execute(f"""CREATE OR REPLACE TABLE ref_state_mapping AS
        SELECT trim(source_name) AS source_name, trim(canonical_name) AS canonical_name
        FROM read_csv('{sql_path(REFERENCE_DIR / "state_mapping.csv")}', header=true, all_varchar=true)""")
    con.execute(f"""CREATE OR REPLACE TABLE ref_states AS
        SELECT * FROM read_csv('{sql_path(REFERENCE_DIR / "states.csv")}', header=true, all_varchar=true)""")
    con.execute(f"""CREATE OR REPLACE TABLE ref_fuel_class AS
        SELECT fuel_label, fuel_class, is_bev::BOOLEAN AS is_bev
        FROM read_csv('{sql_path(REFERENCE_DIR / "fuel_classification.csv")}', header=true, all_varchar=true)""")
    con.execute("CREATE OR REPLACE TABLE ref_excluded_offices (office_code VARCHAR, reason VARCHAR)")
    con.executemany("INSERT INTO ref_excluded_offices VALUES (?, ?)", list(EXCLUDED_FUEL_MAKER_OFFICES.items()))
    bad = con.execute("""SELECT DISTINCT canonical_name FROM ref_state_mapping
        WHERE canonical_name NOT IN (SELECT state_name FROM ref_states)""").fetchall()
    if bad:
        raise UnknownStateError(f"state_mapping.csv maps to names missing from states.csv: {bad}")


def assert_states_mapped(con, table: str, column: str = "state_raw") -> None:
    unknown = con.execute(f"""SELECT DISTINCT {column} FROM {table}
        WHERE {column} NOT IN (SELECT source_name FROM ref_state_mapping)""").fetchall()
    if unknown:
        raise UnknownStateError(
            f"{table}: state names not in data/reference/state_mapping.csv: {[u[0] for u in unknown]}. "
            "Add them to the mapping file and rerun.")


def extract_rto_dataset(con, table: str, path: Path, label_col: str) -> None:
    """Fuel and maker files share a schema: id,date,state_name,state_code,rto,rto_code,registration_type,registrations."""
    con.execute(f"""CREATE OR REPLACE TABLE {table} AS
        SELECT
            id::BIGINT                              AS source_id,
            CAST(date AS DATE)                      AS source_date,
            date_trunc('month', CAST(date AS DATE))::DATE AS month,
            trim(state_name)                        AS state_raw,
            trim(rto)                               AS office_name,
            nullif(trim(rto_code), '')              AS office_code,
            trim(registration_type)                 AS {label_col},
            registrations::BIGINT                   AS registrations,
            coalesce(nullif(trim(rto_code), ''), '') IN (SELECT office_code FROM ref_excluded_offices) AS is_excluded
        FROM read_csv('{sql_path(path)}', header=true,
                      columns={{'id':'BIGINT','date':'VARCHAR','state_name':'VARCHAR','state_code':'VARCHAR',
                               'rto':'VARCHAR','rto_code':'VARCHAR','registration_type':'VARCHAR','registrations':'BIGINT'}})
    """)
    assert_states_mapped(con, table)
    con.execute(f"""ALTER TABLE {table} ADD COLUMN state_name VARCHAR;
        UPDATE {table} t SET state_name = m.canonical_name FROM ref_state_mapping m WHERE m.source_name = t.state_raw;""")
    log.info("%s: %s rows (%s excluded office rows)", table,
             *con.execute(f"SELECT count(*), count(*) FILTER (WHERE is_excluded) FROM {table}").fetchone())


def extract_category(con, path: Path) -> None:
    con.execute(f"""CREATE OR REPLACE TABLE stg_category AS
        SELECT
            id::BIGINT                   AS source_id,
            CAST(date AS DATE)           AS source_date,
            date_trunc('month', CAST(date AS DATE))::DATE AS month,
            trim(state_name)             AS state_raw,
            trim(office_name)            AS office_name,
            trim(office_code)            AS office_code,
            trim(vehicle_type)           AS vehicle_type,
            registrations::DOUBLE        AS registrations
        FROM read_csv('{sql_path(path)}', header=true,
                      columns={{'id':'BIGINT','date':'VARCHAR','state_name':'VARCHAR','state_code':'VARCHAR',
                               'office_name':'VARCHAR','office_code':'VARCHAR','vehicle_type':'VARCHAR',
                               'category':'VARCHAR','registrations':'DOUBLE'}})
    """)
    assert_states_mapped(con, "stg_category")
    con.execute("""ALTER TABLE stg_category ADD COLUMN state_name VARCHAR;
        UPDATE stg_category t SET state_name = m.canonical_name FROM ref_state_mapping m WHERE m.source_name = t.state_raw;""")
    log.info("stg_category: %s rows", con.execute("SELECT count(*) FROM stg_category").fetchone()[0])


def run(con=None, sources: dict[str, Path] | None = None) -> dict[str, Path]:
    sources = sources or discover_sources()
    own = con is None
    con = con or connect_staging()
    try:
        load_reference(con)
        extract_rto_dataset(con, "stg_fuel", sources["fuel"], "fuel_label")
        unknown_fuel = con.execute("""SELECT DISTINCT fuel_label FROM stg_fuel
            WHERE fuel_label NOT IN (SELECT fuel_label FROM ref_fuel_class)""").fetchall()
        if unknown_fuel:
            raise ValueError(f"Fuel labels missing from fuel_classification.csv: {[u[0] for u in unknown_fuel]}")
        extract_rto_dataset(con, "stg_maker", sources["maker"], "maker")
        extract_category(con, sources["category"])
    finally:
        if own:
            con.close()
    return sources
