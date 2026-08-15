# Web-app plan — turn the CLI into a dynamic, multi-brand product

> **Status (2026-08-15): the free dry-run slice (W0→W1→W4) is BUILT and Dockerized.**
> `server/` (FastAPI + SQLite, 8 tests) + `web/` (Next.js, `npm run build` green) + `Dockerfile.api`
> + `web/Dockerfile` + `docker-compose.yml` → `docker compose up --build` runs the whole stack;
> a user analyzes *any* brand (dry-run, $0) from the browser and browses history. Verified live over
> HTTP end-to-end (e.g. Notion). Remaining: W2/W3/W7 (background jobs + cost-gated live runs in the
> UI), W5 (richer history/brand profiles), W6 (native React+D3 charts instead of the iframe).

**Premise correction (important):** the measurement engine is **already brand-agnostic**.
`app/pipeline.py:run_pipeline(GeoConfig(...))` accepts any brand/category/competitors/engines and
returns a full `GeoReport` (metrics + CIs, reconciliation, findings, recommendations, transcript);
live runs already persist to a SQLite fact store (`data/geo.sqlite`). "Asana" was only the demo
subject. So this plan is **not a rewrite** — it wraps the existing, tested core in an API +
persistence + UI so a user can analyze *any* brand from a browser and browse past runs.

```
┌────────────┐     HTTP/JSON      ┌─────────────────────────────┐
│  Next.js   │  ───────────────►  │  FastAPI (server/)          │
│  (web/)    │  ◄───────────────  │   • /brands /runs /reports  │
│  forms +   │   poll status /    │   • background job runner   │
│  dashboard │   fetch report     │   • preflight cost estimate │
└────────────┘                    │   • reuses app/pipeline.py  │
                                   └──────────────┬──────────────┘
                                                  │ reuses, unchanged
                        ┌─────────────────────────┴───────────────────────┐
                        │  existing core: pocs/* + app/pipeline.py          │
                        │  connectors(+budget guard) · metrics · rigor ·    │
                        │  reconcile · insights · dashboard renderer        │
                        └─────────────────────────┬─────────────────────────┘
                                                  │
                                   ┌──────────────┴──────────────┐
                                   │  SQLite: app.db (new index) │
                                   │  + data/geo.sqlite (facts)  │
                                   └─────────────────────────────┘
```

Keeps the project's ethos: **API keys stay server-side** (never sent to the browser), **dry-run is
the default**, live runs are **budget-guarded + cost-confirmed**, and every honesty element (CIs,
synthetic banner, "not distinguishable" callouts, hedged recommendations, methodology card) carries
into the UI.

---

## Key design decisions (recommendation in **bold**)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Long runs (200 calls ≈ minutes) | block the request / background job | **Background job + status polling.** A `jobs` row in SQLite; FastAPI `BackgroundTasks` (or a tiny worker loop) runs it; the UI polls `GET /runs/{id}`. A real queue (arq/Celery) only if we ever scale beyond one machine. |
| D2 | Progress feedback | none / polling / SSE | **Polling a status+progress field** for v1 (simplest, robust); add SSE later if we want live per-engine progress. Requires a small **progress-callback hook** in `run_pipeline`/`_live_runs`. |
| D3 | Charts in the UI | embed existing HTML dashboard in an iframe / rebuild as React+D3 | **Rebuild the hero charts (dumbbell, CI dot-plots, heatmap) as React+D3 components**, reading the report JSON from the API. The D3 logic already exists in `pocs/dashboard/dashboard.py` to port. (Fast path for a first cut: iframe the rendered HTML, then replace.) |
| D4 | Cost control for live runs | trust / estimate+confirm | **Preflight cost estimate + explicit confirm + server-side budget guard.** Show "~$2.30, within $2/provider caps" before running; the existing `CostLedger` still hard-stops. |
| D5 | Auth / multi-user | none / basic / accounts | **Single-user, local, no auth for v1.** Note a simple token gate before any shared/hosted deployment. |
| D6 | Persistence | reuse fact store / new index DB | **New `server/app.db`** (brands, runs, reports, jobs) as the app index; keep `data/geo.sqlite` as the raw fact store the pipeline already writes. Both SQLite, both gitignored. |
| D7 | Deployment | local-only / container | **Local-first** (`uvicorn` + `next dev`), matching the project. Add a `docker-compose` later if hosting is wanted. |

