# POC: `dashboard` — modern GEO report (Task A2)

Every commercial GEO tool ships a glossy dashboard built on a **single-run visibility score**.
This POC renders the honest version: it turns a saved `GeoReport` JSON (from `app/geo.py run`)
into a **modern dark analytics dashboard** — Tailwind CSS + Chart.js (interactive charts) — where
every number carries its uncertainty.

| Output | Fn | What |
|---|---|---|
| Dark HTML dashboard | `render_dashboard(report: dict) -> str` | complete HTML string: server-rendered dark UI (Tailwind) + a `<script id="geo-report">` JSON blob that the client uses to build every Chart.js chart |

Pure function (`dict → str`), so the whole thing is testable offline with a synthetic fixture —
no keys, no I/O. (The **rendered page** loads Tailwind + Chart.js from CDNs, so viewing it needs
internet; the server-rendered content — findings, recommendations, tables, heatmap, transcript —
still shows without JS.)

## What it renders (honesty-first)
- **Sticky top nav** (Overview · Gap · Findings · Metrics · Cross-engine · Evidence · Methodology).
- **Hero + stat tiles** — brand, category, mode badge, and big-number cards (engines, prompts ×
  repeats, total citations, mean cross-engine overlap, spend, generated date). A **loud amber
  banner when the mode is `dry-run (synthetic)`** flags the data as NOT a real measurement.
- **Mention-vs-citation gap (the headline)** — a Chart.js grouped horizontal bar (mention % vs
  citation % per engine); the citation bar turns **red** when an engine mentions the brand a lot
  but cites its own domain ~0% (on the real Asana data OpenAI & Anthropic mention ~80% / cite
  `asana.com` 0%), plus red flag cards.
- **Findings & Recommendations** — the `pocs/insights` interpretation layer, high up: plain-English
  findings (restated numbers) and hedged, evidence-tied GEO recommendations (each names a concrete
  engine/domain/count).
- **Per-engine rates with 95% CI** — three Chart.js charts (mention / citation / SoV) drawing the
  point estimate **plus a floating `[lo, hi]` confidence band**, so a wide/degenerate interval is
  visually obvious rather than hidden behind a single percentage.
- **Statistical distinguishability** — every engine pair through `pocs/rigor.two_proportion_test`;
  prints `A vs B: distinguishable / NOT distinguishable (within noise)` so the dashboard never
  implies a difference inside the noise.
- **Cross-engine reconciliation** — a colored **CSS-grid Jaccard heatmap** of pairwise citation
  overlap, unique cited domains per engine, and source-ecosystem divergence.
- **Top cited domains per engine** — Chart.js small-multiple horizontal bars, target domain in
  the accent color.
- **Prompt set / Prompts used** — the intent split + the exact questions, labelled by intent.
- **Methodology card** — fields + caveats rendered **verbatim** (incl. the Gemini grounding-redirect
  proxy caveat).
- **Evidence / transcript** — per engine, native `<details>/<summary>` blocks (no JS) with the
  prompt, the model's actual answer, and its citations (url · domain · position).
- **Notes.**

## Why it's honest
- **CIs everywhere** — the rate charts always draw the interval; degenerate SoV looks degenerate.
- **Distinguishability gate** — reuses the rigor z-test instead of eyeballing point gaps.
- **No stats duplicated** — `two_proportion_test` imported from `pocs/rigor` via the sibling-dir
  sys.path shim.
- **Safe injection** — the report JSON is escaped (`</` → `<\/`) so it can't break out of its
  `<script>`; all server-rendered text is HTML-escaped.

> **Trade-off (by design choice):** the rendered page depends on the Tailwind + Chart.js CDNs, so
> it is **not** a fully offline single file — it needs internet to render the styling/charts. This
> was chosen for richer visuals; the `render_dashboard` function itself stays pure and offline.

## Design for testing
Pure `dict → str`. `test_dashboard.py` builds a synthetic report mirroring the real Asana finding
and asserts the structure renders (brand, the CDN script tags, the `id="geo-report"` data blob,
`<canvas>` charts, the gap flag, a distinguishability verdict, findings/recommendations, a
`<details>` transcript with a citation URL, the heatmap cells, the synthetic banner logic) plus
edge cases (empty reconciliation, single engine, HTML-escaping).

## Run
```bash
uv run pytest pocs/dashboard/ -q          # offline, no keys

# render a saved JSON report into the HTML dashboard (default output under data/reports/)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json \
    --output data/reports/asana_2026-08-14.html

# enrich an older report with the evidence + interpretation layer from the fact store
# (reconstructs prompts/transcript/top-domains + findings/recommendations; no engine re-called)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json \
    --store data/geo.sqlite --output data/reports/asana_2026-08-14.html
```

## Integrates with
Consumes the exact JSON `app/geo.py run` writes (the `GeoReport` dataclass in `app/pipeline.py`),
wired into the CLI as the `report` subcommand. It is the presentation layer for everything the
pipeline measures — metrics (`pocs/metrics`), reconciliation + methodology card (`pocs/reconcile`),
insights (`pocs/insights`), and the statistics (`pocs/rigor`).
