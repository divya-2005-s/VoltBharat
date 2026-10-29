# VoltBharat API reference

Base URL (local): `http://127.0.0.1:8000`. Interactive docs: `/docs` (Swagger UI) and `/redoc`. Machine-readable spec: [`openapi.json`](openapi.json).

All endpoints are `GET`, read-only, and return:

```json
{ "data": { ... }, "meta": { "period": {"start": "2022-01", "end": "2026-09", "months": 57},
  "sources": ["fuel", "chargers_state"], "notes": ["..."],
  "data_coverage": {"start": "2022-01", "end": "2026-09"}, "last_processed_at": "2026-10-29T09:07:25+00:00" } }
```

Errors return `{"error": {"code": "...", "message": "..."}}` with status 404 (`unknown_state`), 422 (`invalid_request`, `invalid_period`, `period_out_of_range`), 503 (`database_unavailable`, `database_error`) or 500 (`internal_error`). Stack traces and credentials are never returned.

## Common query parameters

| Parameter | Format | Default | Notes |
|---|---|---|---|
| `start` | `YYYY-MM` | first month with data | Clamped to coverage; a note is added to `meta.notes` |
| `end` | `YYYY-MM` | latest month | Must be ≥ `start` |
| `state` | state/UT name, case-insensitive | all India | e.g. `Tamil Nadu` |

## Endpoints

| Endpoint | Parameters | Returns |
|---|---|---|
| `/health` | — | `status`, `database`, last successful ETL time; 503 when the DB is unreachable |
| `/api/v1/overview` | start, end, state | KPIs (BEV, EV share, trailing-12-month YoY, public stations), monthly trend, map values, top 5 states by BEV and by share, powertrain totals |
| `/api/v1/trend` | start, end, state, `granularity=month\|fy\|year` | Time series; partial periods flagged and not compared |
| `/api/v1/states` | start, end, `sort`, `order`, `search`, `page`, `page_size` (≤100) | National totals + paginated state table with ranks, YoY, chargers, BEVs per station |
| `/api/v1/states/{state_name}` | start, end | State summary, monthly trend, powertrain, YoY, top makers (all fuels), OMC installs |
| `/api/v1/segments` | start, end, state | `ev_category_split_supported=false` + reason; EV powertrain mix; all-fuel category context (validated states only) |
| `/api/v1/makers` | start, end, state, `search`, `ev_named_only`, `page`, `page_size` (≤200) | `ev_market_share_supported=false` + reason; all-fuel rankings; name-identified EV maker subset |
| `/api/v1/charging-gap` | start, end, `limit` | National ratio, thresholds, per-state BEVs per station, tier, rank (states with <25 stations unranked) |
| `/api/v1/chargers/growth` | state | OMC installations by FY (source labels), cumulative, growth between complete FYs, status totals |
| `/api/v1/policy-events` | — | Policy milestones with dates, descriptions and sources |
| `/api/v1/policy` | start, end, state, `window=3..12`, `event_id` | Events, before/after comparisons (merged by month), trend, caveats |
| `/api/v1/insights` | start, end | Observations and recommendations with metric, period, sources and reasoning |
| `/api/v1/export` | start, end, state, `dataset` | CSV download. `dataset`: trend, states, charging_gap, makers, powertrain, categories, chargers_growth, policy_comparison, insights |
| `/api/v1/sources` | — | Data sources, EV classification, quality rules, methodology, last ETL run with validation results |
| `/api/v1/meta/states` | — | States and union territories |

## Metric definitions

See the Data Sources page in the app or `backend/app/services/sources.py` (`METHODOLOGY`). Key ones:

- **BEV registrations** = registrations with fuel label `Electric(BOV)` or `Pure EV`.
- **EV share (%)** = BEV ÷ all fuel labels × 100.
- **YoY growth (%)** = (BEV in the 12 months ending at `end` − BEV in the previous 12 months) ÷ previous × 100; unavailable without 24 months of data.
- **BEVs per public station** = BEV registrations in the period ÷ stations in the 2025 snapshot (approximate pressure indicator).

Responses are cached in-process for `CACHE_TTL_SECONDS` (default 300) and sent with `Cache-Control: public, max-age=60`.
