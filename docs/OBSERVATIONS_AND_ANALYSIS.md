# Observations & Analysis — AI_GEO Platform

A synthesis document: what we **observed**, what it **means**, the **metrics** behind the
claims, and clearly-labeled **opinions**. This is the analytical companion to the other docs:

| Doc | Role |
|---|---|
| `RESEARCH.md` | The thesis + evidence tiers (why measurement-honesty is the wedge). |
| `COMPETITIVE_LANDSCAPE.md` | Teardown of ~28 tools; what's reusable / buildable. |
| `ANALYSIS_REPORT.md` | Running **log** (dated decisions, costs, live findings). |
| **this file** | Standing **analysis** — observations, interpretation, opinions. |
| `TASKS.md` | The build plan and status. |

> **Evidence discipline.** Every number below is tagged with the script that produces it, so
> it can be re-derived (`§Reproduction`). Numbers with no script behind them are not stated as
> facts — they are marked **[judgment]** or **[from external research, not our measurement]**.
> This is the whole point of the project, so the documentation holds itself to the same bar.

_Last updated: 2026-08-14._

---

## 1. Executive summary

- The platform's **atomic core works end-to-end**: a brand becomes an intent-labeled prompt
  set (R1), runs through four live answer engines with citation extraction under a hard budget
  cap (F3), and turns into metrics **with confidence intervals** (R2) reusing a tested
  statistics module (O1). **100 automated tests pass, ruff-clean**, and the whole suite runs
  offline (no keys, no spend).
- The **honest-headline claim is demonstrated, not just asserted**: on a controlled synthetic
  run with a *known* 35% citation propensity, R2 recovered `0.375 [0.337, 0.414]` — the true
  value sits inside the 95% interval, and a single-run point score would have hidden that
  uncertainty entirely. This is the thing no competitor ships.
- **We have now measured cross-engine disagreement ourselves.** A live O3 run (4 prompts × 4
  engines, $0.23) put mean cited-domain overlap at **≈10.6%** across all four engines —
  corroborating the ~11% we had only borrowed. Getting there surfaced (and we fixed) a real
  artifact: Gemini's grounding URLs are redirect wrappers whose real domain lives in `web.title`
  (O-7); before the fix Gemini looked like it cited a single host.
- **Total live spend to date ≈ $0.30** (of $8.00 across providers). We still have **not** run a
  full multi-*repeat* measurement on a real brand (the O3 run was 1 repeat, so per-engine SoV is
  uninformative at that n) — brand-level competitive rankings remain explicitly deferred.

---

## 2. Metrics (measured — each has a script)

### 2.1 Build / test metrics
Source: `uv run pytest pocs/<mod> -o addopts=""` per module (§Reproduction R-1).

| Module | Task | Tests | Needs keys | Runtime |
|---|---|---:|---|---|
| `pocs/rigor` | O1 statistics | 22 | no | ~0.48s |
| `pocs/crawler` | C1 safe crawler | 12 | no | ~0.03s |
| `pocs/factstore` | F2 SQLite store | 7 | no | ~0.01s |
| `pocs/connectors` | F3 budget + 4 adapters | 23 | no (offline) | ~0.02s |
| `pocs/onboarding` | R1 prompt-set | 16 | no | ~0.01s |
| `pocs/metrics` | R2 metrics+CI | 20 | no | ~0.48s |
| `pocs/keyword_to_prompt` | R3 keyword→prompt | 14 | no | ~0.02s |
| `pocs/reconcile` | O3 cross-engine reconcile | 13 | no | ~0.7s |
| `app` | A1 pipeline + `geo run` CLI | 16 | no | ~5s |
| **Total** | | **145** | | ~7s |

(Per-module counts drift as tests are added — `pocs/connectors` is 25 after the O-7 Gemini
parser tests; the total is authoritative.)

100 % of the suite runs **offline** — external APIs are mocked/replayed and the crawler uses
saved fixtures — so tests never spend budget or touch the network.

### 2.2 Live-engine metrics
Source: `pocs/connectors/smoke.py` + `data/cost_ledger.json` (§Reproduction R-2).

