"""Data sources, freshness, classification rules and methodology."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.cache import cached

METHODOLOGY = [
    {"metric": "BEV registrations", "definition": "Sum of registrations with fuel label 'Electric(BOV)' or 'Pure EV' in the selected period and states.",
     "source": "fuel"},
    {"metric": "EV share (%)", "definition": "BEV registrations / registrations of all fuel labels × 100, same period and states.",
     "source": "fuel"},
    {"metric": "YoY growth (%)", "definition": "(BEV in the 12 months ending at the selected end month − BEV in the preceding 12 months) / "
     "preceding 12 months × 100. Unavailable when 24 months of data are not available or the previous value is zero.", "source": "fuel"},
    {"metric": "Monthly YoY (%)", "definition": "BEV in a month vs the same month one year earlier.", "source": "fuel"},
    {"metric": "BEVs per public charging station", "definition": "BEV registrations in the selected period / public charging stations "
     "in the 2025 state snapshot. An approximate infrastructure-pressure indicator, not vehicles per charger in operation. "
     f"States with fewer than 25 stations are shown but not ranked.", "source": "fuel + chargers_state"},
    {"metric": "Pressure tier", "definition": "State ratio relative to the national ratio: ≥2× high, ≥1.25× elevated, otherwise typical.",
     "source": "fuel + chargers_state"},
    {"metric": "Share ranking eligibility", "definition": "States with fewer than 10,000 total registrations in the period are not ranked by share; "
     "states with fewer than 1,000 BEVs in the comparison year are not ranked by growth.", "source": "fuel"},
    {"metric": "Maker share (all fuels)", "definition": "Maker registrations / all registrations in the maker source. Not an EV market share.",
     "source": "maker"},
    {"metric": "OMC installations", "definition": "Stations installed by oil marketing companies per financial year, using the source's FY labels.",
     "source": "chargers_omc"},
]


@cached
def sources(conn: Connection) -> dict:
    ds = [dict(r) for r in conn.execute(text("""SELECT source_key, file_name, title, description, provenance, grain,
        coverage_start, coverage_end, coverage_label, row_count, size_bytes, sha256, can_identify_ev, used_for,
        limitations, processed_at FROM data_sources ORDER BY source_id""")).mappings()]
    for d in ds:
        for k in ("coverage_start", "coverage_end", "processed_at"):
            d[k] = d[k].isoformat() if d[k] else None
    fuels = [dict(r) for r in conn.execute(text(
        "SELECT fuel_label, fuel_class, is_bev FROM dim_fuel ORDER BY is_bev DESC, fuel_class, fuel_label")).mappings()]
    run = conn.execute(text("""SELECT run_id, started_at, finished_at, rows_loaded, validation FROM etl_runs
        WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1""")).mappings().first()
    return {
        "sources": ds,
        "classification": {
            "headline_ev_definition": "Battery-electric vehicles (BEV): fuel labels 'Electric(BOV)' and 'Pure EV'.",
            "separate_classes": ["strong_hybrid", "plugin_hybrid", "fcev", "other_hybrid"],
            "labels": fuels,
        },
        "quality_rules": [
            "registrations-by-fuel-type.csv and vehicle-registrations-by-fuel-type.csv are byte-identical; only one is used.",
            "Office HR207 (M/S Pasco Motors LLP, Haryana) is excluded: its values equal the sum of all other offices "
            "(a national aggregate) for Jan-2022 to May-2024.",
            "State names are standardised through a documented mapping table; unknown names stop the pipeline.",
            "Category values that repeat across ≥3 offices in a month, or exceed 10× the office's median (and ≥1,000), are removed; "
            "states whose cleaned totals differ from the fuel source by more than 5% are excluded from category views.",
            "No missing months are imputed or interpolated.",
        ],
        "methodology": METHODOLOGY,
        "last_run": {"run_id": run["run_id"], "started_at": run["started_at"].isoformat(),
                     "finished_at": run["finished_at"].isoformat(), "rows_loaded": run["rows_loaded"],
                     "validation": run["validation"]} if run else None,
    }
