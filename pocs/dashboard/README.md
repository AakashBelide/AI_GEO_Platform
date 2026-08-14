# POC: `dashboard` — local honesty-first HTML report (Task A2)

Every commercial GEO tool ships a glossy dashboard built on a **single-run visibility
score**. This POC renders the honest version: it turns a saved `GeoReport` JSON (from
`app/geo.py run`) into **one self-contained HTML file** — inline CSS, hand-written inline
SVG charts, no server, no network, no external assets — so it opens directly in a browser
and every number carries its uncertainty.

| Output | Fn | What |
|---|---|---|
| Standalone document | `render_dashboard(report: dict) -> str` | complete HTML string (all CSS/SVG inlined) |
| CI bar (the core visual) | `ci_bar_svg(point, lo, hi, …) -> str` | inline-SVG 0–100% bar with a point ● + 95% confidence band/whisker; reused for mention / citation / SoV |

Pure functions (`dict → str`), so the whole thing is offline-testable with a synthetic
fixture — no keys, no I/O.

## What it renders (honesty-first)
- **Header** — brand, category, generated date, total spend, and a **loud banner when the
  mode is `dry-run (synthetic)`** flagging the data as NOT a real measurement.
- **Prompt set** — count, the 80/10/10 intent split, and the branded-skew check message.
- **Per-engine metrics table** — mention / citation / share-of-voice, each as a **CI bar**,
  never a bare point score.
- **Mention-vs-citation gap callout (the headline finding)** — for each engine, mention rate
  beside citation-of-own-domain rate; engines that mention the brand a lot but cite its own
  domain at/near zero are flagged `mentioned, not cited`. On the real Asana data OpenAI and
  Anthropic mention ~80% but cite `asana.com` 0%.
- **Cross-engine reconciliation** — mean pairwise citation-overlap (Jaccard), unique cited
  domains per engine, and the source-ecosystem divergence findings.
- **Statistical distinguishability** — for the citation metric, every engine pair is run
  through `pocs/rigor.two_proportion_test`; the card prints
  `A vs B: distinguishable / NOT distinguishable (within noise)`, so the dashboard never
  implies a difference that is inside the noise.
- **Findings & Recommendations (Task A3)** — the interpretation layer from `pocs/insights`,
  placed right after the gap callout: plain-English findings (restated numbers) and hedged,
  evidence-tied GEO recommendations (each names a concrete engine/domain/count).
- **Methodology card** — fields + caveats rendered **verbatim** (incl. the Gemini
  grounding-redirect proxy caveat).
- **Top cited domains per engine** — a compact per-engine table of the most-cited domains
  with counts, highlighting the target domain where an engine cites it.
- **Prompts used** — the exact prompt set, labelled by intent.
- **Evidence / transcript** — per engine, a native `<details>`/`<summary>` block per prompt
  (no JS) showing the prompt, the model's actual answer, and its citations (url · domain ·
  position). Citation URLs appear as text in the body; the `<head>`/`<style>` stay asset-free.
- **Notes.**

## Why it's honest
- **CIs everywhere** — the SVG bar always shows the interval, so a wide/degenerate estimate
  is visually obvious rather than hidden behind a single percentage.
- **Distinguishability gate** — reuses the rigor POC's z-test instead of eyeballing point
  gaps; "within noise" is stated, not glossed over.
- **No stats duplicated** — `two_proportion_test` is imported from `pocs/rigor` via the same
  sibling-dir sys.path shim `pocs/metrics/metrics.py` uses.
- **Self-contained** — no CDNs, fonts, or scripts; the file works fully offline.

## Design for testing
Pure `dict → str`. `test_dashboard.py` builds a small synthetic report mirroring the real
Asana finding and asserts each section renders (brand, an `<svg>`, the gap callout, a
distinguishability verdict, the methodology caveats), plus an empty-reconciliation edge case.

## Run
```bash
uv run pytest pocs/dashboard/ -q          # offline, no keys

# render a saved JSON report into an HTML dashboard (default output under data/reports/)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json \
    --output data/reports/asana_2026-08-14.html

# enrich an older report with the evidence + interpretation layer from the fact store
# (reconstructs prompts/transcript/top-domains + findings/recommendations; no engine re-called)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json \
    --store data/geo.sqlite --output data/reports/asana_2026-08-14.html
```

## Integrates with
Consumes the exact JSON `app/geo.py run` writes (the `GeoReport` dataclass in
`app/pipeline.py`) and is wired into the same CLI as the `report` subcommand. It is the
presentation layer for everything the pipeline measures — the metrics (`pocs/metrics`), the
reconciliation + methodology card (`pocs/reconcile`), and the statistics (`pocs/rigor`).
