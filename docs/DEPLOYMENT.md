# Deploying VoltBharat (Neon + Render + Vercel)

Nothing here runs automatically. Each step creates or changes an external service, so do it only when you decide to deploy. The app must work locally first (see README).

## 1. Database — Neon (PostgreSQL)

1. Create a Neon project and database (e.g. `voltbharat`). Copy the **pooled** connection string.
2. Convert it to the SQLAlchemy/psycopg form and keep `sslmode=require`:
   `postgresql+psycopg://USER:PASSWORD@HOST/voltbharat?sslmode=require`
3. Load the data **from your machine** (the raw CSVs never leave it; only aggregated tables are uploaded):

```powershell
cd D:\Projects\VoltBharat
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/voltbharat?sslmode=require"
.\.venv\Scripts\python -m etl.run_pipeline --load-db     # creates schema, validates, loads in one transaction
Remove-Item Env:DATABASE_URL
```

`init_db` tries to create the database and continues if it lacks permission (Neon databases already exist). Rerunning is safe: dimensions are upserted and facts replaced in a single transaction.

## 2. API — Render

1. Push the repository to GitHub (raw data, `.env` and processed files are git-ignored).
2. In Render: **New → Blueprint**, select the repo. `render.yaml` defines:
   - build: `pip install -r backend/requirements.txt`
   - start: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT --proxy-headers`
   - health check: `/health`
3. Set environment variables in the Render dashboard:

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Neon URL from step 1 |
| `CORS_ORIGINS` | your Vercel URL(s), comma-separated, e.g. `https://voltbharat.vercel.app` |
| `CACHE_TTL_SECONDS` | `600` (data only changes on reload) |

4. Verify: `https://<service>.onrender.com/health` → `{"status":"ok","database":"ok",...}` and `/docs`.

## 3. Frontend — Vercel

1. **New Project** → import the repo → **Root Directory: `frontend`**. `frontend/vercel.json` sets the Vite build, `dist` output and SPA rewrites.
2. Environment variable: `VITE_API_BASE_URL = https://<service>.onrender.com` (no trailing slash). It is baked in at build time; redeploy after changing it.
3. Add the Vercel domain to `CORS_ORIGINS` on Render.

## Production checklist

- [ ] `/health` returns 200 and a recent `last_successful_etl`
- [ ] Browser console shows no CORS errors (origin must match exactly, including `https://` and no trailing slash)
- [ ] Deep links such as `/charging-gap?start=2025-01` load (SPA rewrite)
- [ ] Data Sources page shows the expected ETL run and validation results

## Troubleshooting

| Symptom | Fix |
|---|---|
| UI shows "Cannot reach the VoltBharat API" | Check `VITE_API_BASE_URL` and that the Render service is awake (free plans sleep; first request can take ~1 min). |
| CORS error in the browser | Add the exact frontend origin to `CORS_ORIGINS` and redeploy the API. |
| `/health` returns 503 | `DATABASE_URL` wrong or Neon branch suspended; check the URL includes `sslmode=require`. |
| API 503 `no_data` | The database is empty: run step 1 again. |
| Map shows a ranked list instead | `public/geo/india_states.geojson` missing from the build: run `npm run sync:geo` before building. |
