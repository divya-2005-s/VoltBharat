# ETL Execution Report

- Started: 2026-10-29T09:07:10+00:00
- Finished: 2026-10-29T09:07:42+00:00
- Database loaded: yes

## Sources

| Key | File |
|---|---|
| fuel | `registrations-by-fuel-type.csv` |
| fuel_dup | `vehicle-registrations-by-fuel-type.csv` |
| maker | `registrations-by-maker.csv` |
| category | `vahan-vehicle-registrations-by-vehicle-category-71m55i.csv` |
| chargers_state | `ev_charging_stations_by_state_2025.csv` |
| chargers_omc | `ev_charging_stations_omc_yearwise_2026.csv` |

## Steps

| Step | Seconds |
|---|---|
| extract_vahan | 9.7 |
| clean_registrations | 2.7 |
| clean_chargers | 0.1 |
| build_geo | 0.0 |
| validate_data | 0.5 |
| load_database | 17.8 |

## Validation

| Status | Check | Detail |
|---|---|---|
| PASS | fuel_files_duplicate_detected | vehicle-registrations-by-fuel-type.csv is byte-identical to registrations-by-fuel-type.csv; only registrations-by-fuel-type.csv is used. |
| PASS | fuel_total_reconciles | raw (excl. HR207) 127,633,967 = processed 127,633,967; excluded HR207 rows 58,568,794 |
| PASS | fuel_label_totals_reconcile | 0 fuel labels differ between raw and processed |
| PASS | maker_total_reconciles | raw (excl. HR207) 127,477,312 = processed 127,477,312 |
| PASS | category_total_reconciles | raw 754,948,125 = clean 301,666,373 + removed outliers 453,281,752 |
| PASS | no_aggregate_leak_in_states | largest single state share of a national month is 17.81% (Uttar Pradesh, 2023-05-01); an aggregate leak would push this near 50% |
| PASS | states_canonical | 0 non-canonical state names in outputs |
| PASS | fuel_state_coverage | 36/36 states and UTs present in fuel data |
| PASS | no_negative_registrations | 0 negative registration values |
| PASS | fuel_months_continuous | 0 missing national months in 2022-01-01..2026-09-01 |
| PASS | fuel_state_months_complete | 0 states have months with no rows (not imputed): [] |
| PASS | fuel_vs_maker_within_2pct | largest monthly gap 1.679% (2026-01-01) |
| PASS | bev_series_spans_label_change | BEV (Electric(BOV) + Pure EV) monthly 2024-01..2024-08: Jan:151,498, Feb:148,707, Mar:223,202, Apr:118,749, May:145,413, Jun:146,229, Jul:189,264, Aug:162,283 |
| PASS | charger_snapshot_total | state snapshot total 29,277 vs published 29,277 |
| PASS | charger_snapshot_states | 36/36 states in charger snapshot |
| WARN | omc_fy_sum_matches_total_installed | 3 states where sum(FY installs) <> total_installed (source uses net-of-decommissioned totals there) |
| WARN | category_states_validated | 29/34 states' cleaned category totals within 5% of fuel totals (Jan-2022..May-2024); others are flagged state_validated=false |

## Outputs

- `data/processed/category_outliers.csv` (406 KB)
- `data/processed/category_state_check.csv` (1 KB)
- `data/processed/category_state_month.csv` (1,586 KB)
- `data/processed/category_state_month.parquet` (182 KB)
- `data/processed/chargers_omc_summary.csv` (1 KB)
- `data/processed/chargers_omc_yearwise.csv` (8 KB)
- `data/processed/chargers_state_snapshot.csv` (1 KB)
- `data/processed/etl_manifest.json` (1 KB)
- `data/processed/ev_named_makers.csv` (8 KB)
- `data/processed/fuel_state_month.csv` (1,169 KB)
- `data/processed/fuel_state_month.parquet` (128 KB)
- `data/processed/maker_state_month.parquet` (937 KB)
- `data/processed/validation_report.json` (4 KB)
