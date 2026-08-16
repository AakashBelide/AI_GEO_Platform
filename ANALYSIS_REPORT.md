# ANALYSIS REPORT — AI_GEO Platform

A running, referenceable log of what was built, the decisions made, the models/costs used,
and what was learned. Append new dated entries at the top of §5 as work continues.

_Last updated: 2026-08-14._

---

## 1. Project in one line
A **measurement-honest** GEO platform: it reports the statistical uncertainty (confidence
intervals, variance, cross-engine disagreement) that the entire commercial GEO market omits.
Thesis + evidence in `RESEARCH.md`; competitor teardown in `COMPETITIVE_LANDSCAPE.md`; build
plan in `TASKS.md`.

## 2. What exists today (all tested, all green)
| Component | Task | Location | Tests | Needs keys? |
|---|---|---|---|---|
| Statistical rigor (Wilson CIs, cluster-bootstrap SoV, distinguishability, variance, drift) | O1 | `pocs/rigor/` | 22 | No |
| Safe site crawler + AI-readability audit | C1 / §7.3 | `pocs/crawler/` | 12 | No |
| Budget guard / cost ledger ($2/provider hard cap) | F3 | `pocs/connectors/budget.py` | 10 | No |
| Append-only SQLite fact store | F2 | `pocs/factstore/` | 7 | No |
| Cross-engine citation connectors (4 engines) | F3 | `pocs/connectors/connectors.py` | 15 | Yes (live) |
| Onboarding: brand → intent-labeled, skew-checked prompt set | R1 | `pocs/onboarding/` | 16 | No |
| Core metric set with CIs (mention/citation/SoV/position/sentiment) | R2 | `pocs/metrics/` | 20 | No |
| Keyword → prompt bootstrapping (intent-inferred, deduped) | R3 | `pocs/keyword_to_prompt/` | 14 | No |
| Cross-engine reconciliation (overlap, SoV, divergence, methodology card) | O3 | `pocs/reconcile/` | 13 | No (live runner optional) |
| End-to-end pipeline + `geo run`/`report`/`audit` CLI | A1/C1 | `app/` | 24 | No (offline); `--live` optional |
| Dark dashboard (Tailwind+D3: dumbbell gap, CI dot-plots, heatmap, transcript) | A2 | `pocs/dashboard/` | 24 | No |
| Interpretation layer: findings + GEO recommendations (evidence-tied) | A2 | `pocs/insights/` | 20 | No |
| Causal attribution (difference-in-differences + holdout control) | O2 | `pocs/causal/` | 10 | No |

| Web API (FastAPI + SQLite index; multi-brand + edge-case tested) | webapp | `server/` | 13 | No |

**Total: 229 tests passing, ruff clean.** Every POC runs its suite fully offline (external APIs
mocked/replayed, crawler uses fixtures) so the suite never spends budget or touches the network.

## 3. Cost controls (money safety)
- **Budget: $2 per provider**, set in `.env` as `BUDGET_USD_PER_PROVIDER=2.00`.
- Enforced by `CostLedger` — persisted to `data/cost_ledger.json` (gitignored) so the cap
  survives restarts. `guard()` runs **before** each call; a test proves the network is never
  touched once a provider is over budget.
- Raw responses cached under `data/cache/` → re-analysis never re-calls the API.
- Cost = tokens × published price + per-call tool fee (deliberately conservative / rounds up).

## 4. Model choices (cheapest-but-decent, per the budget)
| Provider | Model | Why | Notes |
|---|---|---|---|
| OpenAI | `gpt-4o-mini` | cheap; supports Responses API `web_search` | ~$0.15/$0.60 per M + ~$0.025/search |
| Perplexity | `sonar` | cheapest web-grounded LLM | $1/M in+out; search included |
| Gemini | `gemini-2.5-flash` | cheap; Google Search grounding | **proxy for AI Overviews — documented, not identical** |
| Anthropic | `claude-haiku-4-5` | cheapest Claude ($1/$5) | web search uses **basic `web_search_20250305`** (the `_20260209` dynamic-filtering variant needs Opus/Sonnet tiers) |
Overridable via `.env` (`OPENAI_MODEL`, `PERPLEXITY_MODEL`, `GEMINI_MODEL`, `ANTHROPIC_MODEL`).

