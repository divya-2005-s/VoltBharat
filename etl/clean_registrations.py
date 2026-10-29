"""Aggregate staged VAHAN rows to compact state x month outputs.

Outputs (data/processed/):
  fuel_state_month.parquet/.csv      month, state, fuel label/class, registrations (EV source of truth)
  maker_state_month.parquet          month, state, maker, registrations (ALL fuels)
  category_state_month.parquet/.csv  month, state, vehicle type, cleaned + raw registrations (ALL fuels)
  category_outliers.csv              every category value nulled by the outlier rule, with the reason
"""
from __future__ import annotations

import logging

from etl.config import (CATEGORY_REPEAT_MIN_OFFICES, CATEGORY_REPEAT_MIN_VALUE,
                        CATEGORY_SPIKE_MIN_VALUE, CATEGORY_SPIKE_MULTIPLE,
                        EV_MAKER_NAME_PATTERN, PROCESSED_DIR, sql_path)

log = logging.getLogger("etl.clean_registrations")


def export(con, table: str, name: str, csv: bool = True) -> None:
    con.execute(f"COPY {table} TO '{sql_path(PROCESSED_DIR / (name + '.parquet'))}' (FORMAT parquet)")
    if csv:
        con.execute(f"COPY {table} TO '{sql_path(PROCESSED_DIR / (name + '.csv'))}' (HEADER, DELIMITER ',')")


def build_fuel(con) -> None:
    # Natural-key duplicates (same month/office/label twice) are summed: they are
    # distinct source rows, and the aggregation below is to state level anyway.
    con.execute("""CREATE OR REPLACE TABLE fuel_state_month AS
        SELECT s.month, s.state_name, s.fuel_label, r.fuel_class, r.is_bev,
               sum(s.registrations)::BIGINT AS registrations,
               count(*)::INTEGER AS source_rows,
               count(DISTINCT coalesce(s.office_code, s.office_name))::INTEGER AS offices
        FROM stg_fuel s JOIN ref_fuel_class r USING (fuel_label)
        WHERE NOT s.is_excluded
        GROUP BY ALL ORDER BY 1, 2, 3""")
    export(con, "fuel_state_month", "fuel_state_month")
    log.info("fuel_state_month: %s rows", con.execute("SELECT count(*) FROM fuel_state_month").fetchone()[0])


def build_maker(con) -> None:
    pattern = EV_MAKER_NAME_PATTERN.replace("'", "''")  # constant from config, not user input
    con.execute(f"""CREATE OR REPLACE TABLE maker_state_month AS
        SELECT month, state_name, maker,
               regexp_matches(maker, '{pattern}') AS name_identified_ev_maker,
               sum(registrations)::BIGINT AS registrations
        FROM stg_maker WHERE NOT is_excluded
        GROUP BY ALL ORDER BY 1, 2, 3""")
    export(con, "maker_state_month", "maker_state_month", csv=False)
    con.execute("""CREATE OR REPLACE TABLE ev_named_makers AS
        SELECT maker, sum(registrations) AS registrations FROM maker_state_month
        WHERE name_identified_ev_maker GROUP BY 1 ORDER BY 2 DESC""")
    con.execute(f"COPY ev_named_makers TO '{sql_path(PROCESSED_DIR / 'ev_named_makers.csv')}' (HEADER)")
    log.info("maker_state_month: %s rows; %s name-identified EV makers",
             con.execute("SELECT count(*) FROM maker_state_month").fetchone()[0],
             con.execute("SELECT count(*) FROM ev_named_makers").fetchone()[0])


def build_category(con) -> None:
    con.execute(f"""CREATE OR REPLACE TABLE stg_category_flagged AS
        WITH x AS (
            SELECT *,
                count(DISTINCT office_code) OVER (PARTITION BY month, vehicle_type, registrations) AS same_value_offices,
                median(registrations) OVER (PARTITION BY office_code, vehicle_type) AS office_type_median
            FROM stg_category)
        SELECT *,
            CASE
              WHEN registrations >= {CATEGORY_REPEAT_MIN_VALUE} AND same_value_offices >= {CATEGORY_REPEAT_MIN_OFFICES}
                THEN 'repeated_value_across_offices'
              WHEN registrations >= {CATEGORY_SPIKE_MIN_VALUE}
                   AND registrations > {CATEGORY_SPIKE_MULTIPLE} * greatest(office_type_median, 1)
                THEN 'spike_vs_office_median'
            END AS outlier_reason
        FROM x""")
    con.execute("""CREATE OR REPLACE TABLE category_outliers AS
        SELECT month, state_name, office_code, office_name, vehicle_type, registrations,
               same_value_offices, office_type_median, outlier_reason
        FROM stg_category_flagged WHERE outlier_reason IS NOT NULL ORDER BY registrations DESC""")
    con.execute(f"COPY category_outliers TO '{sql_path(PROCESSED_DIR / 'category_outliers.csv')}' (HEADER)")
    con.execute("""CREATE OR REPLACE TABLE category_state_month AS
        SELECT month, state_name, vehicle_type,
               sum(registrations) FILTER (WHERE outlier_reason IS NULL)::BIGINT AS registrations,
               sum(registrations)::BIGINT AS registrations_raw,
               count(*) FILTER (WHERE outlier_reason IS NOT NULL)::INTEGER AS outlier_rows
        FROM stg_category_flagged GROUP BY ALL ORDER BY 1, 2, 3""")

    # Cross-check against the fuel file where both overlap (Jan-2022..May-2024).
    con.execute("""CREATE OR REPLACE TABLE category_state_check AS
        WITH c AS (SELECT state_name, sum(registrations) t FROM category_state_month
                   WHERE month BETWEEN DATE '2022-01-01' AND DATE '2024-05-01' GROUP BY 1),
             f AS (SELECT state_name, sum(registrations) t FROM fuel_state_month
                   WHERE month BETWEEN DATE '2022-01-01' AND DATE '2024-05-01' GROUP BY 1)
        SELECT c.state_name, c.t AS category_total, f.t AS fuel_total,
               round(c.t / nullif(f.t, 0), 4) AS ratio,
               coalesce(abs(c.t / nullif(f.t, 0) - 1) <= 0.05, false) AS within_5pct
        FROM c LEFT JOIN f USING (state_name) ORDER BY ratio DESC""")
    con.execute(f"COPY category_state_check TO '{sql_path(PROCESSED_DIR / 'category_state_check.csv')}' (HEADER)")
    con.execute("""ALTER TABLE category_state_month ADD COLUMN state_validated BOOLEAN;
        UPDATE category_state_month c SET state_validated = k.within_5pct
        FROM category_state_check k WHERE k.state_name = c.state_name;""")
    export(con, "category_state_month", "category_state_month")
    log.info("category: %s outlier values removed (%s registrations); %s/%s states within 5%% of fuel totals",
             *con.execute("SELECT count(*), sum(registrations) FROM category_outliers").fetchone(),
             *con.execute("SELECT count(*) FILTER (WHERE within_5pct), count(*) FROM category_state_check").fetchone())


def run(con) -> None:
    build_fuel(con)
    build_maker(con)
    build_category(con)