| Provider | Model | Live citations parsed | Spend to date | Cap |
|---|---|---:|---:|---:|
| OpenAI | `gpt-4o-mini` | ✓ (0 on evergreen prompts) | $0.0251 | $2.00 |
| Perplexity | `sonar` | 14 | $0.0055 | $2.00 |
| Gemini | `gemini-2.5-flash` | ✓ (0 on trivial prompts) | $0.0001 | $2.00 |
| Anthropic | `claude-haiku-4-5` | 6 | $0.0344 | $2.00 |
| **Total** | | | **≈ $0.065** | $8.00 |

### 2.3 Honest-headline demo (controlled recovery)
Source: `pocs/metrics/demo.py`, seed=7, 30 prompts × 20 repeats = 600 synthetic runs, injected
brand-citation propensity = **0.35** (§Reproduction R-3).

| Metric | Point | 95% CI | Truth inside CI? |
|---|---:|---|:--:|
| Mention rate | 0.457 | [0.417, 0.497] | — (injected 0.45) ✓ |
| Citation rate | 0.375 | [0.337, 0.414] | injected 0.35 ✓ |
| Share of Voice | 0.394 | [0.368, 0.421] | — |
| Position (mean rank) | 1.30 | — | — |

Skew guard on the same set: **4/30 branded (13% ≤ 30% ceiling) → OK**; intent split **24/3/3 =
80/10/10** exactly.

### 2.4 Live cross-engine reconciliation (O3) — our own overlap number
Source: `pocs/reconcile/reconcile_live.py`, 4 commercial/current-info prompts × 4 engines,
1 repeat, 2026-08-13 (§Reproduction R-4). **Run cost: $0.233** (cumulative provider spend now
openai $0.131 · anthropic $0.127 · perplexity $0.028 · gemini $0.012 — all ≪ $2 cap).

| Pair | Cited-domain Jaccard |
|---|---:|
| anthropic ∩ perplexity | 0.167 |
| anthropic ∩ gemini | 0.161 |
| gemini ∩ perplexity | 0.147 |
| anthropic ∩ openai | 0.061 |
| openai ∩ perplexity | 0.060 |
| gemini ∩ openai | 0.037 |
| **Mean, all 4 engines** | **0.106** |

**Our measured cross-engine citation overlap ≈ 10.6%** across all four engines — independently
corroborating the literature's ~11% (which we had only borrowed). Note: the first pass measured
**9.6%** across only 3 engines because Gemini was a redirect artifact (O-7); after the fix,
re-parsing the *same cached payloads* (R-5, zero spend) folds Gemini back in and lands at 10.6%.
Unique domains per engine: perplexity 57 · gemini 52 · openai 32 · anthropic 20. SoV at this tiny
sample is uninformative (n=0–1 prompts per engine hit the brand universe; CIs are degenerate/[0,1])
— correctly flagged rather than reported as fact.

---

## 3. Observations

**O-1 — A single run is not reproducible; the interval is the honest unit.**
In the controlled demo the point estimate lands near but not on the truth (0.375 vs 0.35); only
the **interval** reliably covers it. Empirically, then, a lone "visibility score" is a draw from
a distribution, and reporting it without its width overstates precision. *Evidence: R-3.*

**O-2 — Citation extraction depends on the model actually choosing to search.**
Trivial/evergreen prompts ("top 2 project management tools, one sentence") were answered from
parametric memory with **0 citations** on OpenAI, Gemini, and Anthropic. Forcing a
current-information prompt produced 6 (Anthropic) and 14 (Perplexity) real citations. *This is a
measurement-design finding: the prompt set is part of the instrument.* *Evidence: R-2.*

**O-3 — Locale silently changes the cited source set.**
The verified Perplexity run returned **Spanish-language sources** for an English query, i.e. the
retrieved source ecosystem is locale-sensitive. An un-pinned locale is an uncontrolled variable.
*Evidence: `ANALYSIS_REPORT.md` 2026-08-13 entry; R-2.*