## 5. Run log & findings

### 2026-08-15 — Web app: dynamic multi-brand product (FastAPI + Next.js + SQLite + Docker)
- Wrapped the (already brand-agnostic) pipeline in a **web app** so any brand can be analyzed from a
  browser — not just the Asana demo. Built the free dry-run slice (W0→W1→W4 of `docs/WEBAPP_PLAN.md`):
  - **`server/`** — FastAPI + SQLite index (`app.db`): `POST /api/runs` (dry-run, synchronous, $0),
    `GET /api/runs[/{id}[/report[.html]]]`, `/api/brands`, `/api/estimate`, `/api/health`. Reuses
    `pipeline`/`dashboard` unchanged via `bootstrap.ensure_paths()`. **Live gated (HTTP 400)** so the
    web surface can't spend money; **keys stay server-side** (health returns booleans only). 8
    TestClient tests. `pyproject` gains fastapi + uvicorn; pytest `pythonpath=["."]`.
  - **`web/`** — Next.js 16 / React 19 / TS (dark theme): New Analysis form (dry-run default, Live
    disabled with a money note), Report page (synthetic banner, stat tiles, verbatim findings +
    recommendations, per-engine table with **CIs**, and the D3 dashboard via `<iframe>`), History.
    `npm run build` green (standalone output).
  - **Docker** — `Dockerfile.api` (uv) + `web/Dockerfile` (node:22 standalone) + `docker-compose.yml`
    (+ `.dockerignore`, `.env.example`): `cp .env.example .env && docker compose up --build` →
    frontend `:3000`, API `:8000`. `./data` mounted so history persists.
- **Verified end-to-end over real HTTP** (uvicorn, not just TestClient) on a NON-Asana brand
  (Notion): dry-run → report with per-engine CIs (openai citation 0.267 [0.171, 0.390], n=60), 5
  findings, 4 recommendations, overlap 0.33; history + `report.html` served. Suite now **224**, ruff
  clean. (Docker images not built locally — daemon was down; compose validated, `uv.lock` present.)

### 2026-08-15 — Polish: Makefile, `geo audit`, docs consistency
- **`Makefile`** — reproducibility one-liners: `make verify` (216 tests + ruff, all offline, $0),
  `make demos` (the three offline demos), `make report`, `make audit`, `make help`.
- **`geo audit`** — wired the C1 crawler into the CLI (`app/geo.py`), so **all POCs are now
  reachable from the one entrypoint**: crawls a scrape-safe sandbox (default books.toscrape.com,
  robots-respected, rate-limited, page-capped) and prints per-page AI-readability scores + writes
  JSON. Core factored into a testable `run_audit` (injected fetcher) — 4 offline tests. Verified
  live on the sandbox (2 pages, mean AI-readability 0.65). Suite **216**, ruff clean.
- Consistency sweep of all docs (test counts, forward-looking "Next:" lines, self-contained claims)
  — clean; refreshed README doc index (added the A3/A4 docs) and quick start.

### 2026-08-14 — O2 (causal) + A3/A4 docs → all planned tasks complete
- **O2 `pocs/causal/` (10 tests).** Difference-in-differences with a **holdout control** that nets
  out background drift; reports causal uplift with a **cluster-bootstrap CI** + significance (CI
  excludes 0), alongside the naive delta + measured drift. `demo.py` shows the drift trap: a
  drift-only experiment reads **+0.11 naive** (looks like a win) but DiD correctly says **not
  significant**; a real +0.15 effect is recovered as **+0.14 [0.09, 0.18]**. Validated offline on
  simulated known-effect+known-drift data. Live before/after CLI integration is future work.
- **A3 `docs/GA4_ATTRIBUTION.md`** (documentation-only): GA4 custom-channel-group + source-regex
  method for AI-referral traffic, cross-referenced with the supply-side citation data; honest
  limits (dark/Direct ⇒ lower bound; correlation not causation).
- **A4 `docs/DEMO_WRITEUP.md`**: self-contained narrative of the live Asana run + headline finding
  with reproduction and caveats.
