# POC: `causal` — did the edit actually work? (Task O2)

No commercial GEO tool proves an edit *caused* a visibility change — they show a raw
before/after delta and call it "impact". But AI answers drift 40–60% month-to-month on their
own, so a raw delta is mostly background drift. This POC does the honest version:
**difference-in-differences (DiD) with a holdout control**, reporting the causal uplift **with a
confidence interval** instead of a point delta.

```
causal uplift  =  (treated_post − treated_pre)  −  (control_post − control_pre)
                   \_______ raw delta ________/    \____ background drift ____/
```

- **Treated** prompts = the ones whose target pages you edited.
- **Control / holdout** prompts = unedited topics measured over the same window; whatever moved
  them is drift, which we subtract off.
- **CI** = a cluster bootstrap over prompts (same philosophy as `pocs/rigor`) — resample whole
  prompts, recompute DiD, take percentiles. If the interval **includes 0**, the edit is *not*
  shown to have worked, and the report says so rather than quoting the raw delta.

| Fn | What |
|---|---|
| `difference_in_differences(treated, control, …)` | causal uplift + bootstrap CI + `significant` (CI excludes 0), plus the naive delta and the measured background drift for contrast |
| `naive_delta(treated)` | the misleading number competitors report (treated post − pre, no drift control) |
| `simulate_experiment(true_effect, drift, …)` | before/after data with a KNOWN effect + KNOWN drift, for tests/demo |
| `PROVEN_LEVERS` | the content levers an experiment would apply (Quotation / Statistics / Cite-Sources, RESEARCH.md §2.2) |

## The demo (the drift trap)
`uv run python pocs/causal/demo.py` runs two simulated experiments. In both the naive delta is
positive and looks like a win; only the holdout-controlled DiD tells them apart:

| Scenario | naive delta | causal uplift (DiD, 95% CI) | verdict |
|---|---:|---|---|
| Real edit worked (true +0.15, drift +0.10) | **+0.25** | **+0.14 [0.09, 0.18]** | significant ✓ |
| No edit — only drift (true 0, drift +0.12) | **+0.11** | −0.02 [−0.06, +0.03] | **not significant** ✓ |

## Design for testing
Pure computation — no keys, no network. Tests inject a known effect + known drift and assert the
DiD **recovers the effect within its CI**, that the naive delta is **biased by the drift**, that a
real effect is flagged significant, and that a **drift-only** experiment is **not** (the false-win
trap). Deterministic (seeded bootstrap).

## Live workflow (how you'd run it for real)
1. `geo run --brand … --live` **before** editing → the pre-period fact store.
2. Apply a proven lever (`PROVEN_LEVERS`) to the target pages; keep a holdout set of unedited
   topics.
3. `geo run … --live` **after**, over a matched window → the post-period.
4. Build `PrePost` rows (target-citation hits/n per prompt, pre & post) for the treated and
   holdout prompts and call `difference_in_differences`.

*(Live before/after integration into the CLI is future work — the estimator is validated here
offline on simulated data, which is the O2 "done when" bar.)*

## Run
```bash
uv run pytest pocs/causal/ -q       # 10 tests, offline
uv run python pocs/causal/demo.py   # the drift-trap demo (no network)
```

## Integrates with
Consumes the same per-prompt citation outcomes the pipeline already produces (`pocs/metrics` /
`pocs/factstore`), and its CI philosophy matches `pocs/rigor`. It is the last differentiator from
`COMPETITIVE_LANDSCAPE.md` §7.2 — causal proof, which no surveyed competitor offers.
