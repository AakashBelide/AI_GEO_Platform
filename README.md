# AI_GEO Platform — measurement-honest Generative Engine Optimization

A local-only research + engineering project that measures **how brands show up in AI answer
engines** (ChatGPT, Perplexity, Google/Gemini, Claude) — and reports the *uncertainty* the
commercial GEO market hides.

> **SEO** optimizes for Google's blue links. **GEO** (Generative Engine Optimization) is the
> successor problem: getting your brand **mentioned and cited** in AI-generated answers. The catch
> is that AI answers are non-deterministic and drift 40–60% month-to-month, yet the entire
> commercial GEO market ships a single "visibility score" anyway, and **none of ~28 surveyed tools
> report any statistical confidence.** This project builds the honest version: confidence
> intervals, cross-engine reconciliation, causal attribution, and the underlying evidence.

**Status:** 🟢 **229 tests passing, ruff-clean**, live-verified on all four engines. Ships as a
CLI *and* a Dockerized web app (FastAPI + Next.js + SQLite) that analyzes **any brand** — see
[Run with Docker](#web-app-dynamic-multi-brand--run-with-docker).

---

## The headline finding (real data)

A live run on **Asana** vs Monday.com / Trello / ClickUp — 10 prompts × 5 repeats × 4 engines,
200 real API calls, ≈ $2.55 under a hard $2/provider budget cap:

| Engine | Mentions Asana | Cites **asana.com** |
|---|---:|---:|
| OpenAI | **82%** | **0%** (0/50) |
| Anthropic | **80%** | **0%** (0/50) |
| Perplexity | 74% | 40% |
| Gemini | 60% | 14% |

**OpenAI and Anthropic recommend Asana in ~80% of answers but never link `asana.com`** — they
cite third-party review sites; Perplexity and Gemini *do* link the brand. A single blended
"visibility score" hides that *mentioned* ≠ *cited*, and that it differs by engine. Cross-engine
citation overlap was **12.7%** (the engines cite largely different webs). See
[`docs/DEMO_WRITEUP.md`](docs/DEMO_WRITEUP.md).

---

## What makes it *honest* (the differentiators)

- **Confidence intervals on every rate** — Wilson intervals + cluster bootstrap; a single-run
  score is never shown without its interval. A degenerate estimate *looks* degenerate.
- **Statistical distinguishability** — a two-proportion test states when two engines are *not*
  distinguishable ("within noise"), so the tool never claims a difference that isn't real.
- **Cross-engine reconciliation** — one disclosed normalization + a pairwise-overlap heatmap +
  an auto-generated methodology card, because every vendor's "Share of Voice" means something
  different.
- **Causal attribution** — a difference-in-differences estimator with a holdout control that nets
  out background drift, so "impact" is a *causal uplift with a CI*, not a raw before/after delta.
- **Evidence + hedged recommendations** — the report includes the exact prompts, each model's
  answer and citations, and recommendations tied to concrete domains/engines/counts (labelled as
  directional hypotheses, not proven levers).
- **A caught measurement artifact** — Gemini's grounding URLs are redirect wrappers; a naive tool
  would report "Gemini cites nothing you do." We found and fixed it (real domain lives in
  `web.title`).

---

## Architecture

Every capability was built and tested as a POC first, then wired behind one CLI (`app/geo.py`).

| POC | What it does | Tests |
|---|---|---:|
| `pocs/connectors` | 4 answer engines behind one interface + a **$2/provider budget guard** | 25 |
| `pocs/factstore` | append-only SQLite fact store (one immutable row per engine call) | 7 |
| `pocs/rigor` | Wilson CIs, cluster bootstrap, two-proportion test, variance, drift | 22 |
| `pocs/onboarding` | brand → intent-labeled, branded-skew-checked prompt set (R1) | 16 |
| `pocs/metrics` | mention / citation / SoV / position, each **with a CI** (R2) | 20 |
| `pocs/keyword_to_prompt` | SEO keyword list → GEO prompts (R3) | 14 |
| `pocs/reconcile` | cross-engine overlap + SoV + divergence + methodology card (O3) | 13 |
| `pocs/causal` | difference-in-differences + holdout control (O2) | 10 |
| `pocs/crawler` | robots-respecting, rate-limited **sandbox-only** site AI-readability audit | 12 |
| `pocs/insights` | evidence-tied findings + hedged GEO recommendations | 20 |
| `pocs/dashboard` | GeoReport → dark **Tailwind + D3** HTML dashboard | 24 |
| `app/` | the `geo` CLI (`run` / `report` / `audit`) wiring it all together | 33 |
| `server/` | FastAPI + SQLite web API over the pipeline (dry-run; multi-brand tested) | 13 |
| `web/` | Next.js frontend (form → report → history); dark theme, iframes the D3 dashboard | — |

---

## Quick start

Requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/). No other global installs.

