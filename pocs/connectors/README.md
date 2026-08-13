# POC: `connectors` — cross-engine citation tracker + budget guard (Task F3)

The atomic core of the platform: run a prompt through four answer engines and extract
who gets **cited**, behind one uniform interface — with a hard per-provider spend cap.

## Engines
| Provider | Model (cheapest-decent) | Citations from |
|---|---|---|
| OpenAI | `gpt-4o-mini` | Responses API `web_search` → `url_citation` annotations |
| Perplexity | `sonar` | Sonar REST → `search_results[]` / `citations[]` |
| Gemini | `gemini-2.5-flash` | grounding → `grounding_chunks[].web` *(documented proxy for AI Overviews)* |
| Anthropic | `claude-haiku-4-5` | `web_search_20250305` → `web_search_result` blocks |

## Money safety (`budget.py`)
- **$2 hard cap per provider**, persisted to `data/cost_ledger.json` (gitignored) so it
  holds across restarts. `CostLedger.guard()` runs **before** every network call and raises
  `BudgetExceeded` if the estimated spend would breach the cap — verified by a test that the
  network is never touched once over budget.
- Costs are conservative estimates (tokens × published price + per-call tool fee).
- Raw payloads are cached under `data/cache/` so re-analysis never re-calls the API.

## Design for testing
Citation **parsing is pure** (`parse_openai/perplexity/gemini/anthropic`) and tested offline
against real-shape fixtures. The network layer is a thin `_raw_call` override, exercised only
by the frugal live `smoke.py`.

## Run
```bash
uv run pytest pocs/connectors/ -q          # 25 tests, offline (no keys, no network)
uv run python pocs/connectors/smoke.py     # 1 short prompt/engine, budget-gated (spends cents)
```

## Verified live (2026-08-13)
- **All four engines live-verified** on commercial/current-info prompts (O3 run): OpenAI 38,
  Perplexity 76, Gemini 85, Anthropic 30 citations across 4 prompts.
- **Gemini grounding URLs are redirect wrappers** (`vertexaisearch…/grounding-api-redirect/…`);
  the parser now recovers the real domain from `web.title` (`_gemini_domain`) so Gemini is
  comparable to the other engines. Gemini-2.5-flash still returns empty on *trivial* prompts
  (thinking-model quirk) — parser yields empty correctly; use substantive prompts for grounding.
- Trivial/evergreen prompts don't trigger search (0 citations) — a measurement-design finding.

See `../../ANALYSIS_REPORT.md` for the running log of decisions, costs, and findings.

## Integration
Feeds the fact store (`pocs/factstore`) — each `EngineResponse` becomes one immutable `runs`
row + `citations` rows — then the rigor module (`pocs/rigor`) computes CIs / SoV over them.
