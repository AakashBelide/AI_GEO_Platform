# ANALYSIS REPORT — AI_GEO Platform

A running, referenceable log of what was built, the decisions made, the models/costs used,
and what was learned. Append new dated entries at the top of §5 as work continues.

_Last updated: 2026-08-13._

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

**Total: 129 tests passing, ruff clean.** Every POC runs its suite fully offline (external APIs
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

**Spend so far (of $2.00 each):** OpenAI ~$0.025 · Gemini ~$0.0001 · Anthropic ~$0.034 · Perplexity ~$0.006.

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
- Follow-ups: a multi-repeat O3 run for meaningful SoV; O2 (causal before/after) still to build.
- Buildable now with no keys: app integration (A1) of the passing POCs.

## 7. How to reproduce
```bash
cp .env.example .env          # then add real keys (already done locally)
uv sync
uv run pytest -q              # 64 tests, offline
uv run python pocs/connectors/smoke.py        # frugal live check (spends cents)
uv run python pocs/crawler/demo.py            # safe sandbox crawl
```
