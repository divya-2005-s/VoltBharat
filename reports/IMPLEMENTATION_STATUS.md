# VoltBharat — Implementation Status

Resume point for multi-session work. Last updated 29 Oct 2026.

| Phase | Status | Notes |
|---|---|---|
| 1 Inspect & audit | Done | `python -m etl.inspect_data` → `reports/data_audit.md`, `data/processed/audit/*.json` |
| 2 Mappings & rules | Done | `data/reference/*.csv`, rules in `etl/config.py`, audit §9–10 |
| 3 ETL | Done | `python -m etl.run_pipeline`; 17 pass / 2 warn / 0 fail |
| 4 PostgreSQL | Done | Docker `voltbharat-db` on 127.0.0.1:5433; `--load-db` idempotent (verified by reloading) |
| 5 FastAPI | Done | 15 endpoints, `/docs`; `docs/openapi.json` exported |
| 6 Frontend | Done | 8 pages; light/dark; desktop/tablet/phone checked by screenshot |
| 7 Integration | Done | All UI figures come from the API; no console errors on any page |
| 8 Tests | Done | pytest 61 passed · Vitest 18 passed · Playwright 8 passed (3 consecutive runs) |
| 9 Docs | Done | README, docs/ARCHITECTURE.md, docs/API.md, reports/analysis_report.md, reports/insights_report.pdf, notebook |
| 10 Deployment config | Done (not deployed) | `render.yaml`, `frontend/vercel.json`, `backend/requirements.txt`, docs/DEPLOYMENT.md |

## Key data decisions
- `vehicle-registrations-by-fuel-type.csv` is byte-identical to `registrations-by-fuel-type.csv` → ignored.
- Office HR207 is a national aggregate leaked into office rows → excluded from fuel and maker data.
- BEV = `Electric(BOV)` + `Pure EV` (label migration during 2024). Hybrids/FCEV separate.
- Maker and category files have no fuel field → never EV metrics.
- Category file: outlier rule + per-state validation against fuel file (29/34 states pass).

## Open items / possible next steps
- Git is not initialised in the project folder (not requested). `.gitignore` is ready.
- E2E runs with one worker: `vite preview` on Windows intermittently reset connections under parallel load.
- If the schema starts evolving, introduce Alembic on top of the `schema_version` baseline.
- Better data would unlock EV-by-category and EV-by-maker analysis (see README limitations).
