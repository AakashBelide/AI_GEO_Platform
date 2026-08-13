# POC: `metrics` — core metric set **with uncertainty** (Task R2)

The metrics every GEO tool reports — but computed the honest way, as **estimates with
confidence intervals** instead of single-run point scores. Each run is one Bernoulli/observed
sample, so N runs of a prompt give a Wilson interval, not a lone percentage. Reuses the
`rigor` POC (O1) for all the statistics — no duplicated Wilson/bootstrap code.

| Metric | Fn | How |
|---|---|---|
| Mention rate (R2.1) | `mention_estimate` | word-boundary alias regex per run → Wilson CI |
| Citation rate (R2.2) | `citation_estimate` | target-domain (incl. subdomain) match per run → Wilson CI |
| Share of Voice (R2.3) | `share_of_voice` | target ÷ (target+competitor) citations, **cluster-bootstrap CI over prompts** |
| Position (R2.4) | `position_summary` | mean 1-based citation rank + first-mention char offset |
| Sentiment (R2.5) | `judge_sentiments` + `cohen_kappa` | LLM-as-judge (injectable), **validated vs a gold set** via Cohen's κ |

## The honesty details
- **Subdomain-aware, substring-safe matching.** `blog.acme.com` matches `acme.com`;
  `fakeacme.com` does not. Mentions use `(?<!\w)…(?!\w)` boundaries so `Acme` ≠ `Acmentor`.
- **SoV is clustered by prompt** (repeats of a prompt share retrieval context), so the CI
  reflects correlated GEO non-determinism rather than pretending runs are independent.
- **Sentiment is never trusted blind.** `sentiment_kappa_report` returns Cohen's κ against a
  hand-labeled gold set and a `trustworthy` flag (κ ≥ 0.6); the judge itself is an injectable
  `Callable` (offline tests use a deterministic stub — no network).

## Design for testing
Pure functions over lightweight `RunRecord`s — decoupled from the fact store and live
connectors — so the suite runs offline on synthetic runs with known answers.

## Run
```bash
uv run pytest pocs/metrics/ -q     # 20 tests, offline
uv run python pocs/metrics/demo.py # R1 → synthetic runs → R2 metrics with CIs (no network)
```

## Integrates with
Consumes `RunRecord`s built from `pocs/factstore` rows (from `pocs/connectors` output) and the
`BrandProfile` from `pocs/onboarding`; emits `BrandMetrics` (each field an `Estimate` with a
CI) that the reporting layer (A2) renders honesty-first.
