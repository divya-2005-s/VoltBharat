# VoltBharat

**India's Electric Mobility Intelligence Platform** — EV adoption and charging-gap analytics built on VAHAN registration data and Government of India charging-station data.

VoltBharat answers: how fast battery-electric vehicle (BEV) registrations are growing, which states lead in volume and adoption share, where EV registrations are high relative to public charging stations, how charging infrastructure has grown, and how registrations moved around FAME-II, EMPS 2024 and PM E-DRIVE milestones. It states plainly what the data **cannot** answer (EV splits by vehicle category and EV market share by manufacturer) instead of estimating them.

Audience: policymakers, charge-point operators, automakers, investors, researchers and analysts.

---

## Contents

[Architecture](#architecture) · [Datasets](#dataset-inventory) · [Data quality](#data-cleaning-methodology) · [Metrics](#metric-definitions) · [Quick start](#quick-start-windows-powershell) · [Pages](#frontend-pages) · [API](#backend-endpoints) · [Tests](#running-tests) · [Troubleshooting](#troubleshooting) · [Limitations](#known-limitations) · [Deployment](#deployment)

## Architecture

```
data/*.csv ──► ETL (Python + DuckDB) ──► data/processed/* ──► PostgreSQL (star schema)
                 audit · clean · validate                         │
                                                                   ▼
                       React + TypeScript dashboard ◄── FastAPI /api/v1 (JSON + CSV)
```

| Layer | Stack |
|---|---|
| Data engineering | Python 3.13, DuckDB (large CSVs), pandas, Jupyter |
| Database | PostgreSQL 17 (Docker, port 5433), SQLAlchemy 2, idempotent `sql/schema.sql` + `sql/views.sql` |
| Backend | FastAPI, Pydantic v2, SQLAlchemy Core with bound parameters, pytest |
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui-style components on Radix, Apache ECharts, TanStack Query, React Router, Lucide |
| Testing | pytest (ETL + API), Vitest + React Testing Library, Playwright |

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
VoltBharat/
├── data/                 raw CSVs (untouched) · processed/ (generated) · reference/ (mappings, policy events, GeoJSON)
├── etl/                  inspect_data, extract_vahan, clean_*, build_geo, validate_data, init_db, load_database,
│                         run_pipeline, generate_reports
├── sql/                  schema.sql, views.sql
├── backend/app/          main.py, core/, db.py, schemas.py, routers/, services/ · backend/tests/
├── frontend/             Vite app (src/, e2e/, public/geo/)
├── notebooks/            01_exploratory_analysis.ipynb
├── reports/              data_audit.md, analysis_report.md, insights_report.pdf, etl_execution_report.md, figures/
├── docs/                 ARCHITECTURE.md, API.md, DEPLOYMENT.md, openapi.json
├── tests/etl/            pipeline tests on synthetic CSVs
└── docker-compose.yml, render.yaml, requirements.txt, .env.example, pytest.ini
```

## Dataset inventory

All six files sit in `data/` and are opened read-only. File names are discovered by pattern, so small name differences are tolerated.

| File | Content | Coverage | Identifies EVs? | Used for |
|---|---|---|---|---|
| `registrations-by-fuel-type.csv` | VAHAN registrations by RTO × month × fuel label | Jan 2022 – Sep 2026 | **Yes** | All EV metrics |
| `vehicle-registrations-by-fuel-type.csv` | **Byte-identical copy** of the file above | — | — | Ignored (hash-checked each run) |
| `registrations-by-maker.csv` (259 MB) | VAHAN registrations by RTO × month × maker | Jan 2022 – Sep 2026 | No (no fuel field) | All-fuel maker rankings |
| `vahan-vehicle-registrations-by-vehicle-category-*.csv` | Registrations by office × month × vehicle category | Jan 2019 – May 2024 | No (no fuel field) | All-fuel category context |
| `ev_charging_stations_by_state_2025.csv` | Public EV charging stations by state | 2025 snapshot (total 29,277) | — | Charging-gap denominator |
| `ev_charging_stations_omc_yearwise_2026.csv` | Stations installed by oil marketing companies by FY | FY2020-21 – FY2025-26 (to 1 Mar 2026) | — | Charger growth (separate measure) |

**Provenance.** The VAHAN extracts come from the MoRTH VAHAN dashboard; the original download URLs were not recorded with the files. The state charging snapshot matches the PIB annexure (Aug 2025, inputs from the Ministry of Power) that totals 29,277 stations. The map uses a community-curated GeoJSON (`udit-001/india-maps-data`, district level, dissolved to states by `etl/build_geo.py`); it is not an official Survey of India product.

The full audit (schemas, nulls, duplicates, label inventories, date ranges, and the evidence for each rule below) is generated in [reports/data_audit.md](reports/data_audit.md).

## Data cleaning methodology

1. **Duplicate file.** The two fuel-type files have the same SHA-256; only one is used. Adding them would double every figure.
2. **Aggregate leak (HR207).** Office "M/S Pasco Motors LLP, 40 Mile Stone(F.C)" in Haryana reports, every month from Jan 2022 to May 2024, a value equal to the sum of every other office in India (ratio 0.97–1.00). It is a national total recorded as an office row, and it disappears after May 2024. Left in, it doubles national totals and creates a false ~50% "collapse" in June 2024. It is excluded from the fuel and maker data.
3. **EV classification** (`data/reference/fuel_classification.csv`). EV = BEV = `Electric(BOV)` + `Pure EV`. VAHAN moved battery-electric volumes from the first label to the second during 2024; the combined series is continuous. Strong hybrid, plug-in hybrid, fuel cell and other hybrid labels are reported separately and never counted as EVs.
4. **State names** are standardised via `data/reference/state_mapping.csv` (e.g. `Ut Of Dnh And Dd` → Dadra and Nagar Haveli and Daman and Diu; OMC row `Leh` → Ladakh). Unknown names stop the pipeline.
5. **Keys and duplicates.** Offices are keyed by state + code + name so West Bengal offices with null codes are kept. Natural-key duplicates are summed (they are distinct source rows), and counts are reported.
6. **Category file outliers.** Values ≥1,000 that repeat identically across ≥3 offices in a month, or exceed 10× the office's median, are removed. States whose cleaned totals differ from the fuel file by more than 5% (Jan 2022 – May 2024) are excluded from category views. 29 of 34 states pass.
7. **No imputation.** Missing months are never interpolated.
8. **Validation gate.** Totals are reconciled raw → processed → database (exact match required). A failed check stops the load.

## Database schema

Star schema in [sql/schema.sql](sql/schema.sql): `dim_state`, `dim_date` (month grain with Indian FY), `dim_fuel`, `dim_maker`, `dim_vehicle_type`; facts `fact_registrations_fuel`, `fact_registrations_maker`, `fact_registrations_segment`, `fact_chargers`, `fact_chargers_omc_fy`, `fact_chargers_omc_status`; plus `data_sources`, `etl_runs`, `policy_events` and views in [sql/views.sql](sql/views.sql). Primary keys, foreign keys, check constraints and indexes are defined; loads run in one transaction and are idempotent.

## Metric definitions

| Metric | Definition |
|---|---|
| BEV registrations | Sum of `Electric(BOV)` + `Pure EV` registrations in the period and area |
| EV share (%) | BEV ÷ registrations of all fuel labels × 100 |
| YoY growth (%) | BEV in the 12 months ending at the selected end month vs the previous 12 months; unavailable without 24 months of data or with a zero base |
| Monthly YoY (%) | A month vs the same month one year earlier |
| BEVs per public station | BEV registrations in the selected period ÷ stations in the 2025 snapshot. **Approximate infrastructure-pressure indicator**, not vehicles per operating charger; says nothing about utilisation, power, location or home charging |
| Pressure tier | State ratio vs national ratio: ≥2× high, ≥1.25× elevated, otherwise typical; states with <25 stations are not ranked |
| Ranking eligibility | Share ranks need ≥10,000 total registrations in the period; growth ranks need ≥1,000 BEVs in the comparison year |
| OMC installations | Stations installed per FY, using the source's FY labels; the partial FY2025-26 is never compared with full years |

## Quick start (Windows PowerShell)

Prerequisites: Python 3.13, Node.js 24, Docker Desktop (for the bundled database) — or any PostgreSQL 14+ you set in `DATABASE_URL`.

```powershell
cd D:\Projects\VoltBharat

# 1. Python dependencies
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

# 2. Configuration (first time only): copy the template, then set POSTGRES_PASSWORD and DATABASE_URL
Copy-Item .env.example .env        # skip if .env already exists
notepad .env                       # DATABASE_URL=postgresql+psycopg://voltbharat:<password>@127.0.0.1:5433/voltbharat

# 3. Start PostgreSQL (Docker Desktop must be running)
docker compose up -d

# 4. Dataset audit  ->  reports\data_audit.md
.\.venv\Scripts\python -m etl.inspect_data

# 5. ETL + validation + database load (idempotent; ~30 s)
.\.venv\Scripts\python -m etl.run_pipeline --load-db

# 6. Backend  ->  http://127.0.0.1:8000/docs
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# 7. Frontend (new terminal)  ->  http://127.0.0.1:5173
cd D:\Projects\VoltBharat\frontend
Copy-Item .env.example .env        # skip if it exists
npm install
npm run dev
```

Optional: `python -m etl.run_pipeline` (without `--load-db`) only rebuilds processed files; `python -m etl.init_db` only creates the schema; `python -m etl.generate_reports` regenerates `reports/analysis_report.md`, `reports/insights_report.pdf` and figures from the database.

## Frontend pages

| Page | What it shows |
|---|---|
| Overview | KPIs (BEV registrations, YoY, EV share, public stations), monthly trend with policy markers, EV-share choropleth (click to filter), top-5 states, powertrain highlights |
| State Explorer | Map with selectable metric, top-15 comparison, searchable/sortable/paginated table, state detail drawer |
| Vehicle Segments | Why EV category splits are unavailable; EV powertrain trends and mix; all-fuel category stacked area and donut (validated states) |
| Manufacturers | Why EV market share is unavailable; all-fuel rankings and share; name-identified EV maker subset |
| Charging Gap | BEVs-per-station map, ranked table with tiers, pressure bars, registrations-vs-stations scatter, OMC installations by FY |
| Policy Impact | Trend with milestones and prior-year baseline, before/after comparisons (3/6/12-month windows), caveats |
| Insights | Generated observations and recommendations, each with metric, period and source |
| Data Sources | Provenance, coverage, hashes, last ETL run and validation results, classification rules, methodology |

Global filters (date range, state) live in the URL and persist across pages. Every chart has a PNG export and CSV export where relevant; light/dark mode follows the system and can be toggled.

## Backend endpoints

`/health`, `/api/v1/overview`, `/trend`, `/states`, `/states/{state_name}`, `/segments`, `/makers`, `/charging-gap`, `/chargers/growth`, `/policy-events`, `/policy`, `/insights`, `/export`, `/sources`, `/meta/states`. Parameters, response shapes and errors: [docs/API.md](docs/API.md) and Swagger UI at `/docs`.

## Running tests

```powershell
cd D:\Projects\VoltBharat
.\.venv\Scripts\python -m pytest                 # ETL (synthetic data) + API (needs the loaded DB)

cd frontend
npm test                                          # Vitest + React Testing Library
npx playwright install chromium                   # first time only
npm run test:e2e                                  # Playwright; needs the API running on :8000
```

API tests check key figures (KPIs, YoY, ratios, rankings, sums) against independent SQL queries on the database, and skip with a clear reason if the database is not loaded. E2E tests build the frontend and run against `vite preview` on port 4173.

## Troubleshooting

| Problem | Fix |
|---|---|
| `DATABASE_URL is not set` | Create `.env` from `.env.example`. |
| `docker compose up` fails | Start Docker Desktop. Port 5433 is used so a local PostgreSQL on 5432 is unaffected. |
| Pipeline stops on `UnknownStateError` | A new state spelling appeared: add it to `data/reference/state_mapping.csv`. |
| Pipeline stops on an unknown fuel label | Add the label to `data/reference/fuel_classification.csv` with its class. |
| UI shows "Data unavailable" | The API cannot reach the database; check `docker ps` and `/health`. |
| UI shows "Cannot reach the VoltBharat API" | Start the backend, check `frontend/.env` → `VITE_API_BASE_URL`. |
| CORS error | Add the frontend origin to `CORS_ORIGINS` in `.env` and restart the API. |
| Map shows a list instead of a map | Run `npm run sync:geo` (copies `data/reference/india_states.geojson` into `frontend/public/geo/`). |
| Notebook can't import duckdb | Run it with the project venv's Python (`.\.venv\Scripts\python -m jupyter lab`). |

## Known limitations

- **No EV split by vehicle category** (2W/3W/car/bus/goods): no source has both fuel and category.
- **No EV market share by manufacturer**: the maker source has no fuel field. The name-identified EV maker list is a lower bound.
- **Charging snapshot is a single 2025 state-level count** of stations (not charging points), without power, utilisation, uptime or location. The ratio is not time-matched to registrations.
- **OMC data covers only OMC-installed stations**; FY2025-26 is partial; `total_installed` is net of decommissioned stations in a few rows.
- **Category data** is all-fuel, ends May 2024, excludes Telangana and Lakshadweep, and needed heavy outlier removal; five states fail validation and are excluded.
- **Policy comparisons are associations**, not causal effects; overlapping schemes and seasonality cannot be separated.
- VAHAN registration counts may lag sales and may not cover every registering authority in every month.

## Deployment

Configuration for Neon (PostgreSQL), Render (`render.yaml`, API) and Vercel (`frontend/vercel.json`) is included but **nothing is deployed automatically**. Step-by-step guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Reports

- [reports/data_audit.md](reports/data_audit.md) — dataset audit (generated)
- [reports/analysis_report.md](reports/analysis_report.md) and [reports/insights_report.pdf](reports/insights_report.pdf) — findings (generated from the database)
- [reports/etl_execution_report.md](reports/etl_execution_report.md) — last ETL run and validation results
