# `server/` — GEO web API (FastAPI)

A thin HTTP layer over the existing, already brand-agnostic pipeline (`app/pipeline.py`) so any
brand can be analyzed from a browser and past runs can be browsed. Reuses the pipeline + POCs
unchanged via `bootstrap.ensure_paths()`; persists to a SQLite index (`db.py`, `data/app.db`).

## Endpoints
| Method + path | Purpose |
|---|---|
| `GET /api/health` | liveness + which engine keys are configured (**booleans only**) |
| `POST /api/estimate` | rough per-provider cost estimate for a run (no spend) |
| `POST /api/runs` | create + run an analysis. **Dry-run is synchronous** ($0, offline) and returns the report inline; **live is gated (HTTP 400)** — use the CLI |
| `GET /api/runs` | run history (most recent first) |
| `GET /api/runs/{id}` | run status/detail |
| `GET /api/runs/{id}/report` | the `GeoReport` JSON |
| `GET /api/runs/{id}/report.html` | the full dark D3 dashboard (reuses `pocs/dashboard`) |
| `GET/POST /api/brands` | list / save reusable brand profiles |

Interactive docs at `/docs` (Swagger) when running.

## Run
```bash
uv run uvicorn server.main:app --reload        # http://localhost:8000
uv run pytest server -q                         # 8 offline tests (dry-run, TestClient)
```

## Honesty / safety carried over
- **Keys stay server-side** (loaded from `.env`); the API never returns key values.
- **Dry-run default; live gated** so the web surface can't spend money.
- Reports render `rigor`/`insights` output as-is — CIs on every rate, synthetic banner,
  distinguishability verdicts, hedged recommendations. No new "cleaner" numbers.
- `data/app.db` + `data/geo.sqlite` are gitignored.

## Notes
- `GEO_APP_DB` sets the index DB path (default `data/app.db`); `GEO_CORS_ORIGINS` the allowed
  browser origin (default `http://localhost:3000`).
- Background jobs + live runs + native React charts are the next phases (see
  `docs/WEBAPP_PLAN.md`); this slice delivers the dry-run product end-to-end.
