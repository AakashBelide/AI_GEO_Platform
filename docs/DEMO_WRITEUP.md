# Demo write-up — a measurement-honest GEO run on a real brand (Task A4)

A short, self-contained narrative of the platform doing its job end-to-end on a real brand, and
the finding it produced. For the full evidence discipline see `docs/OBSERVATIONS_AND_ANALYSIS.md`;
for the running log see `ANALYSIS_REPORT.md`. Every number here is reproducible (§Reproduce).

## The thesis in one line
The commercial GEO market sells a single "visibility score" for how brands show up in AI answers
(ChatGPT, Perplexity, Gemini, Claude). But AI answers are non-deterministic and drift 40–60%
month-to-month, and **zero of ~28 surveyed tools report any statistical confidence**
(`COMPETITIVE_LANDSCAPE.md`). This platform builds the honest version: it reports the uncertainty,
the cross-engine disagreement, and the evidence the market hides.

## What was run
One command, live, under a hard $2/provider budget guard:

```
geo run --brand "Asana" --category "project management software" \
  --target-domain asana.com --competitor-domains monday.com,trello.com,clickup.com \
  --engines openai,perplexity,gemini,anthropic --prompts 10 --repeats 5 --live
```

**10 prompts × 5 repeats × 4 engines = 200 real API calls, total cost ≈ $2.55.** Every prompt,
answer, and citation was persisted to an append-only fact store; the report renders as an
interactive dark dashboard (`data/reports/asana_2026-08-14.html`).

## The headline finding: mention ≠ citation, and it's engine-specific

| Engine | Mentions Asana | Cites **asana.com** | What it links instead |
|---|---:|---:|---|
| OpenAI | **82%** | **0%** (0/50) | techradar, kanbanchi, taskrhino |
| Anthropic | **80%** | **0%** (0/50) | thedigitalprojectmanager, capterra, paymoapp |
| Perplexity | 74% | 40% | reddit (70×), thedigitalprojectmanager, wrike |
| Gemini | 60% | 14% | project-management.com, asana.com, wrike |

**OpenAI and Anthropic recommend Asana in ~80% of answers but never send a click to `asana.com`** —
they cite third-party review sites. Perplexity and Gemini *do* link the brand. A single blended
"visibility score" collapses two things a brand experiences completely differently: being
*recommended* vs. being *linked* — and it differs by engine. That is the GEO strategy insight the
honest measurement surfaces and a score hides.

Two supporting results:
- **Cross-engine citation overlap ≈ 12.7%** (mean pairwise Jaccard) — the engines cite largely
  different webs, so "Share of Voice" is not portable across them. This independently corroborates
  the ~11% figure from the literature (we measured our own).
- **Share of Voice was *not* reliably measurable** even at 50 runs/engine — only 1–4 prompts per
  engine surfaced the brand universe, so the SoV confidence intervals are degenerate. The platform
  **flags this and refuses to rank brands** rather than printing a clean-but-fake number. That
  refusal is the thesis in action.

## Why you can trust it (and where we drew the line)
- **Confidence intervals on every rate** (Wilson / cluster-bootstrap, `pocs/rigor`); a single-run
  score is never shown without its interval.
- **Statistical distinguishability:** the dashboard runs a two-proportion test and states, e.g.,
  *"anthropic vs openai citation rate: NOT distinguishable (within noise)"* — it won't claim a
  difference that isn't real.
- **A caught measurement artifact:** Gemini's grounding URLs are redirect wrappers, so its cited
  domains first looked like a single fake host. We found and fixed it (real domain lives in
  `web.title`); a naive tool would have reported "Gemini cites nothing you do."
- **Recommendations are labelled directional hypotheses, not proven levers** — because proving an
  edit *caused* a change needs a controlled before/after test (`pocs/causal`, Task O2), which the
  platform provides but which requires its own experiment to run.
- **Honesty ledger:** `docs/OBSERVATIONS_AND_ANALYSIS.md` §6 tracks exactly what is and isn't
  substantiated. Real-brand SoV ranking is explicitly *not yet* claimed.

## What the report gives a brand (actionable, evidence-tied)
Auto-generated from this run's data (verbatim examples):
- *Finding:* "openai mentions Asana in 82% of answers but cites asana.com in 0% — it recommends the
  brand without linking it."
- *Recommendation:* "anthropic and openai never cite asana.com but do cite
  thedigitalprojectmanager.com (23), paymoapp.com (18), project-management.com (17), wrike.com (17)
  — a hypothesis worth testing is pursuing presence/mentions on those third-party roundups (PR &
  listings, not on-site SEO)."
- *Recommendation:* "perplexity leans on reddit.com (70 citations) — authentic community presence
  may help, but verify it is causal before investing."

## Reproduce
```bash
uv sync
uv run pytest                       # 212 tests, offline

# 1) the live run (spends ~$2.5, budget-guarded) — or skip and use the saved report
uv run python app/geo.py run --brand "Asana" --category "project management software" \
  --target-domain asana.com --competitor-domains monday.com,trello.com,clickup.com \
  --engines openai,perplexity,gemini,anthropic --prompts 10 --repeats 5 --live

# 2) render the dark dashboard from the saved report (+ evidence from the fact store)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json \
  --store data/geo.sqlite --output data/reports/asana_2026-08-14.html

# 3) the causal drift-trap demo (offline, no spend)
uv run python pocs/causal/demo.py
```

## The one-sentence takeaway
On real data, a brand's "AI visibility" is not one number — it depends on the engine, on whether
you mean *mentioned* or *cited*, and on how much noise the estimate carries; this platform reports
all three, and says so when the honest answer is "we can't tell yet."
