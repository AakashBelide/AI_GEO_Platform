# AI_GEO Platform

A **measurement-honest** Generative Engine Optimization (GEO) toolkit — a local-only
research + engineering project for INFO7375, *Computational Skepticism for AI*.

Where commercial GEO tools ship single-run "visibility scores" despite 40–60% monthly
citation drift, this project builds the parts the whole industry skips: **statistical
rigor (confidence intervals, variance), causal attribution, and transparent cross-engine
reconciliation.**

- **`RESEARCH.md`** — the research report and thesis (evidence-tiered).
- **`COMPETITIVE_LANDSCAPE.md`** — teardown of ~28 competitor tools + what's buildable solo.
- **`docs/OBSERVATIONS_AND_ANALYSIS.md`** — standing analysis: observations, interpretation,
  measured metrics, and clearly-labeled opinions (each number cites a reproduction script).
- **`ANALYSIS_REPORT.md`** — running log of dated decisions, costs, and live findings.
- **`docs/DEMO_WRITEUP.md`** — the end-to-end demo narrative + headline finding (A4).
- **`docs/GA4_ATTRIBUTION.md`** — how to detect AI-referral traffic in GA4 (A3, docs-only).
- **`Claude_Research.md`** — an earlier research document (preserved from the remote repo).
- **`TASKS.md`** — the concrete build plan and task graph.

## Status
🟢 All planned tasks complete: **216 tests passing, ruff-clean.** POCs built for F1–F3 (project +
fact store + 4-engine connectors under a $2/provider budget guard), O1 (statistical rigor), O2
(causal difference-in-differences), O3 (cross-engine reconciliation), C1 (safe crawler), R1/R3
(onboarding + keyword→prompt), R2 (metrics with confidence intervals) — all wired behind one CLI
(`app/geo.py`, A1), with a dark Tailwind+D3 dashboard + findings/recommendations (A2) and
attribution/demo docs (A3/A4). Live-verified on all four engines; measured cross-engine citation
overlap ≈10.6–12.7%; on a live Asana run OpenAI/Anthropic mention the brand ~80% but cite its own
domain 0% (≈$2.84 spent of $8.00). See `pocs/`, `app/`, `docs/`, and `TASKS.md`.

## Quick start
```bash
make install                # uv sync
make verify                 # 216 tests + ruff, all offline ($0)   (or: make help)

# End-to-end dry-run (synthetic, $0):
uv run python app/geo.py run --brand "Asana" --category "project management software" \
    --target-domain asana.com --competitor-domains monday.com,trello.com,clickup.com
# add --live to call real engines under the $2/provider budget guard

# Render a saved report into a visual (Tailwind+D3) HTML dashboard:
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json

# Site-side AI-readability audit of a scrape-safe sandbox:
uv run python app/geo.py audit          # (or: make audit)
```

## Requirements (already on the dev machine — no new global installs)
- Python 3.13 + [uv](https://docs.astral.sh/uv/)
- Node 22 + npm
- Docker (optional)
- Playwright (for the crawler POC)

## Setup
```bash
# 1. Secrets (never committed)
cp .env.example .env       # then edit .env with your real API keys
# .env and secrets/ are gitignored — verify with:  git status --ignored

# 2. Python env (per-POC or root; uv manages it)
uv sync                    # once a pyproject.toml exists
uv run pytest              # run tests
```

## Safety & ethics
- **APIs, not scraping**, for answer engines (OpenAI Responses `web_search`, Perplexity
  Sonar, Gemini grounding). Google AI Overviews is proxied via Gemini grounding and
  documented as such — never scraped.
- The crawler POC only touches **scrape-safe sandbox sites**, respects `robots.txt`,
  rate-limits, and caps pages — it must never risk an IP block.
- **No PII or secrets** are ever committed. See `CLAUDE.md` for the hard rules.

## Repo
Remote: `git@github-personal:AakashBelide/AI_GEO_Platform` (local-only development;
no cloud deployment).
