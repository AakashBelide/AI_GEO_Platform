# insights — interpretation layer (A2 reporting)

Turns a measured GEO report into **findings** (what the numbers say) and
**recommendations** (GEO actions to test). Pure, deterministic, offline — no LLM, no
network, no fabrication. Every statement is a restatement of, or a pointer to, a number
already in the report.

## Why it exists
The measurement pipeline produces honest numbers (rates with CIs, cross-engine overlap,
top cited domains). Those numbers still need a plain-English reading. Commercial GEO tools
jump straight to an opaque "visibility score" plus generic advice; this module instead
writes findings/recommendations that a reader can trace back to a specific engine, domain,
or count — and it hedges every recommendation as a hypothesis, because causal proof needs a
controlled before/after (Task O2), which this run does not perform.

## API
```python
from insights import top_domains, generate_findings, generate_recommendations

top_domains(citations_by_engine, k=10)   # engine -> [(domain, count), ...]
generate_findings(report)                # list[str] — factual, restated numbers
generate_recommendations(report)         # list[str] — hedged, evidence-tied GEO actions
```

`report` is the dict emitted by `app/pipeline.GeoReport.to_dict()` (or a JSON report
enriched from the fact store). The functions read `per_engine_metrics`,
`reconciliation`, `top_domains`, `brand`, `mode`, and (optionally) `target_domain`.

## What it surfaces
Findings cover, when the data supports it: the **mention-vs-citation gap** per engine
("OpenAI mentions Asana in 82% of answers but cites asana.com in 0%"); which engines do vs
don't cite the target domain; the cross-engine overlap number and the portability caveat it
implies; the actually-most-cited domains for the category; any flagged ecosystem divergence;
any engine pair whose citation rates are **not statistically distinguishable** (reuses
`pocs/rigor.two_proportion_test`); and a data-sufficiency caveat when Share-of-Voice
intervals are degenerate or very wide.

Recommendations cover: pursuing presence on the **named** third-party review/aggregator
domains that non-citing engines lean on (framed as PR/listings, not on-site SEO); keeping
the pages that citing engines already link fresh; community presence where an engine
over-indexes Reddit (verify, don't assume); and enlarging the prompt set before ranking
brands when SoV is under-powered.

## Honesty guarantees
- Synthetic dry-run reports are prefixed `ILLUSTRATIVE ONLY`.
- Recommendations always close with the O2 causal hedge.
- Deterministic: identical report in → identical lists out (see `test_insights.py`).

## Tests
`uv run pytest pocs/insights` — offline, fixture-driven.