**O-4 — "Thinking" models can legitimately return empty grounding.**
`gemini-2.5-flash` returned no text/chunks on a trivial prompt. The parser correctly yields an
empty result (empty-in → empty-out is tested), so this is a prompt-design caveat, not a bug.

**O-5 — Branded-query skew is real and now measurable.**
Left unguarded, an "onboarding" prompt set drifts toward "{brand} reviews / {brand} vs X"
queries that put the brand *in the question* — guaranteeing it appears in the answer. The R1
guard quantifies this (branded ratio vs a 30% ceiling) and flags it. *Evidence: R-1 tests
`test_all_branded_set_fails_skew_check`, `test_default_set_passes_skew_check`.*

**O-6 — Cross-engine agreement is low — now measured by us.** **[our measurement, 2026-08-13]**
On 4 commercial prompts × 4 engines, the mean pairwise cited-domain Jaccard was **0.106 (≈10.6%)**
across all four engines (after the O-7 Gemini fix; 0.096 across the three engines that were
comparable before it) — independently corroborating the ~11% figure we had only borrowed. Even the
*most*-overlapping pair (Anthropic↔Perplexity) shared just 16.7% of domains. So "Share of Voice"
genuinely is not the same object across engines; comparing raw vendor SoV numbers is comparing
different webs. *Evidence: R-4, R-5.*

**O-7 — Gemini grounding hides the real source domain behind a redirect — found *and fixed*.**
**[our measurement + fix]** Every Gemini grounding URI is
`vertexaisearch.cloud.google.com/grounding-api-redirect/…`, so all 85 Gemini citations first
collapsed to **1 unique "domain"** with **0 overlap** everywhere — a **measurement artifact**, not
low agreement. Fix (zero-network): the real publisher domain is carried in `web.title`, so the
parser now reads the domain from `title` when the uri is a redirect wrapper
(`connectors._gemini_domain`). Re-parsing the *same cached payloads* then yields **52 real Gemini
domains** and restores its overlap with the other engines (gemini↔perplexity 0.147, gemini↔anthropic
0.161). A tool that silently kept the wrapper would have reported a fake "Gemini cites nothing you
do." *Evidence: R-4 + R-5; cached payloads under `data/cache/gemini/`.*

---

## 4. Analysis (what the observations mean)

**A-1 — Why intervals beat scores (math + market gap).**
Each "was brand X cited?" is a Bernoulli trial; N runs give a binomial proportion. We use the
**Wilson score interval** rather than the normal approximation because it stays valid at small N
and near 0/1 — exactly the regime GEO lives in (few dozen runs, rates near the extremes). The
market gap is stark: **0 of ~28 surveyed tools report any interval** (COMPETITIVE_LANDSCAPE.md),
despite academic/industry reports of 5–7pp CIs and 40–60% monthly citation drift. So the cheapest
correct statistic is also the most differentiated. *Code: `pocs/rigor/rigor.py:wilson_interval`.*

**A-2 — Where the noise comes from, and the budget implication.**
GEO variance decomposes across factors — repeat, paraphrase, model, locale. The rigor module's
one-way variance-components estimator (`one_way_variance_components`) plus
`variance_budget_recommendation` operationalize the generalizability-theory insight: **breadth
(more paraphrases/models) reduces error variance more per dollar than repeats.** Practically,
under a fixed budget you should spend calls on *diversity of phrasing/engine*, not on hammering
one prompt — and O1 can output that recommendation from the data.

**A-3 — Share of Voice must be clustered, not pooled.**
All repeats of one prompt share a retrieval context, so their citations are **correlated**.
Pooling them as if independent understates the CI. We therefore bootstrap **whole prompts**
(`share_of_voice_ci` → `cluster_bootstrap_ci`). The R2 SoV CI (±~2.6pp at n=30 prompts in the
demo) reflects between-prompt variability, which is the honest source of uncertainty for SoV.

