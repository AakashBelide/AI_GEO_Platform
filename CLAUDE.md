# CLAUDE.md — AI_GEO Platform

Project-level guidance for Claude Code (and humans). This file lives **inside** the
`AI_GEO/` repo and applies to everything in it.

## What this project is
A **measurement-honest Generative Engine Optimization (GEO) platform** — a local-only
research/engineering project for the INFO7375 "Computational Skepticism for AI" course.
The thesis (see `RESEARCH.md`): the entire commercial GEO market ships single-run
"visibility scores" despite 40–60% monthly citation drift, and **no competitor reports
statistical confidence, proves causation, or reconciles cross-engine methodology**
(see `COMPETITIVE_LANDSCAPE.md`). This project builds the honest measurement they skip.

## HARD CONSTRAINTS (do not violate)
1. **Repo boundary.** Never create, modify, or delete any file **outside** this `AI_GEO/`
   directory. The parent project has its own CLAUDE.md / INSTRUCTIONS.md / TASKS.md — off-limits.
   The repo root IS `AI_GEO/`, so git will never stage anything outside it. Keep it that way.
2. **No PII / secrets in git, ever.** Real keys → `.env` (gitignored). Anything sensitive
   (PII, credentials, raw exported answers) → `secrets/` (gitignored). Only `.env.example`
   with placeholder values is committed. Never paste real keys into chat or any tracked file.
   Before every commit, run `git status` and sanity-check the file list.
3. **Commit only AI_GEO files.** (Guaranteed by repo root = AI_GEO.) Remote:
   `git@github-personal:AakashBelide/AI_GEO_Platform`. `Claude_Research.md` is the remote's
   original research doc — preserve it and its history.

## Workflow (mandated)
- **POC-first.** Every capability starts as a POC in `pocs/<name>/`, gets **tests**, is
  validated, and only then is integrated into the real app under `app/`.
- **Tests always.** Python → `pytest`; follow good engineering practice (typed, small
  functions, deterministic tests, mock external APIs so the suite runs offline).
- **Local only.** No cloud deploys. No new global installs beyond what's already on the
  system (Python 3.13 + uv, Node 22 + npm, Docker, Playwright).

## Crawler safety (Task 7.3)
Only crawl **scrape-safe sandbox targets** (default `books.toscrape.com`). Always respect
`robots.txt`, set a rate limit + delay, cap page count, and identify via a custom user-agent.
**Never** crawl a target in a way that could get the user's IP blocked or raise ToS concerns.
Do **not** scrape Google AI Overviews or consumer ChatGPT/Perplexity UIs — use official APIs.

## Layout
```
AI_GEO/
├── RESEARCH.md               # primary research report (thesis)
├── COMPETITIVE_LANDSCAPE.md  # competitor teardown + buildable analysis
├── Claude_Research.md        # remote's original research doc (preserved)
├── TASKS.md                  # the build plan (7.1 reusable, 7.2 open lanes, 7.3 crawler)
├── CLAUDE.md                 # this file
├── README.md
├── .env.example              # committed template (placeholders only)
├── .env                      # gitignored — real keys
├── secrets/                  # gitignored — PII / credentials
├── pocs/                     # proof-of-concepts (build + test here first)
└── app/                      # the integrated platform (added after POCs pass)
```

## Commands (once POCs exist)
- `uv run pytest` — run the test suite
- `uv run ruff check .` — lint (if configured)
See `README.md` for setup.
