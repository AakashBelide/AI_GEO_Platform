# AI_GEO Platform — Web Frontend

A Next.js (App Router) frontend for the AI_GEO Platform, a **measurement-honest**
Generative Engine Optimization analysis tool. Every rate is shown with its
confidence interval; dry-runs are loudly flagged as synthetic; live runs are gated.

## Stack

- Next.js 15 (App Router) + React 19 + TypeScript
- Plain CSS (CSS variables, dark theme) — no CSS framework
- `output: "standalone"` for a slim Docker image

## Configuration

The frontend talks to the FastAPI backend at `NEXT_PUBLIC_API_BASE`.

```bash
cp .env.example .env.local
# edit if needed; default is http://localhost:8000
```

| Variable               | Default                 | Notes                                             |
| ---------------------- | ----------------------- | ------------------------------------------------- |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Backend base URL. Inlined at build time (public). |

## Develop

```bash
npm install
npm run dev          # http://localhost:3000
```

Start the backend separately:

```bash
# from the AI_GEO repo root
uvicorn server.main:app --reload   # http://localhost:8000
```

## Build (the verification gate)

```bash
npm install
npm run build        # typecheck + production build must pass
npm run start        # serve the production build
```

## Docker

```bash
# build (bake in the API base if it differs from localhost)
docker build -t ai-geo-web \
  --build-arg NEXT_PUBLIC_API_BASE=http://localhost:8000 .

# run
docker run --rm -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE=http://localhost:8000 \
  ai-geo-web
```

Note: `NEXT_PUBLIC_*` values are inlined into the client bundle at **build**
time. The runtime `-e` flag is provided for parity, but the effective value is
the one passed as `--build-arg` when the image was built.

## Pages

- **`/`** — New Analysis form. Defaults to dry-run; live is disabled with a money
  note. Submits `POST /api/runs` and routes to the report.
- **`/runs/[id]`** — Report. Synthetic banner on dry-runs, stat tiles, findings +
  recommendations (verbatim), a per-engine table (every rate as `point [lo, hi]
  (n)`), a JSON download, and the full backend D3 dashboard embedded in an
  `<iframe>`.
- **`/history`** — Past runs table linking to each report.

## Honesty guarantees (enforced in the UI)

- No bare rates — mention / citation / share-of-voice always show their CI.
- Dry-runs render a loud amber "SYNTHETIC — not a real measurement" banner.
- Findings and recommendations are rendered verbatim; recommendations are framed
  as directional hypotheses, not guarantees.
- Live runs are disabled in the UI (gated 400 server-side) with the money note.
