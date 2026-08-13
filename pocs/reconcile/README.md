# POC: `reconcile` — cross-engine reconciliation + methodology card (Task O3)

Every GEO vendor's "Share of Voice" means something different because each answer engine cites a
different slice of the web (reported ChatGPT↔Perplexity domain overlap ≈ 11%). This POC does the
honest version: **normalize citations the same disclosed way across engines, quantify how much
they disagree, explain where the divergence comes from, and auto-emit a methodology card.**

| Output | Fn | What |
|---|---|---|
| Citation overlap (O3.1) | `overlap_report` | pairwise Jaccard on cited-domain sets + mean-overlap headline |
| Per-engine SoV (O3.2) | `per_engine_share_of_voice` | target ÷ (target+competitor) citations, **one** normalization, each with a bootstrap CI (reuses `pocs/metrics`→`pocs/rigor`) |
| Divergence explainer (O3.3) | `ecosystem_profile` + `ecosystem_divergence` | which engine over-indexes which source bucket (Reddit / Wikipedia / YouTube / …) |
| Methodology card (O3.4) | `build_methodology_card` | machine-readable: sampling, per-engine access method, dates, normalization, caveats |

`reconcile(...)` bundles all four into one `ReconciliationReport` (`.to_dict()` → JSON).

## Why it's honest
- **One normalization for every engine** (`DOMAIN_NORMALIZATION`, documented in-code and in the
  card), so a difference between engines is a *real* difference, not a methodology artifact.
- **SoV keeps its CI** — cross-engine numbers are comparable *and* honest about noise; at small
  n the intervals are wide on purpose (the demo shows `[0.00, 1.00]` at n=3).
- The **source-ecosystem mapping is deliberately small and disclosed** (`ECOSYSTEM_RULES`);
  everything unmatched is `other` — transparency over false completeness.

## Design for testing
Pure computation over `RunRecord`s grouped by engine — no keys, no network — so the suite runs
offline. Dates are injected (`generated_utc`) so the methodology card is deterministic.

## Run
```bash
uv run pytest pocs/reconcile/ -q          # 13 tests, offline
uv run python pocs/reconcile/demo.py      # synthetic multi-engine reconciliation (no network)
uv run python pocs/reconcile/reconcile_live.py   # frugal live overlap (spends cents, budget-guarded)
```

## Integrates with
Consumes `RunRecord`s built from `pocs/connectors` output (grouped by engine) — the same records
`pocs/metrics` uses — and produces the cross-engine comparison + methodology card that the
reporting layer (A2) renders. This is the artifact that lets us replace the borrowed ~11%
overlap figure with our own measured number.
