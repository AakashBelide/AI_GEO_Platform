# POC: `onboarding` — brand → auto-prompts → competitors (Task R1)

Turns a `BrandProfile` (name, aliases, domain, category, competitors, use-cases) into a
tracked **prompt set**. The industry-standard onboarding UX (Otterly/Semrush/Profound)
plus the two guards competitors skip:

- **Branded-query skew guard (R1.3).** A set full of "{brand} reviews" queries inflates
  visibility — the brand is already in the question. `skew_check` enforces a ceiling on the
  branded ratio (default 30%) and flags a set that exceeds it.
- **Intent distribution (R1.4).** Every prompt is labeled informational / commercial /
  navigational, targeting an **80/10/10** discovery mix (RESEARCH.md §5.2) via
  largest-remainder apportionment (sums exactly to `n_total` for any size).

Also: **paraphrase variants (R1.5)** — deterministic surface rephrasings of one prompt
(same intent/branded/category), which feed the rigor POC's variance-components design (O1.4).

## Design for testing
Generation is **pure and deterministic** (template pools, round-robin over competitors/
use-cases) so the suite runs fully offline. The optional LLM-drafting step (R1.2c) is an
injectable `Callable` and is never invoked by the tests.

## Run
```bash
uv run pytest pocs/onboarding/ -q     # 16 tests, offline
```

## Integrates with
Emits `Prompt` objects whose `.text` is sent to `pocs/connectors` (one `runs` row per engine
call in `pocs/factstore`), and whose `branded`/`intent` labels + `BrandProfile.all_names()`
feed `pocs/metrics` (R2) for mention/citation/SoV. See `../metrics/demo.py` for the flow.
