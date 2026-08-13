# POC: `rigor` — statistical rigor for GEO measurement (Task O1)

**The project's headline differentiator.** Every commercial GEO tool ships single-run point
estimates despite 40–60% monthly citation drift. This module reports **uncertainty** instead.

## Why it matters
No competitor (of ~28 surveyed in `../../COMPETITIVE_LANDSCAPE.md`) reports confidence
intervals, sample sizes, or "these two brands aren't statistically distinguishable." This is
the cheapest, most defensible, literally-uncontested feature — and it needs **no API keys and
no network**, so it was built first.

## What's in it (`rigor.py`)
- `wilson_interval` / `proportion_estimate` — Wilson score CIs for binary metrics
  (mention rate, citation rate); correct for small n and proportions near 0/1.
- `share_of_voice_ci` / `cluster_bootstrap_ci` — cluster bootstrap (resample the **prompt**,
  not the row) for Share of Voice CIs.
- `two_proportion_test` — is brand A vs brand B distinguishable, or is the gap noise?
- `one_way_variance_components` + `variance_budget_recommendation` — decompose noise into
  sources and advise spending API calls on paraphrase/model **breadth** over repeats
  (Zatuchin 2026).
- `citation_drift` — month-over-month churn of the cited-source set (Jaccard).

## Run
```bash
uv run pytest pocs/rigor/ -v      # 22 tests, fully offline
uv run ruff check pocs/rigor/
```

## Demo
```
Brand cited in 3/20 runs: 0.150 [0.052, 0.360] (n=20, 95% CI)
Rival cited in 5/20 runs : 0.250 [0.112, 0.469] (n=20, 95% CI)
Distinguishable? False (p=0.43) -> cannot claim rival wins
```
The point estimates differ (15% vs 25%) but overlap within noise — the honest verdict every
competitor hides.

## Integration
Feeds `app/`: R2 metrics wrap their outputs in these `Estimate`s; A2 dashboard renders CIs
on every bar; O2 (causal) uses `two_proportion_test` to judge uplift significance.

## Notes / limits
- `one_way_variance_components` is a simplified one-way random-effects estimator (method of
  moments, negative components clamped to 0). A full crossed G-theory model is future work.
- Bootstrap CIs are seeded for determinism; default `n_boot=5000` (lower in tests for speed).