```bash
make install                 # uv sync
make verify                  # 229 tests + ruff, all offline ($0)   (make help for all targets)

# End-to-end DRY-RUN (synthetic data, $0, deterministic — the default):
uv run python app/geo.py run --brand "Asana" --category "project management software" \
    --target-domain asana.com --competitor-domains monday.com,trello.com,clickup.com

# LIVE (real engines, budget-guarded to $2/provider) — add --live:
uv run python app/geo.py run --brand "Asana" --category "..." \
    --target-domain asana.com --competitor-domains monday.com,trello.com --live

# Render a saved report into the dark Tailwind+D3 dashboard (opens in a browser):
uv run python app/geo.py report --input data/reports/<file>.json --store data/geo.sqlite

# Site-side AI-readability audit of a scrape-safe sandbox:
uv run python app/geo.py audit
```

### Using live engines
```bash
cp .env.example .env         # then add your OpenAI / Perplexity / Gemini / Anthropic keys
# .env, secrets/, and data/ are gitignored and MUST NEVER be committed.
```
Live runs default to the cheapest capable models (`gpt-4o-mini`, `sonar`, `gemini-2.5-flash`,
`claude-haiku-4-5`) and every call passes a pre-flight budget guard — a provider can never exceed
its $2 cap. The dashboard loads Tailwind + D3 from CDNs, so *viewing* it needs internet.

---

## Web app (dynamic, multi-brand) — run with Docker

A FastAPI backend + Next.js frontend let anyone analyze **any brand** from the browser and browse
past runs (stored in SQLite). The whole stack comes up with one command.

```bash
# 1. Provide env vars (dry-run needs no keys; see "Environment variables" below)
cp .env.example .env          # edit .env if you want to add keys / change the budget

# 2. Build + start both services
docker compose up --build

# 3. Open the app
#    Frontend  → http://localhost:3000
#    API docs  → http://localhost:8000/docs   (FastAPI Swagger UI)
```

That's it — a new person only edits `.env` and runs `docker compose up --build`. The backend
persists runs/reports to `./data` (mounted volume, gitignored) so history survives restarts.

**What the web UI does:** enter a brand + category + competitors → get the full report (per-engine
metrics **with confidence intervals**, the mention-vs-citation gap, cross-engine reconciliation,
findings + recommendations, and the interactive dashboard) → all runs saved under **History**.

> **Note — the web UI runs in DRY-RUN mode** (deterministic synthetic data, **$0**, no keys
> needed) so it's safe to demo and can't spend money. **Live** runs (real engines, real cost) are
> intentionally available only via the CLI (`uv run python app/geo.py run … --live`) in this
> build, so a public/hosted UI can never rack up charges.

### Environment variables

| Var | For | Needed? | Default |
|---|---|---|---|
| `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` | live engine calls (CLI) | only for `--live` | — |
| `BUDGET_USD_PER_PROVIDER` | hard per-provider spend cap on live runs | no | `2.00` |
| `GEO_APP_DB` | backend run/report index (SQLite) | no | `data/app.db` |
| `GEO_CORS_ORIGINS` | browser origin allowed to call the API | no | `http://localhost:3000` |
| `NEXT_PUBLIC_API_BASE` | API base the browser calls (inlined at build) | no | `http://localhost:8000` |

**Keys never reach the browser** — they're read server-side only; `/api/health` reports which
engines are configured as booleans, never values. The dashboard loads Tailwind + D3 from CDNs, so
viewing it needs internet.

### Run without Docker (local dev)
```bash
# Backend (terminal 1)
uv sync && uv run uvicorn server.main:app --reload      # http://localhost:8000
# Frontend (terminal 2)
cd web && npm install && npm run dev                     # http://localhost:3000
```

## Documentation

- [`RESEARCH.md`](RESEARCH.md) — the research report and thesis (evidence-tiered).
- [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md) — teardown of ~28 tools + what's buildable.
- [`docs/OBSERVATIONS_AND_ANALYSIS.md`](docs/OBSERVATIONS_AND_ANALYSIS.md) — standing analysis:
  observations, interpretation, measured metrics, opinions, and an **honesty ledger** (each number
  cites a reproduction script; unmeasured claims are labelled).
- [`docs/DEMO_WRITEUP.md`](docs/DEMO_WRITEUP.md) — the end-to-end demo narrative + headline finding.
- [`docs/GA4_ATTRIBUTION.md`](docs/GA4_ATTRIBUTION.md) — detecting AI-referral traffic in GA4.
- [`ANALYSIS_REPORT.md`](ANALYSIS_REPORT.md) — dated running log of decisions, costs, findings.
- [`TASKS.md`](TASKS.md) — the build plan and task graph.

---

## Safety & ethics

- **Official APIs, not scraping**, for the answer engines. Google AI Overviews is *proxied* via
  Gemini grounding and documented as such — never scraped.
- The crawler touches **scrape-safe sandbox sites only** (default `books.toscrape.com`), respects
  `robots.txt`, rate-limits, and caps pages — it must never risk an IP block or crawl a real
  client site.
- **No API keys, secrets, PII, or run data are committed.** Real keys live in `.env`; sensitive
  data in `secrets/`; run artifacts (fact store, cached responses, reports) in `data/` — all
  gitignored. Only placeholder templates (`.env.example`) are tracked.

---

## Notes

Built as an independent research project for a graduate course on computational skepticism in AI.
Numbers throughout are backed by reproduction scripts; anything not measured is labelled a judgment
or "not yet substantiated." Local-only — no cloud deployment.
