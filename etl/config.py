"""Central configuration for the VoltBharat ETL pipeline.

All paths are resolved relative to the project root so the pipeline runs from
any working directory. Raw datasets are only ever opened read-only.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("VB_RAW_DIR", PROJECT_ROOT / "data"))
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
AUDIT_DIR = PROCESSED_DIR / "audit"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"

# Offices whose rows are excluded because they are proven to be mislabelled
# aggregates. See reports/data_audit.md, section "Aggregate leak: HR207".
EXCLUDED_FUEL_MAKER_OFFICES = {
    "HR207": "Office 'M/S Pasco Motors LLP, 40 Mile Stone(F.C)' reports values equal "
    "(within ~0.3%) to the sum of every other office in India for Jan-2022..May-2024; "
    "it is a national aggregate leaked into an office row and would double-count."
}

# Category dataset outlier rule (all-fuel context data only, never EV metrics).
CATEGORY_SPIKE_MULTIPLE = 10.0   # value > N x office/vehicle-type median ...
CATEGORY_SPIKE_MIN_VALUE = 1000  # ... and at least this many registrations
CATEGORY_REPEAT_MIN_OFFICES = 3  # identical value in >= N offices same month/type ...
CATEGORY_REPEAT_MIN_VALUE = 1000  # ... and at least this large

# Maker names matched by this pattern are flagged as "name-identified EV makers".
# This is a name-based heuristic (a lower bound), never an EV market share.
EV_MAKER_NAME_PATTERN = r"(?i)(electric|\be-?mobility\b|\bev\b|\bevs\b|e-motorad)"


@dataclass(frozen=True)
class SourceSpec:
    key: str
    pattern: str
    description: str


SOURCE_SPECS = [
    SourceSpec("fuel", "registrations-by-fuel-type*.csv",
               "VAHAN registrations by fuel type, monthly, RTO level"),
    SourceSpec("fuel_dup", "vehicle-registrations-by-fuel-type*.csv",
               "Second copy of the fuel-type extract (checked for duplication)"),
    SourceSpec("maker", "registrations-by-maker*.csv",
               "VAHAN registrations by maker, monthly, RTO level (all fuels)"),
    SourceSpec("category", "vahan-vehicle-registrations-by-vehicle-category*.csv",
               "VAHAN registrations by vehicle category, monthly, office level (all fuels)"),
    SourceSpec("chargers_state", "ev_charging_stations_by_state*.csv",
               "State-wise public EV charging stations snapshot"),
    SourceSpec("chargers_omc", "ev_charging_stations_omc_yearwise*.csv",
               "Year-wise EV charging stations installed by oil marketing companies"),
]


def discover_sources(raw_dir: Path = RAW_DIR) -> dict[str, Path]:
    """Map each source key to the single matching file in ``raw_dir``.

    Matching is done on file names only, so slight naming differences (suffixes)
    are tolerated. Raises if a required pattern matches zero or several files.
    """
    names = sorted(p.name for p in raw_dir.glob("*.csv"))
    found: dict[str, Path] = {}
    for spec in SOURCE_SPECS:
        matches = [n for n in names if fnmatch.fnmatch(n.lower(), spec.pattern.lower())]
        if len(matches) == 0:
            if spec.key == "fuel_dup":
                continue
            raise FileNotFoundError(f"No file matching '{spec.pattern}' in {raw_dir}")
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous files for '{spec.key}': {matches}")
        found[spec.key] = raw_dir / matches[0]
    return found


def ensure_dirs() -> None:
    for d in (PROCESSED_DIR, AUDIT_DIR, REFERENCE_DIR, REPORTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def sql_path(p: Path) -> str:
    """Path as a DuckDB string literal (forward slashes, quotes escaped)."""
    return str(p).replace("\\", "/").replace("'", "''")
