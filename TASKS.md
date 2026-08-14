# TASKS.md — AI_GEO Platform Build Plan

Task graph for building a **measurement-honest GEO platform**, local-only. Derived from
`COMPETITIVE_LANDSCAPE.md` §7 (what's reusable / open lanes / what's buildable) and
`RESEARCH.md` §5 (roadmap).

## Conventions
- **Workflow is POC-first (mandatory):** every capability is built and tested in
  `pocs/<name>/`, validated, then integrated into `app/`. A task is only "Done" when its
  POC has passing tests **and** it's integrated (or explicitly deferred).
- **Status:** ☐ todo · ◐ in progress · ☑ done · ⏸ blocked/deferred.
- **Tests always.** Python → `pytest`, external APIs mocked so the suite runs offline.
- **Never commit PII/secrets.** Keys in `.env`; sensitive data in `secrets/` (both gitignored).
- Task IDs: `F` foundation · `R` reusable patterns (§7.1) · `O` open lanes (§7.2) ·
  `C` crawler (§7.3) · `A` app integration · `X` cross-cutting.

## Dependency overview
```
F1 env  ─┬─► F2 schema ─┬─► F3 connectors ─┬─► R1 onboarding ─► R2 metrics ─┬─► O1 rigor
         │              │                  │                                ├─► O2 causal
         │              │                  └─► R3 keyword→prompt             └─► O3 reconcile
         │              │
         └──────────────┴─► C1 crawler (independent; safe sandbox only)
O1+O2+O3+R2 ─► A1..A4 app integration (dashboard, reporting)
X1 testing / X2 lint / X3 docs run throughout.
```
**Critical path:** F1 → F2 → F3 → R1 → R2 → **O1 (rigor)** = the headline differentiator; do it first among the open lanes.

---

## MILESTONE 0 — Foundation (F)

### F1 ☐ Python project + tooling baseline
- **Why:** every POC needs a reproducible env and a test runner.
- **Prerequisites:** none (uv, Python 3.13 already installed).
- **Subtasks:**
  - F1.1 `pyproject.toml` at repo root (uv-managed); deps: `pytest`, `pydantic`,
    `python-dotenv`, `httpx`, `pandas`, `numpy`, `scipy`, `statsmodels`, `ruff`.
  - F1.2 `uv sync` produces a working `.venv`; `uv run pytest` runs (even with 0 tests).
  - F1.3 `ruff` config (line length, basic rules) + a `pytest.ini`/`[tool.pytest]` section.
  - F1.4 A tiny smoke test so CI-lite is green from day one.
- **Deliverable:** `pyproject.toml`, `uv.lock`, green `pytest`.
- **Done when:** `uv run pytest` passes locally.

### F2 ☐ Fact-store schema (SQLite, append-only)
- **Why:** variance/drift require immutable per-run rows (RESEARCH.md §3.4).
- **Depends on:** F1.
- **Prerequisites:** decide SQLite (chosen) over Postgres for local simplicity.
- **Subtasks:**
  - F2.1 Tables: `prompts`, `runs` (raw_response JSON + answer_text), `citations`,
    `mentions`, `content_scores` (schema per RESEARCH.md §3.4).
  - F2.2 `runs` is **append-only** (one immutable row per engine call); no updates.
  - F2.3 SQLAlchemy models + a migration/init script; `data/` is gitignored.
  - F2.4 Tests: insert/read round-trip; enforce append-only by convention + test.
- **Deliverable:** `pocs/factstore/` with schema + tests.
- **Done when:** round-trip tests pass; DB file lands in gitignored `data/`.

### F3 ☐ Engine connector layer (adapters + normalization)
- **Why:** the atomic core of every GEO product; must be uniform + ToS-clean.
- **Depends on:** F1, F2.
- **Prerequisites:** **API keys in `.env`** (OpenAI, Perplexity, Gemini). *Blocked on user
  providing keys locally — see "What I need from you" in the status note.*
