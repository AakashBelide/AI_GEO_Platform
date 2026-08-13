# AI_GEO Platform

A **measurement-honest** Generative Engine Optimization (GEO) toolkit — a local-only
research + engineering project for INFO7375, *Computational Skepticism for AI*.

Where commercial GEO tools ship single-run "visibility scores" despite 40–60% monthly
citation drift, this project builds the parts the whole industry skips: **statistical
rigor (confidence intervals, variance), causal attribution, and transparent cross-engine
reconciliation.**

- **`RESEARCH.md`** — the research report and thesis (evidence-tiered).
- **`COMPETITIVE_LANDSCAPE.md`** — teardown of ~28 competitor tools + what's buildable solo.
- **`Claude_Research.md`** — an earlier research document (preserved from the remote repo).
- **`TASKS.md`** — the concrete build plan and task graph.

## Status
🟡 Early scaffolding. Building POCs first (see `pocs/`), then integrating into `app/`.

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