- Also fixed stale TASKS.md markers (F1/F2/F3/O1/C1 were done but unmarked). **Every task in the
  plan is now ☑** (only cross-cutting X + small deferred niceties remain). Suite **212**, ruff clean.

### 2026-08-14 — A2 charts moved to D3.js (from Chart.js)
- Swapped the charting layer to **all-D3 (v7, CDN)**; Chart.js removed. D3 draws the honesty
  visuals properly instead of faking them: the mention-vs-citation gap is now a **dumbbell**
  (mention ●───● citation per engine; flagged engines red), the per-engine rates are **dot-plots
  with lo→hi error whiskers + caps** (no visual clamping — degenerate SoV looks wide), top-domains
  are D3 small-multiple bars, and the overlap is a **D3 heatmap** (sequential color scale + value
  cells + gradient legend). One shared tooltip; responsive (viewBox + debounced resize redraw);
  all builders no-op gracefully on missing/single-engine data. Tailwind dark theme unchanged.
- Kept every honesty element; JSON blob still `</`-escaped, server text HTML-escaped. Dashboard
  suite still 24 tests (rewritten for D3 mounts); suite **202**, ruff clean. Regenerated
  `data/reports/asana_2026-08-14.html` (~231 KB, 9 D3-populated SVG mounts).

### 2026-08-14 — A2 redesign: modern dark dashboard (Tailwind + Chart.js)
- Rewrote `pocs/dashboard/dashboard.py` into a **dark analytics dashboard**: sticky nav, hero +
  stat tiles, and interactive **Chart.js** charts — the mention-vs-citation gap (grouped bars),
  per-engine rates as point + floating **95% CI band**, and per-engine top-domain small-multiples;
  the cross-engine overlap is a CSS-grid **Jaccard heatmap**. Styling via **Tailwind** (both from
  CDN). Findings/recommendations promoted near the top; evidence transcript kept as `<details>`.