---

## Data model — `server/app.db` (SQLite)

```sql
brands(id, name, category, domain, aliases_json, competitors_json,
       competitor_domains_json, created_at)                    -- reusable brand profiles
runs(id, brand_id, mode, engines_json, n_prompts, repeats, locale, seed,
     status, progress_pct, progress_note, est_cost, actual_cost,
     error, created_at, started_at, finished_at)               -- one analysis run
reports(run_id PRIMARY KEY, report_json)                       -- the GeoReport JSON blob
-- jobs are just runs with status in {queued, running, done, error}; no separate table needed.
```
Raw per-call evidence (prompts / answers / citations) continues to live in `data/geo.sqlite`
(the existing fact store); the API reads it back via `app/store_reader.py` for the transcript.

---

## API surface (FastAPI, `server/`)

| Method + path | Purpose |
|---|---|
| `POST /api/estimate` | preflight cost estimate for a proposed run (no spend) |
| `POST /api/runs` | create a run (body = brand config + `mode: dry-run\|live`); returns `run_id`, enqueues the job |
| `GET /api/runs` | history list (paginated) — brand, mode, status, cost, dates |
| `GET /api/runs/{id}` | run status + `progress_pct`/`progress_note` |
| `GET /api/runs/{id}/report` | the `GeoReport` JSON (metrics, reconciliation, findings, recommendations, transcript) |
| `GET /api/runs/{id}/report.html` | the server-rendered dashboard (reuse `render_dashboard`) — handy for iframe/export |
| `GET/POST /api/brands` | list / save reusable brand profiles |
| `GET /api/health` | liveness + configured-engines (which keys are present, booleans only) |

Server-only concerns: load `.env` server-side; **never** return key values (only presence
booleans); enforce the `CostLedger` before any live call; validate/limit `n_prompts`×`repeats` so a
request can't blow the budget.

---

## Frontend (Next.js, `web/`)

Pages / flows:
1. **New Analysis** — a form: brand, category, aliases, competitors (+ their domains), engines
   (multiselect), prompts, repeats, and a **Dry-run ⇄ Live** toggle. On Live, show the preflight
   **cost estimate + confirm** dialog.
2. **Run progress** — after submit, poll status; show a progress bar + per-stage note
   ("querying perplexity, prompt 7/10"); handle errors.
3. **Report** — the dashboard for that run: hero stat tiles, the **mention-vs-citation gap**
   dumbbell, per-engine **CI dot-plots**, the **overlap heatmap**, distinguishability verdicts,
   **findings** + **recommendations**, top-cited domains, and the **evidence transcript**
   (collapsible). "Download HTML/JSON" buttons.
4. **History** — table of past runs (brand, mode, date, cost, status) → open any report; re-run a
   brand with one click; save/reuse brand profiles.

Honesty carried into the UI: CIs on every rate; a loud **synthetic banner** on dry-runs; "NOT
distinguishable (within noise)" badges; recommendations labelled *directional hypotheses*; the
methodology card + caveats verbatim.

---

## Task graph (phased)

> Convention mirrors `TASKS.md`: POC/verify-first, tests throughout, secrets server-side, SQLite,
> honesty preserved. Each phase is independently demoable.

### W0 — Scaffolding
- `server/` (FastAPI app, `app.db` schema + migrations, config loads `.env`), `web/` (Next.js +
  TypeScript). Shared: import the existing pipeline (add `server/` to the path shim like `app/`).
