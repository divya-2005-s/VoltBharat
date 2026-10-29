# VoltBharat architecture

```
 data/*.csv (raw, read-only)
      │
      ▼
 ┌──────────────────────── ETL (Python + DuckDB) ─────────────────────────┐
 │ inspect_data   → reports/data_audit.md, data/processed/audit/*.json    │
 │ extract_vahan  → staging.duckdb (standardised office-level rows)       │
 │ clean_registrations / clean_chargers → data/processed/*.parquet|csv    │
 │ build_geo      → data/reference/india_states.geojson                   │
 │ validate_data  → data/processed/validation_report.json (fail = stop)   │
 │ load_database  → PostgreSQL (one transaction, idempotent)              │
 └────────────────────────────────────────────────────────────────────────┘
      │
      ▼
 PostgreSQL (star schema: dim_* + fact_* + data_sources + etl_runs + views)
      │  read-only connections, bound parameters
      ▼
 FastAPI  /api/v1/*  (services/ compute metrics; TTL cache; JSON envelopes; CSV export)
      │  JSON over HTTP (CORS allow-list)
      ▼
 React + TypeScript (Vite) — TanStack Query, React Router, ECharts, Tailwind, shadcn-style UI
```

## Design decisions

| Decision | Why |
|---|---|
| DuckDB for raw CSVs | The 259 MB maker file is aggregated with SQL without loading it into pandas. |
| State × month grain in PostgreSQL | Every dashboard metric is national or state level; office-level rows are not needed at query time (~313k fact rows total). |
| Facts keep the raw fuel label | EV classification lives in `dim_fuel` (from `data/reference/fuel_classification.csv`), so a policy change is a reference-data edit, not an ETL rewrite. |
| Validation gate before load | A failed reconciliation stops the pipeline; the database keeps its previous good data. |
| Full refresh in one transaction | Reruns never duplicate rows; a failure rolls back completely. |
| Metric logic in backend services | The UI only formats; the report generator calls the same services, so the PDF and dashboard cannot disagree. |
| 503 instead of fallback data | When the database is unreachable the API returns an error and the UI shows an error state, never estimates. |
| Baseline `schema.sql` instead of Alembic | One idempotent baseline schema with a `schema_version` table. Introduce Alembic when the schema starts to evolve. |

## Database schema

- `dim_state` (36 states/UTs, canonical names matching the GeoJSON), `dim_date` (month grain, calendar + Indian FY), `dim_fuel` (label → class, `is_bev`), `dim_maker` (with `name_identified_ev_maker`), `dim_vehicle_type`
- `fact_registrations_fuel` (date, state, fuel) — the only EV-identifying fact
- `fact_registrations_maker` (date, state, maker) — all fuels
- `fact_registrations_segment` (date, state, vehicle type) — all fuels, cleaned, with `state_validated`
- `fact_chargers` (state snapshot), `fact_chargers_omc_fy`, `fact_chargers_omc_status` — kept separate
- `data_sources` (provenance, coverage, hashes, limitations), `etl_runs` (row counts + validation results), `policy_events`
- Views: `v_ev_state_month`, `v_ev_national_month`, `v_state_chargers`

Primary keys are natural (e.g. `(date_id, state_id, fuel_id)`), with foreign keys to every dimension and indexes on `(state_id, date_id)`.

## Frontend structure

```
src/app/          App routes, providers (QueryClient, theme, tooltips, toasts)
src/components/   layout/ (shell, sidebar, header) · filters/ · charts/ (ECharts wrapper, option builders, tokens)
                  maps/ (India choropleth + fallback) · dashboard/ (cards, KPI, notices, states) · tables/ · ui/ (primitives)
src/hooks/        useFilters (URL state), queries (TanStack Query), useTheme, usePolicyMarkers
src/lib/          api.ts (all HTTP), formatters.ts (Indian numbers, months), utils.ts
src/pages/        one file per page
src/types/api.ts  response types mirroring backend/app/schemas.py
```

Global filters (`start`, `end`, `state`) live in the URL and are carried across pages by the sidebar links. Query keys include every filter that changes a response.

## Chart conventions

Colours come from a palette validated for colour-vision deficiency (light and dark separately): BEV is always the first series (green). Sequential single-hue ramps are used for maps (green for adoption, amber for infrastructure pressure). Pressure tiers use status colours with an icon and a text label, never colour alone. Charts never use two y-axes.