- **Trade-off (per the user's explicit choice):** the rendered page now depends on the Tailwind +
  Chart.js CDNs, so it is **no longer a fully offline single file** — viewing needs internet. The
  `render_dashboard` function stays pure/offline-tested; the report JSON is injected as an escaped
  (`</`→`<\/`) `<script id="geo-report">` blob and all server text is HTML-escaped. Every honesty
  element preserved (CIs visible, synthetic banner, distinguishability verdicts, verbatim caveats).
- 24 dashboard tests (rewritten); regenerated `data/reports/asana_2026-08-14.html` (~232 KB, 8
  canvases). Suite now **202 tests**, ruff clean.

### 2026-08-14 — A2 extended: evidence drill-down + findings/recommendations
- **`pocs/insights/` (20 tests) + `app/store_reader.py` (6 tests).** The dashboard now carries the
  underlying EVIDENCE and an INTERPRETATION layer, both reconstructed from `data/geo.sqlite` for the
  real Asana run (no re-spend, no network):
  - **Evidence:** the 10 prompts, and per engine a collapsible `<details>` transcript per prompt with
    the model's actual answer + citations (url/domain/position); plus a **top-cited-domains-per-engine**
    table (target highlighted).
  - **Findings** (deterministic, restate the numbers) and **Recommendations** (evidence-tied, hedged as
    directional hypotheses; every one names a concrete domain/engine/count; causal proof deferred to O2).
    `pocs/insights/insights.py` reuses `pocs/rigor.two_proportion_test`.
- Pipeline now populates `prompts/transcript/top_domains/findings/recommendations` natively; `geo report
  --store <db>` enriches a saved JSON from the fact store. Real findings on the Asana data e.g.:
  *"openai mentions Asana in 82% of answers but cites asana.com in 0%"*, *"most-cited domains for this
  category are thedigitalprojectmanager.com (101), project-management.com (94), reddit.com (77)…"*,
  *"anthropic and openai are NOT statistically distinguishable on citation rate (p=1.00)"*.
- Regenerated `data/reports/asana_2026-08-14.html` (118 KB, 40 transcript blocks). Suite now **199 tests**.

### 2026-08-14 — A2: local HTML dashboard (visual, offline, no server)
- **`pocs/dashboard/` (15 tests) + `geo report` subcommand (4 tests).** Renders a saved GeoReport
  JSON into ONE self-contained HTML file — inline CSS + hand-written SVG, no network/JS/CDN, opens
  directly in a browser. Honesty-first visuals: every rate is a **point + 95% CI band** (never a
  bare score); a synthetic dry-run is loudly banner-flagged as "not a real measurement"; the
  **mention-vs-citation gap** is highlighted in red per engine; cross-engine pairs get a
  **two-proportion-test distinguishability verdict** (refuses to imply a within-noise difference);
  the methodology card + caveats render verbatim. Reuses `pocs/rigor` via the sys.path shim.
- Generated the real artifact: `data/reports/asana_2026-08-14.html` (30 KB, 20 inline SVGs, 0
  external asset links). On it, OpenAI & Anthropic are flagged "mentioned, not cited", and
  anthropic-vs-openai citation rate is correctly marked "NOT distinguishable (within noise)".
- Usage: `uv run python app/geo.py report --input data/reports/<file>.json`. Suite now **164 tests**.

### 2026-08-14 — First full LIVE brand run (Asana) — the headline finding
Ran the whole pipeline live: `geo run --brand Asana … --live`, 10 prompts × 5 repeats × 4 engines
(200 calls). **Cost ≈ $2.55** (openai $1.28 · anthropic $0.90 · perplexity $0.27 · gemini $0.09 —
all ≪ $2 cap; cumulative ≈ $2.84).
- **Mention ≠ citation, and it's engine-specific (the money finding).** OpenAI & Anthropic
  **mentioned** Asana ~80% of answers but cited **asana.com in 0/50 runs each** — they linked review
  sites (techradar, capterra, thedigitalprojectmanager). Perplexity & Gemini *did* link asana.com
  (30 and 25 times; citation rate 0.40 and 0.14). A single blended "visibility score" would hide
  that Asana is *recommended-but-never-linked* on OpenAI/Anthropic and *linked* on Perplexity/Gemini.
- **Cross-engine citation overlap = 12.7%** — third independent corroboration of ~11%, now on a real
  brand.
- **SoV still degenerate** even at 50 runs/engine (only n=1–4 prompts per engine surfaced the brand
  universe; CIs span [0.25,1.0] or [0,0]) — flagged, not reported. Real SoV needs many more prompts.
- Every rate carries a Wilson CI; report persisted to `data/geo.sqlite` + `data/reports/` (gitignored).

### 2026-08-14 — A1: end-to-end `geo run` CLI built (offline dry-run default)
- **`app/` (16 tests).** Wires the passing POCs into one command: brand → prompts (R1) → runs
  (synthetic dry-run / live connectors) → fact store (F2, live) → metrics with CIs (R2/O1) →
  cross-engine reconciliation + methodology card (O3). Reuses POC modules unchanged via
  `app/_paths.py`; orchestration in `pipeline.py`, CLI in `geo.py`.
- **Dry-run is the default and spends $0** (deterministic synthetic data, clearly labeled "NOT a
  measurement"); `--live` is required to call real engines, still under the $2/provider guard.
  Outputs human tables **and** a machine-readable JSON report under `data/reports/` (gitignored);
  live runs persist to `data/geo.sqlite`.
- Verified end-to-end on a dry-run (Asana / 4 engines / 30 prompts × 8): CIs on every metric,
  realistic synthetic overlap (~0.43), divergence explainer fires. Suite now **145 tests**.
  Milestone 4 (A1) done; remaining open lane is O2 (causal).

### 2026-08-13 — O3 follow-up: Gemini redirect artifact FIXED (offline, $0)
- Root cause confirmed: Gemini grounding chunks carry the real publisher domain in **`web.title`**
  (e.g. `tech.co`, `thedigitalprojectmanager.com`) while `web.uri` is the vertexaisearch redirect.
- Fix: `connectors._gemini_domain` reads the domain from `title` when the uri is a redirect
  wrapper (zero network — the redirect is *not* followed). +2 parser tests (connectors → 15).
- Re-derived overlap from the **same cached payloads** (`recompute_from_cache.py`, R-5, no spend):
  Gemini now resolves **52 real domains** (was 1), and the **all-4-engine mean overlap = 0.106
  (≈10.6%)** — an even tighter corroboration of the borrowed ~11%. Gemini↔Perplexity 0.147,
  Gemini↔Anthropic 0.161. Suite now **129 tests**.

### 2026-08-13 — O3 (cross-engine reconciliation) built + first LIVE measurement
- **O3 `pocs/reconcile/` (13 tests, offline).** Cross-engine citation overlap (pairwise Jaccard),
  per-engine SoV under one documented normalization (reuses R2/O1 CIs), a source-ecosystem
  divergence explainer, and an auto-generated machine-readable **methodology card**.
- **Live run** (`reconcile_live.py`, 4 commercial prompts × 4 engines, 1 repeat, **$0.233**):
  - **Our own measured cross-engine overlap ≈ 9.6%** (mean pairwise Jaccard among OpenAI /
    Perplexity / Anthropic) — independently **corroborates the borrowed ~11%** from the
    literature. Top pair Anthropic↔Perplexity = 16.7%; all others 6% or less.
  - **New finding (O-7): Gemini grounding URLs are redirect wrappers**
    (`vertexaisearch.cloud.google.com/grounding-api-redirect/…`), so all 85 Gemini citations
    collapse to **1 unique domain** and show 0 overlap with everyone — a measurement **artifact**,
    not low agreement. Gemini is now excluded from domain-overlap (stated in the methodology card)
    until the redirect is resolved. Evidence in `data/cache/gemini/`.
  - Unique domains/engine: perplexity 57 · openai 32 · anthropic 20 · gemini 1 (artifact).
  - Per-engine SoV was **uninformative at n=1 repeat** (degenerate CIs) — correctly flagged, not
    reported as fact. A multi-repeat run is needed for real SoV.
- Suite now **127 tests**. Cumulative live spend ≈ $0.30 across providers (all ≪ $2 caps).

### 2026-08-13 — R3 (keyword→prompt) built, offline
- **R3 `pocs/keyword_to_prompt/` (14 tests).** Turns an SEO keyword list into intent-labeled
  prompts and merges them into the R1 set. Intent is inferred from **whole-token** modifiers
  (`best`/`pricing`/`vs`/`review`/`buy` → commercial; brand-name → navigational; else
  informational) so `buyer` never triggers `buy`. Merge de-duplicates on a normalized key
  (casefold + collapsed whitespace + stripped trailing punctuation), so `crm` and `What is CRM?`
  don't double-count. Deterministic, no keys. Suite now **114 tests**. Milestone 1 (R) complete.

### 2026-08-13 — R1 (onboarding) + R2 (metrics) built, offline
- **R1 `pocs/onboarding/` (16 tests).** Brand profile → deterministic, intent-labeled prompt
  set. Enforces the **80/10/10** informational/commercial/navigational mix (largest-remainder
  apportionment sums exactly to any `n_total`) and a **branded-skew guard** (≤30% brand-naming
  prompts, else flagged) — the two guards competitors skip. Paraphrase variants feed O1's
  variance design. Pure/deterministic; LLM-drafting is an injectable, un-networked `Callable`.
- **R2 `pocs/metrics/` (20 tests).** Mention / citation / SoV / position — each returned as an
  `Estimate` **with a 95% CI**, reusing `pocs/rigor` (no duplicated stats). SoV is
  cluster-bootstrapped over prompts. Sentiment = injectable LLM-judge **validated with Cohen's
  κ** against a gold set (κ≥0.6 ⇒ trustworthy). Matching is subdomain-aware and substring-safe
  (`blog.acme.com`✓, `fakeacme.com`✗, `Acme`≠`Acmentor`).
- **End-to-end demo** (`pocs/metrics/demo.py`, no network): R1 set → 600 synthetic runs → R2
  recovered the injected 35% citation propensity as `0.360 [0.323, 0.399]` — the CI covers the
  truth, and a single-run score would have hidden it. This is the platform's honest headline.
- **Spend: $0.00** (both POCs and the demo are fully offline/synthetic). Suite now **100 tests**.

### 2026-08-13 — First live smoke test (all 4 engines, 1 short prompt each)
Prompt: _"What are the top 2 project management tools? Answer in one sentence."_

| Engine | Result | Cost | Citations | Note |
|---|---|---|---|---|
| OpenAI `gpt-4o-mini` | ✅ answered | $0.0251 | 0 | didn't search (prompt answerable from knowledge) |
| Perplexity `sonar` | ❌ **401 Unauthorized** | $0 | — | **provided key is rejected — needs a valid key** |
| Gemini `gemini-2.5-flash` | ✅ (empty text) | $0.0001 | 0 | thinking-model returned no text/chunks on a trivial prompt |
| Anthropic `claude-haiku-4-5` | ✅ answered | $0.0126 | 0 | chose not to search ("I don't need to search") |

### 2026-08-13 — Citation-extraction validation (forced web search)
Prompt (forces search): _"Search the web: best AI search visibility (GEO) tracking tools in 2026 … with sources."_ on `claude-haiku-4-5`.
- **✅ 6 citations parsed** end-to-end: frase.io, humanizeai.com, stackmatix.com,
  midastouchinfotech.com, thatmarketingbuddy.com, dageno.ai — with titles + positions.
- Cost $0.0218. Confirms the full loop: budget guard → live call → parse → cost record.

### 2026-08-13 — Perplexity key replaced & verified
- New `PERPLEXITY_API_KEY` works: `sonar` forced-search parsed **14 citations** (Profound,
  dageno.ai, surmado.com, reddit.com, …) for $0.0055. **All 4 engines now live-verified.**
- Note: Perplexity returned Spanish-language results/sources for this session → **locale/geo
  affects the cited source set.** The prompt set (R1) should pin locale explicitly.

**Spend so far (of $2.00 each), cumulative:** OpenAI ~$1.41 · Anthropic ~$1.03 · Perplexity ~$0.30 · Gemini ~$0.10 (total ≈ $2.84 of $8.00; all engines still under their $2 caps, mostly from the live Asana run).

### Learnings
1. **Citation extraction depends on the model actually searching.** Trivial/evergreen prompts
   are answered from parametric knowledge with 0 citations. The prompt set (Task R1) must use
   **commercial / current-info** phrasing to reliably trigger retrieval — this is itself a
   measurement-design finding worth writing up.
2. **Gemini-2.5-flash is a thinking model** and can return empty text on trivial prompts. For
   grounding data, use substantive prompts; the parser handles empty correctly.
3. **Perplexity key is currently invalid (401).** Blocks the Perplexity engine until replaced.
4. The parsers are validated against real API payload shapes (offline fixtures) **and** on live
   Anthropic data — the atomic core of the platform works.

## 6. Open items / what I need
- ~~Perplexity API key returns 401~~ — **resolved 2026-08-13**: replaced key verified (14 citations). All 4 engines live.
- ~~R1 (onboarding) + R2 (metrics)~~ — **done 2026-08-13** (offline, 36 new tests). Live
  sentiment-judge κ-validation still wants a small hand-labeled gold set + a few judged calls.
- ~~R3 (keyword→prompt)~~ — **done 2026-08-13** (offline, 14 tests). Milestone 1 (R) complete.
- ~~O3 (cross-engine reconciliation)~~ — **done 2026-08-13** (13 tests + live run; overlap ≈9.6%
  measured, Gemini redirect artifact found).
- ~~Resolve Gemini grounding redirects to real domains~~ — **done** (via `web.title`; now in overlap).
- ~~Multi-repeat live run~~ — **done 2026-08-14** (Asana, 10×5; mention≠citation finding, overlap
  12.7%). SoV still needs *more prompts* (not more repeats) to be non-degenerate.
- Remaining: O2 (causal before/after); A2 dashboard to visualize the JSON reports.
- Buildable now with no keys: app integration (A1) of the passing POCs.

## 7. How to reproduce
```bash
cp .env.example .env          # then add real keys (already done locally)
uv sync
uv run pytest -q              # 64 tests, offline
uv run python pocs/connectors/smoke.py        # frugal live check (spends cents)
uv run python pocs/crawler/demo.py            # safe sandbox crawl
```
