-- VoltBharat analytical schema (PostgreSQL 14+).
-- Idempotent: safe to run repeatedly; never drops or truncates anything.

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT NOT NULL
);

-- ---------------------------------------------------------------- dimensions
CREATE TABLE IF NOT EXISTS dim_state (
    state_id    SMALLSERIAL PRIMARY KEY,
    state_name  TEXT NOT NULL UNIQUE,
    state_code  CHAR(2) NOT NULL UNIQUE,
    state_type  TEXT NOT NULL CHECK (state_type IN ('State', 'UT')),
    region      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id        INTEGER PRIMARY KEY,            -- yyyymm
    month_start    DATE NOT NULL UNIQUE,
    year           SMALLINT NOT NULL,
    month          SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    quarter        SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    fy_start_year  SMALLINT NOT NULL,              -- Indian FY starts in April
    fy_label       TEXT NOT NULL,                  -- e.g. FY2024-25
    month_label    TEXT NOT NULL                   -- e.g. Apr 2024
);

CREATE TABLE IF NOT EXISTS dim_fuel (
    fuel_id     SMALLSERIAL PRIMARY KEY,
    fuel_label  TEXT NOT NULL UNIQUE,
    fuel_class  TEXT NOT NULL,
    is_bev      BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_maker (
    maker_id                  SERIAL PRIMARY KEY,
    maker_name                TEXT NOT NULL UNIQUE,
    name_identified_ev_maker  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_vehicle_type (
    vehicle_type_id  SMALLSERIAL PRIMARY KEY,
    vehicle_type     TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------- provenance
CREATE TABLE IF NOT EXISTS data_sources (
    source_id        SMALLSERIAL PRIMARY KEY,
    source_key       TEXT NOT NULL UNIQUE,
    file_name        TEXT NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL,
    provenance       TEXT NOT NULL,
    grain            TEXT NOT NULL,
    coverage_start   DATE,
    coverage_end     DATE,
    coverage_label   TEXT NOT NULL,
    row_count        BIGINT,
    size_bytes       BIGINT,
    sha256           CHAR(64),
    can_identify_ev  BOOLEAN NOT NULL,
    used_for         TEXT NOT NULL,
    limitations      TEXT NOT NULL,
    processed_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS etl_runs (
    run_id        SERIAL PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    rows_loaded   JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation    JSONB NOT NULL DEFAULT '[]'::jsonb,
    message       TEXT
);

CREATE TABLE IF NOT EXISTS policy_events (
    event_id     TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    short_name   TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE,
    event_type   TEXT NOT NULL,
    description  TEXT NOT NULL,
    source       TEXT NOT NULL,
    CHECK (end_date IS NULL OR end_date >= start_date)
);

-- ---------------------------------------------------------------- facts
-- Registrations by fuel label: the only EV-identifying source.
CREATE TABLE IF NOT EXISTS fact_registrations_fuel (
    date_id        INTEGER  NOT NULL REFERENCES dim_date (date_id),
    state_id       SMALLINT NOT NULL REFERENCES dim_state (state_id),
    fuel_id        SMALLINT NOT NULL REFERENCES dim_fuel (fuel_id),
    registrations  BIGINT   NOT NULL CHECK (registrations >= 0),
    source_rows    INTEGER  NOT NULL,
    PRIMARY KEY (date_id, state_id, fuel_id)
);
CREATE INDEX IF NOT EXISTS ix_frf_state_date ON fact_registrations_fuel (state_id, date_id);
CREATE INDEX IF NOT EXISTS ix_frf_fuel ON fact_registrations_fuel (fuel_id);

-- Registrations by maker: ALL fuels (source has no fuel field).
CREATE TABLE IF NOT EXISTS fact_registrations_maker (
    date_id        INTEGER  NOT NULL REFERENCES dim_date (date_id),
    state_id       SMALLINT NOT NULL REFERENCES dim_state (state_id),
    maker_id       INTEGER  NOT NULL REFERENCES dim_maker (maker_id),
    registrations  BIGINT   NOT NULL CHECK (registrations >= 0),
    PRIMARY KEY (date_id, state_id, maker_id)
);
CREATE INDEX IF NOT EXISTS ix_frm_maker_date ON fact_registrations_maker (maker_id, date_id);
CREATE INDEX IF NOT EXISTS ix_frm_state_date ON fact_registrations_maker (state_id, date_id);

-- Registrations by vehicle category: ALL fuels, after outlier removal.
CREATE TABLE IF NOT EXISTS fact_registrations_segment (
    date_id            INTEGER  NOT NULL REFERENCES dim_date (date_id),
    state_id           SMALLINT NOT NULL REFERENCES dim_state (state_id),
    vehicle_type_id    SMALLINT NOT NULL REFERENCES dim_vehicle_type (vehicle_type_id),
    registrations      BIGINT,             -- NULL when every source value was an outlier
    registrations_raw  BIGINT   NOT NULL,
    outlier_rows       INTEGER  NOT NULL,
    state_validated    BOOLEAN  NOT NULL,  -- state's cleaned total within 5% of fuel file
    PRIMARY KEY (date_id, state_id, vehicle_type_id)
);
CREATE INDEX IF NOT EXISTS ix_frs_state_date ON fact_registrations_segment (state_id, date_id);

-- Public charging stations, state snapshot (2025).
CREATE TABLE IF NOT EXISTS fact_chargers (
    state_id                  SMALLINT NOT NULL REFERENCES dim_state (state_id),
    source_id                 SMALLINT NOT NULL REFERENCES data_sources (source_id),
    snapshot_label            TEXT     NOT NULL,
    public_charging_stations  INTEGER  NOT NULL CHECK (public_charging_stations >= 0),
    PRIMARY KEY (state_id, source_id)
);

-- OMC-installed charging stations by financial year (a different, narrower measure).
CREATE TABLE IF NOT EXISTS fact_chargers_omc_fy (
    state_id         SMALLINT NOT NULL REFERENCES dim_state (state_id),
    fy_label         TEXT     NOT NULL,
    fy_order         SMALLINT NOT NULL,
    is_partial_year  BOOLEAN  NOT NULL,
    installed        INTEGER  NOT NULL CHECK (installed >= 0),
    PRIMARY KEY (state_id, fy_label)
);

CREATE TABLE IF NOT EXISTS fact_chargers_omc_status (
    state_id           SMALLINT PRIMARY KEY REFERENCES dim_state (state_id),
    decommissioned     INTEGER NOT NULL,
    total_installed    INTEGER NOT NULL,
    total_operational  INTEGER NOT NULL,
    source_rows        TEXT    NOT NULL
);

INSERT INTO schema_version (version, description)
VALUES (1, 'Baseline star schema')
ON CONFLICT (version) DO NOTHING;