- Health endpoint reports which engine keys are present (booleans only). **Done when:** `GET
  /api/health` works; `next dev` renders a placeholder.

### W1 — Backend: dry-run analysis end-to-end (no money) ⭐ do first
- `POST /api/runs` (dry-run) → runs `run_pipeline` synchronously for dry-run (fast), stores the
  `GeoReport` in `reports`, returns `run_id`. `GET /api/runs/{id}/report` returns it.
- Brand + run + report persistence in `app.db`. **Tests:** API tests with FastAPI `TestClient`
  (dry-run only, offline). **Done when:** POST a brand → GET a full report JSON, all offline.

### W2 — Background jobs + progress
- Job runner: dry-run stays sync; **live** runs go to a background task; `runs.status`/
  `progress_pct`/`progress_note` updated as it goes. Add a **progress callback** to
  `run_pipeline`/`_live_runs` (engine/prompt counter) — a small, tested core change.
- `GET /api/runs/{id}` returns live status. **Done when:** a (mocked) long run reports progress and
  finishes; polling shows it.

### W3 — Cost control for live runs
- `POST /api/estimate` (reuse `connectors.preflight_estimate`) → per-provider estimate + total.
- `POST /api/runs {mode:live}` requires an acknowledged estimate; the `CostLedger` guard runs
  server-side; requests that would exceed caps are rejected pre-flight. **Done when:** an
  over-budget request is refused before any call; a within-budget one records actual cost.

### W4 — Frontend: form → dry-run report
- New Analysis form (validated) → `POST /api/runs` (dry-run) → poll → **Report page** rendering the
  metrics with CIs, findings, recommendations. Start charts by **iframing** `report.html`, then
  (W6) replace with React components. **Done when:** a user analyzes any brand (synthetic) and sees
  a full report in the browser.

### W5 — Frontend: history + brand profiles
- History table (from `GET /api/runs`), open past reports, save/reuse brand profiles. **Done when:**
  past runs persist across restarts and reopen.

### W6 — Native React+D3 charts
- Port the dumbbell / CI dot-plots / overlap heatmap / top-domain bars from
  `pocs/dashboard/dashboard.py` into React+D3 components fed by the report JSON; drop the iframe.
  **Done when:** charts render natively, responsive, with tooltips, honesty intact.

### W7 — Live runs in the UI + polish
- Wire the Live toggle + cost-confirm dialog to `POST /api/runs {mode:live}`; progress view; error
  and empty states; "download HTML/JSON"; a short README for `server/` + `web/`. **Done when:** a
  user runs a real brand live, watches progress, and gets the report — under budget.

**Cross-cutting:** keys never leave the server; dry-run default everywhere; CIs + synthetic banner +
distinguishability + hedged recommendations preserved in every view; `app.db` and `data/` gitignored;
tests at each phase (pytest for the API, a few Playwright/RTL tests for the UI).

---

## Effort & sequencing
- **Fastest meaningful milestone:** W0→W1→W4 = *"analyze any brand in the browser (dry-run, free)."*
  That alone delivers the dynamic multi-brand app the request asks for, with $0 risk.
- **Then** W2/W3/W7 add live runs safely; W5 adds history; W6 upgrades the charts.
- Rough size: W1 small (the core is done), W2–W3 medium (jobs + cost gating are the real work),
  W4–W6 medium-large (frontend), W7 small-medium.

## Risks / notes
- **Money:** the only real hazard — mitigated by dry-run default, preflight estimate + confirm, and
  the server-side `CostLedger` hard cap. Consider a global daily ceiling too.
- **Long jobs on a single process:** fine locally; if hosted, move to a real task queue (D1).
- **Don't fork the honesty layer:** the UI must render `insights`/`rigor` output as-is — no new
  "cleaner" numbers that drop the intervals.
- **Scope discipline:** auth, multi-tenant, and hosting are explicitly deferred (D5/D7).