**A-4 — Sentiment is untrustworthy without agreement testing.**
An LLM-as-judge sentiment label is only as good as its agreement with humans. R2 therefore
returns **Cohen's κ** against a hand-labeled gold set and a `trustworthy` flag (κ ≥ 0.6), and
keeps the judge itself an injectable `Callable`. We do **not** report sentiment as a number until
κ clears the bar — the same evidence discipline applied to our own metric.

**A-5 — The skew guard is a measurement-validity defense, not a UX nicety.**
O-5 means branded-heavy sets inflate every downstream metric. Enforcing an unbranded/category
majority (the 80/10/10 intent target + 30% branded ceiling) is what makes mention/citation rates
*mean* "discoverability" rather than "we already know the name." It's the input-side half of the
honesty story; the CI is the output-side half.

---

## 5. Opinions & judgments  *(explicitly labeled — not measured facts)*

- **[judgment] The defensible wedge is honesty, not coverage.** We will never out-crawl Semrush
  or out-integrate Profound. The uncontested position is "the tool that tells you when the number
  is noise" — CIs, distinguishability tests, disclosed methodology. Every build choice so far
  serves that, and it maps cleanly onto the course's computational-skepticism thesis.
- **[judgment] The strongest single artifact is the distinguishability test.** `two_proportion_
  test` answering "are brand A and brand B actually different, or within noise?" is the feature a
  skeptical buyer feels immediately, and the one competitors structurally can't add without
  admitting their scores are noisy. Worth foregrounding in the demo/write-up.
- **[judgment] Biggest current weakness: no live end-to-end run on a real brand.** Everything is
  proven on synthetic/controlled data or single live calls. Until a full 4-engine × N-repeat run
  exists (under budget), competitive numbers stay out of scope — and we should keep saying so.
- **[judgment] Second weakness: the keyword→prompt and prompt templates are heuristic.** They're
  honest and deterministic, but not yet validated against real search-intent data; treat R1/R3
  output as a *curatable draft*, which is how the UX is framed.
- **[opinion] Cross-engine reconciliation (O3) is the best next spend of live budget** — it
  produces a genuinely novel, defensible artifact (a disclosed cross-engine methodology card +
  overlap number) for a few cents, and lets us replace the borrowed ~11% figure with our own.

---

## 6. Honesty ledger — what is NOT yet substantiated

| Claim | Status |
|---|---|
| Metrics carry correct CIs | **Substantiated** (R2 tests + rigor tests; demo recovery). |
| All 4 engines parse real citations | **Substantiated** (live: Perplexity 14, Anthropic 6). |
| Budget can never be exceeded | **Substantiated** (guard test: network untouched once over cap). |
| Cross-engine overlap ≈ 10.6% (all 4 engines) | **Substantiated (ours)** — O3 live run + Gemini fix (R-4, R-5); corroborates the borrowed ~11%. |
| Gemini domains resolved via web.title (redirect not followed) | **Substantiated (ours)** — O-7 fix; Gemini now folded into overlap. Domains are as Gemini reports them, not verified against the live redirect target. |
| 40–60% monthly citation drift | **Not ours** — external; `citation_drift` can measure it once we have two dated snapshots. |
| Real-brand competitive ranking | **Not attempted** — needs a full live run; out of scope until then. |
| Sentiment numbers | **Gated** — reported only after κ ≥ 0.6 on a gold set (not yet collected). |

---

## 7. Reproduction

```bash
# R-1  per-module + total test counts (offline, no keys)
for d in rigor crawler factstore connectors onboarding metrics; do
  uv run pytest pocs/$d -o addopts="" | tail -1; done
uv run pytest            # 100 passed

# R-2  live engine check + spend ledger (spends cents, budget-guarded)
uv run python pocs/connectors/smoke.py
cat data/cost_ledger.json

# R-3  honest-headline demo (offline, seeded, reproducible)
uv run python pocs/metrics/demo.py

# R-4  live cross-engine reconciliation (spends ~$0.23, budget-guarded)
uv run python pocs/reconcile/reconcile_live.py

# R-5  re-derive overlap from CACHED payloads with the Gemini fix (offline, $0)
uv run python pocs/reconcile/recompute_from_cache.py

uv run ruff check .      # lint clean
```
