# POCs — Proof of Concepts

**Workflow (mandatory):** build a capability here first → write tests → validate → only then
integrate into `../app/`. Nothing goes into the app untested.

Each POC is a self-contained folder with its own `README.md` (purpose, how to run, how it
integrates) and a `tests/` (or `test_*.py`) suite that runs **offline** (external APIs
mocked/replayed; crawler uses saved fixtures).

| POC | Task | Needs API keys? | Status |
|---|---|---|---|
| `rigor/` | O1 — statistical rigor (Wilson CIs, variance, drift) | No (synthetic) | ☑ 22 tests |
| `crawler/` | C1 — safe sandbox site crawler + AI-readability audit | No (sandbox) | ☑ 12 tests |
| `connectors/budget.py` | F3 — budget guard / cost ledger ($2/provider cap) | No | ☑ 10 tests |
| `factstore/` | F2 — append-only SQLite fact store | No | ☑ 7 tests |
| `connectors/` | F3 — OpenAI / Perplexity / Gemini / Anthropic adapters | **Yes** | ☑ 15 tests + live-verified |
| `onboarding/` | R1 — brand → auto-prompts → competitors | No (deterministic) | ☑ 16 tests |
| `metrics/` | R2 — mention/citation/SoV/position/sentiment | No (synthetic) | ☑ 20 tests |
| `keyword_to_prompt/` | R3 — keyword → prompt bootstrap | No | ☑ 14 tests |
| `reconcile/` | O3 — cross-engine reconciliation | No (offline); live runner optional | ☑ 13 tests + live-verified |
| `dashboard/` | A2 — GeoReport → dark Tailwind+D3 dashboard | No (render); CDN to view | ☑ 24 tests |
| `insights/` | A2 — findings + GEO recommendations (evidence-tied) | No | ☑ 20 tests |
| `causal/` | O2 — controlled before/after attribution (DiD + holdout) | No (synthetic) | ☑ 10 tests |

**229 tests passing, ruff clean.** See `../TASKS.md` for subtasks/dependencies and
`../ANALYSIS_REPORT.md` for the running log of decisions, costs, and live findings.
Every suite runs fully offline; live engine calls happen only in `connectors/smoke.py`
under the $2/provider budget guard.