- **Subtasks:**
  - F3.1 Adapter interface: `query(prompt, *, temperature, seed) -> EngineResponse`.
  - F3.2 OpenAI Responses API + `web_search` tool; parse `url_citation` annotations.
  - F3.3 Perplexity Sonar; parse inline citations.
  - F3.4 Gemini + `google_search` grounding; parse `groundingMetadata`.
    **Document it as an AI-Overviews proxy, not the real thing.**
  - F3.5 Citation normalization: canonicalize URLs → registrable domain; dedupe.
  - F3.6 **Offline test mode:** record real responses once → replay fixtures so the suite
    runs with no keys/network (VCR-style JSON fixtures under `tests/fixtures/`).
  - F3.7 Cost guard: cap calls/run; cache raw responses so re-analysis never re-calls.
- **Deliverable:** `pocs/connectors/` with 3 adapters + replay-based tests.
- **Done when:** all 3 adapters return a normalized `EngineResponse`; tests pass offline.

---

## MILESTONE 1 — Reusable patterns (R) — from §7.1 "what's genuinely reusable"

> These are validated, table-stakes patterns. Reuse (don't reinvent) the definitions;
> the differentiation is in Milestone 2, not here.

### R1 ☑ Onboarding pattern: brand → auto-prompts → competitors
> **Done (POC):** `pocs/onboarding/` — 16 tests. Deterministic generator (80/10/10 intent
> split via largest-remainder), branded-skew guard (R1.3), paraphrase variants (R1.5).
> LLM-drafting (R1.2c) is an injectable `Callable` (not exercised offline). App integration pending (A1).
- **Why:** industry-standard UX; skipping it feels primitive (§7.1).
- **Depends on:** F3 (needs an engine to help draft/validate prompts) — but the
  deterministic parts (brand profile, competitor list) can start after F2.
- **Prerequisites:** pick a **safe demo brand + vertical** for testing (no real client PII;
  use a public brand or a fictional one). Decide the prompt-set size (30–50 per RESEARCH §5.2).
- **Subtasks:**
  - R1.1 Brand profile object (name, aliases, domain, category, competitors).
  - R1.2 Prompt auto-generation: 3 techniques from §7.1 — (a) topic/entity-derived,
    (b) keyword→prompt (see R3), (c) LLM-drafted; user-curatable list.
  - R1.3 **Guard against branded-query skew** (§2 criticism): enforce a target ratio of
    *unbranded/category* prompts vs branded; flag if too branded.
  - R1.4 Intent split 80/10/10 informational/commercial/navigational (RESEARCH §5.2).
  - R1.5 Paraphrase variants (2–3 each) — feeds O1's variance-efficiency design.
  - R1.6 Tests: profile validation; skew guard; intent distribution.
- **Deliverable:** `pocs/onboarding/` + tests.
- **Done when:** given a brand, emits a curatable, intent-labeled, skew-checked prompt set.

### R2 ☑ Core metric set (standard definitions)
> **Done (POC):** `pocs/metrics/` — 20 tests. Mention/citation/SoV/position each returned as
> an `Estimate` with a CI (reuses `pocs/rigor`); SoV cluster-bootstrapped over prompts.
> Sentiment = injectable LLM-judge validated with Cohen's κ vs a gold set (R2.5). R2.6
> (Princeton PAWC/Subjective Impression) deferred. See `pocs/metrics/demo.py` for the R1→R2 flow.
- **Why:** users/evaluators expect these exact metrics (§7.1); reuse standard defs.
- **Depends on:** F2, F3.
- **Prerequisites:** brand-mention detection strategy (regex + NER + LLM-as-judge fallback).
- **Subtasks:**
  - R2.1 **Mention rate** — % of runs naming the brand (Bernoulli per run).
  - R2.2 **Citation rate** — % of runs citing/linking the target domain.
  - R2.3 **Share of Voice** — target ÷ total (brand & citation variants), vs competitor set.
  - R2.4 **Position** — citation order / first-mention char offset (Princeton weighting).
  - R2.5 **Sentiment** — LLM-as-judge; **validate against a hand-labeled gold set**, report
    Cohen's κ (RESEARCH §3.3, §4.1).
  - R2.6 Optional research-grade: Position-Adjusted Word Count + Subjective Impression
    (replicate Princeton definitions).
  - R2.7 Tests: each metric on synthetic fixtures with known answers.
- **Deliverable:** `pocs/metrics/` + tests + a gold-set fixture for sentiment κ.
- **Done when:** metrics computed deterministically from fact-store rows; κ reported.

### R3 ☑ Keyword → prompt conversion (bootstrapping trick)
> **Done (POC):** `pocs/keyword_to_prompt/` — 14 tests. Intent inferred from whole-token
> modifiers (commercial/navigational/informational), keyword wrapped in per-intent question
> frames, merged + de-duplicated into an R1 set on a normalized key. Deterministic, no keys.
- **Why:** cheap way to seed prompts from existing SEO keyword data (§7.1, Otterly/Semrush).
- **Depends on:** R1.
- **Prerequisites:** a sample keyword list (public/synthetic — no PII).
- **Subtasks:** R3.1 map keyword → natural-language prompt templates; R3.2 dedupe/merge
  into R1's set; R3.3 tests.
- **Deliverable:** `pocs/keyword_to_prompt/` + tests.
- **Done when:** a keyword list yields deduped, intent-labeled prompts.

> **Note (not building):** server-log AI-bot analytics (Profound/Scrunch) is out of scope —
> requires the user's own production CDN/server logs. Documented in §7.1 as reusable-to-know,
> not reusable-to-build here.

---

## MILESTONE 2 — Open lanes (O) — from §7.2, the differentiators

### O1 ☐ Statistical rigor / uncertainty reporting  ⭐ HEADLINE FEATURE
- **Why:** **zero of ~28 competitors report confidence** (§7.2 #1). Cheapest to build,
  literally uncontested, corroborated by Digiday + academic 5–7pp CIs. This is the thesis.
- **Depends on:** R2 (needs metric samples). Can prototype on synthetic data before F3 keys.
- **Prerequisites:** none external — **pure computation, no keys, no network, no IP risk.**
  → **Best first POC to build immediately.**
- **Subtasks:**
  - O1.1 **Wilson score interval** for binary metrics (mention/citation rate) — correct for
    small n (RESEARCH §4.4).
  - O1.2 **Cluster/bootstrap CIs** for Share of Voice (cluster by prompt).
  - O1.3 **Run each prompt N times**; report mean ± SD + CI, never single-run scores.
  - O1.4 **Variance-components decomposition** (Zatuchin/generalizability theory): partition
    variance into within-prompt resampling / paraphrase / model / (locale). Output a
    **budget recommendation**: prioritize paraphrase+model breadth over repeats.
  - O1.5 **Significance test:** "are brand A and brand B distinguishable?" — report when NOT.
  - O1.6 **Drift tracking:** day-to-day citation-set change (replicate the 40–60% finding).
  - O1.7 Tests: Wilson bounds vs known values; bootstrap coverage on simulated data;
    variance decomposition recovers injected components; significance test edge cases.
- **Deliverable:** `pocs/rigor/` + thorough tests (this module is the project's spine).
- **Done when:** given a sample of runs, emits CIs, variance breakdown, budget advice,
  and pairwise significance verdicts — all tested on synthetic data.

### O2 ☐ Causal attribution (controlled before/after)
- **Why:** no tool proves an edit *caused* a visibility change (§7.2 #2). Princeton method,
  scaled down.
- **Depends on:** F3, R2, O1 (CIs to judge significance), C1 (to fetch/edit page content).
- **Prerequisites:** a page you control or a synthetic content variant; a held-out prompt set.
- **Subtasks:**
  - O2.1 Experiment design: content variant A/B, matched prompts, matched time windows.
  - O2.2 **Holdout prompts** (unedited-topic controls) to net out background drift.
  - O2.3 Apply a *proven* lever (Quotation / Statistics / Cite-Sources per RESEARCH §2.2).
  - O2.4 Pre/post measurement with O1's CIs; report **causal uplift with uncertainty**,
    not a raw delta.
  - O2.5 Tests: simulate a known effect + known drift → estimator recovers the effect,
    holdout removes the drift.
- **Deliverable:** `pocs/causal/` + tests.
- **Done when:** on simulated data it separates true lift from volatility within CI.

### O3 ☑ Cross-engine reconciliation (transparent methodology)
> **Done (POC + live):** `pocs/reconcile/` — 13 tests. Pairwise/mean cited-domain Jaccard (O3.1),
> per-engine SoV under one documented normalization reusing R2/O1 CIs (O3.2), source-ecosystem
> divergence explainer (O3.3), auto-generated machine-readable methodology card (O3.4). Live run
> (`reconcile_live.py`, $0.23): found **Gemini grounding URLs are redirect wrappers**, fixed by
> reading the domain from `web.title` (`connectors._gemini_domain`, +2 tests). Re-derived from
> cache (`recompute_from_cache.py`, $0): **all-4-engine overlap ≈10.6%**, corroborating ~11%.
> Follow-up remaining: a multi-repeat run for meaningful (non-degenerate) SoV.
- **Why:** every vendor's SoV means something different; ~11% domain overlap ChatGPT↔Perplexity
  (§7.2 #4). Normalize + explain divergence with a disclosed method.
- **Depends on:** F3, R2.
- **Prerequisites:** normalized citations from ≥2 engines (F3.5).
- **Subtasks:**
  - O3.1 Cross-engine overlap metric (Jaccard on cited domains); replicate "~11% overlap".
  - O3.2 Per-engine SoV with a **single, documented** normalization (published in-repo).
  - O3.3 Divergence explainer: which engine favors which source ecosystem (Reddit/Wikipedia/YouTube).
  - O3.4 A "methodology card" auto-generated per report (sampling, engine access, dates).
  - O3.5 Tests: overlap math on fixtures; normalization is deterministic & documented.
- **Deliverable:** `pocs/reconcile/` + tests.
- **Done when:** produces a cross-engine comparison + machine-readable methodology card.

---

## MILESTONE 3 — Crawler (C) — from §7.3 "try it locally, safely"

### C1 ☐ Whole-site crawler + AI-readability audit (Lumar/Scrunch-style, small scale)
- **Why:** §7.3 — attempt site-side crawling/rendering/technical audit locally to learn the
  shape of the problem. Explicitly a *learning* task, not a production crawler.
- **Depends on:** F1 (independent of the engine work; can run in parallel).
- **⚠️ SAFETY PREREQUISITES (do first, non-negotiable):**
  - Use a **scrape-safe sandbox target only** — default `https://books.toscrape.com`
    (a site built for scraping practice; also `quotes.toscrape.com`). These raise **zero**
    blocking/ToS concerns.
  - **Respect `robots.txt`** (parse + obey before every fetch).
  - **Rate-limit**: ≥1.5s delay, cap `CRAWLER_MAX_PAGES` (default 25), single concurrency.
  - Custom, honest **user-agent**; no header spoofing.
  - **Never** crawl Google AI Overviews / consumer ChatGPT / a real client site here.
  - All knobs come from `.env` (see `.env.example` CRAWLER_* vars).
- **Subtasks:**
  - C1.1 robots.txt fetch + parse + obey (`urllib.robotparser`).
  - C1.2 Polite fetcher (httpx) with delay, page cap, retry/backoff, timeout.
  - C1.3 **Static vs rendered** comparison: raw HTML vs Playwright-rendered DOM — quantify
    how much content is JS-buried (a real Scrunch-style signal).
  - C1.4 AI-readability audit per page: heading structure, main-content extractability,
    schema/JSON-LD presence, word/statistic density, title/meta quality.
  - C1.5 **AI-bot access check:** simulate GPTBot/ClaudeBot/PerplexityBot **user-agents**
    against the sandbox and report allow/deny (note the Otterly caveat: UA response only,
    not a full robots.txt policy audit — do BOTH: UA test + robots.txt parse).
  - C1.6 Emit a per-site audit report (JSON) feeding `content_scores` (F2).
  - C1.7 Tests: robots parsing (allow/deny fixtures); rate-limiter timing; audit scoring on
    saved sandbox HTML fixtures (offline — no live crawl in CI).
- **Deliverable:** `pocs/crawler/` + tests + one saved sandbox audit report.
- **Done when:** crawls the sandbox within limits, produces an audit, tests pass offline,
  and it demonstrably never exceeds the safety caps.

---

## MILESTONE 4 — App integration (A)

### A1 ☑ Integrate validated POCs into `app/`
> **Done:** `app/` — 16 tests. `geo run` CLI wires R1→(synthetic/live F3)→F2→R2/O1→O3 into one
> command. Offline dry-run by default ($0, deterministic, labeled synthetic); `--live` calls real
> engines under the $2 guard and persists to `data/geo.sqlite`. Emits human tables + a JSON report
> under `data/reports/`. Reuses POC modules unchanged via `app/_paths.py`. A scheduler for repeated
> runs is deferred (not needed for the single-shot CLI yet).
- **Depends on:** the relevant POCs passing (F3, R1–R3, O1–O3, C1).
- **Subtasks:** package modules under `app/` (connectors, metrics, rigor, reconcile, crawler);
  a scheduler for repeated runs; one CLI entrypoint (`geo run --brand ... --engines ...`).
- **Done when:** end-to-end: brand in → prompts → multi-engine runs → fact store → metrics
  **with CIs** → cross-engine report + methodology card.

### A2 ☑ Reporting / dashboard (local)
> **Done:** `pocs/dashboard/` (15 tests) + `geo report` subcommand (4 tests). GeoReport JSON →
> one self-contained HTML file (inline CSS/SVG, no server/JS/network). Honesty-first: CI bands on
> every rate, synthetic-run banner, mention-vs-citation gap callout, cross-engine
> two-proportion-test distinguishability verdicts, verbatim methodology card. Real artifact at
> `data/reports/asana_2026-08-14.html`. Drift chart deferred (needs two dated snapshots).
- **Depends on:** A1. Tech TBD (start with static HTML/matplotlib; optional Next/React later).
- **Subtasks:** per-brand citation frequency **with Wilson CIs**; SoV by engine; cross-engine
  overlap chart; drift chart; "not statistically distinguishable" callouts.
- **Done when:** a local report renders the honesty-first visuals (CIs everywhere).

### A3 ☐ Attribution notes (GA4 regex channel group) — documentation-only for now
- **Depends on:** A1. No live GA4 (local-only); document the method (RESEARCH §4.3).

### A4 ☐ End-to-end demo run + write-up
- **Depends on:** A1–A2. Produce the "single-run scores aren't reproducible; here are the CIs"
  finding on real data (RESEARCH §5.2).

---

## CROSS-CUTTING (X)

- **X1 ☐ Testing discipline:** pytest everywhere; external APIs mocked/replayed; deterministic
  seeds; coverage on the stats modules especially (O1/O2 are correctness-critical).
- **X2 ☐ Lint/format:** ruff; keep functions small and typed.
- **X3 ☐ Docs:** update `README.md` per milestone; each POC has its own `README.md` stating
  purpose, how to run, and how it integrates.
- **X4 ☐ Commit hygiene:** small commits; `git status` sanity-check before each; never stage
  `.env`/`secrets/`; push to `origin/main`.

---

## Suggested execution order
1. **F1 → O1** (build the rigor spine on synthetic data first — no keys needed). ⭐
2. **C1** (crawler on sandbox — safe, parallelizable, no keys needed).
3. **F2 → F3** (needs API keys — *blocked on user*).
4. **R1 → R2 → R3** (reusable patterns, once connectors exist).
5. **O3 → O2** (reconciliation, then causal).
6. **A1 → A2 → A4** (integrate + demo).

> **Blocked-on-user:** F3 and everything downstream that hits live engines need API keys in
> `.env` (OpenAI, Perplexity, Gemini). Until then, O1 and C1 proceed fully on synthetic /
> sandbox data with no keys.
