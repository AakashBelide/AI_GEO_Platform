# POCs — Proof of Concepts

**Workflow (mandatory):** build a capability here first → write tests → validate → only then
integrate into `../app/`. Nothing goes into the app untested.

Each POC is a self-contained folder with its own `README.md` (purpose, how to run, how it
integrates) and a `tests/` (or `test_*.py`) suite that runs **offline** (external APIs
mocked/replayed; crawler uses saved fixtures).

| POC | Task | Needs API keys? | Status |
|---|---|---|---|
| `rigor/` | O1 — statistical rigor (Wilson CIs, variance, drift) | No (synthetic) | ◐ building |
| `crawler/` | C1 — safe sandbox site crawler + AI-readability audit | No (sandbox) | ☐ |
| `factstore/` | F2 — append-only SQLite fact store | No | ☐ |
| `connectors/` | F3 — OpenAI / Perplexity / Gemini adapters | **Yes** | ☐ blocked |
| `onboarding/` | R1 — brand → auto-prompts → competitors | Yes (light) | ☐ |
| `metrics/` | R2 — mention/citation/SoV/position/sentiment | Yes (light) | ☐ |
| `keyword_to_prompt/` | R3 — keyword → prompt bootstrap | No | ☐ |
| `reconcile/` | O3 — cross-engine reconciliation | Yes | ☐ |
| `causal/` | O2 — controlled before/after attribution | Yes | ☐ |

See `../TASKS.md` for full subtasks, dependencies, and the execution order. POCs that need
keys are blocked until `.env` is filled locally; `rigor/` and `crawler/` proceed now with no
keys and no IP risk.
