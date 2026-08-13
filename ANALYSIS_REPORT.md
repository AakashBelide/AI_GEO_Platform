# ANALYSIS REPORT — AI_GEO Platform

A running, referenceable log of what was built, the decisions made, the models/costs used,
and what was learned. Append new dated entries at the top of §5 as work continues.

_Last updated: 2026-08-13._

---

## 1. Project in one line
A **measurement-honest** GEO platform: it reports the statistical uncertainty (confidence
intervals, variance, cross-engine disagreement) that the entire commercial GEO market omits.
Thesis + evidence in `RESEARCH.md`; competitor teardown in `COMPETITIVE_LANDSCAPE.md`; build
plan in `TASKS.md`.

## 2. What exists today (all tested, all green)
| Component | Task | Location | Tests | Needs keys? |
|---|---|---|---|---|
| Statistical rigor (Wilson CIs, cluster-bootstrap SoV, distinguishability, variance, drift) | O1 | `pocs/rigor/` | 22 | No |
| Safe site crawler + AI-readability audit | C1 / §7.3 | `pocs/crawler/` | 12 | No |
| Budget guard / cost ledger ($2/provider hard cap) | F3 | `pocs/connectors/budget.py` | 10 | No |
| Append-only SQLite fact store | F2 | `pocs/factstore/` | 7 | No |
| Cross-engine citation connectors (4 engines) | F3 | `pocs/connectors/connectors.py` | 13 | Yes (live) |

**Total: 64 tests passing, ruff clean.** Every POC runs its suite fully offline (external APIs
mocked/replayed, crawler uses fixtures) so the suite never spends budget or touches the network.

## 3. Cost controls (money safety)
- **Budget: $2 per provider**, set in `.env` as `BUDGET_USD_PER_PROVIDER=2.00`.
- Enforced by `CostLedger` — persisted to `data/cost_ledger.json` (gitignored) so the cap
  survives restarts. `guard()` runs **before** each call; a test proves the network is never
  touched once a provider is over budget.
- Raw responses cached under `data/cache/` → re-analysis never re-calls the API.
- Cost = tokens × published price + per-call tool fee (deliberately conservative / rounds up).

## 4. Model choices (cheapest-but-decent, per the budget)
| Provider | Model | Why | Notes |
|---|---|---|---|
| OpenAI | `gpt-4o-mini` | cheap; supports Responses API `web_search` | ~$0.15/$0.60 per M + ~$0.025/search |
| Perplexity | `sonar` | cheapest web-grounded LLM | $1/M in+out; search included |
| Gemini | `gemini-2.5-flash` | cheap; Google Search grounding | **proxy for AI Overviews — documented, not identical** |
| Anthropic | `claude-haiku-4-5` | cheapest Claude ($1/$5) | web search uses **basic `web_search_20250305`** (the `_20260209` dynamic-filtering variant needs Opus/Sonnet tiers) |
Overridable via `.env` (`OPENAI_MODEL`, `PERPLEXITY_MODEL`, `GEMINI_MODEL`, `ANTHROPIC_MODEL`).

## 5. Run log & findings

### 2026-08-13 — First live smoke test (all 4 engines, 1 short prompt each)
Prompt: _"What are the top 2 project management tools? Answer in one sentence."_

| Engine | Result | Cost | Citations | Note |
|---|---|---|---|---|
| OpenAI `gpt-4o-mini` | ✅ answered | $0.0251 | 0 | didn't search (prompt answerable from knowledge) |
| Perplexity `sonar` | ❌ **401 Unauthorized** | $0 | — | **provided key is rejected — needs a valid key** |
| Gemini `gemini-2.5-flash` | ✅ (empty text) | $0.0001 | 0 | thinking-model returned no text/chunks on a trivial prompt |
| Anthropic `claude-haiku-4-5` | ✅ answered | $0.0126 | 0 | chose not to search ("I don't need to search") |

### 2026-08-13 — Citation-extraction validation (forced web search)
Prompt (forces search): _"Search the web: best AI search visibility (GEO) tracking tools in 2026 … with sources."_ on `claude-haiku-4-5`.
- **✅ 6 citations parsed** end-to-end: frase.io, humanizeai.com, stackmatix.com,
  midastouchinfotech.com, thatmarketingbuddy.com, dageno.ai — with titles + positions.
- Cost $0.0218. Confirms the full loop: budget guard → live call → parse → cost record.

**Spend so far (of $2.00 each):** OpenAI ~$0.025 · Gemini ~$0.0001 · Anthropic ~$0.034 · Perplexity $0.

### Learnings
1. **Citation extraction depends on the model actually searching.** Trivial/evergreen prompts
   are answered from parametric knowledge with 0 citations. The prompt set (Task R1) must use
   **commercial / current-info** phrasing to reliably trigger retrieval — this is itself a
   measurement-design finding worth writing up.
2. **Gemini-2.5-flash is a thinking model** and can return empty text on trivial prompts. For
   grounding data, use substantive prompts; the parser handles empty correctly.
3. **Perplexity key is currently invalid (401).** Blocks the Perplexity engine until replaced.
4. The parsers are validated against real API payload shapes (offline fixtures) **and** on live
   Anthropic data — the atomic core of the platform works.

## 6. Open items / what I need
- **Perplexity API key** — the current one returns 401. Replace it in `.env` (`PERPLEXITY_API_KEY=`)
  to enable the 4th engine. (Do not paste keys into chat — edit `.env` locally.)
- Next tasks that need keys: R1 (brand → auto-prompts), R2 (metrics: mention/citation/SoV/sentiment),
  O3 (cross-engine reconciliation), O2 (causal before/after). All will run under the same $2 caps.
- Tasks buildable now with no keys: finishing O1 integration, R3 (keyword→prompt).

## 7. How to reproduce
```bash
cp .env.example .env          # then add real keys (already done locally)
uv sync
uv run pytest -q              # 64 tests, offline
uv run python pocs/connectors/smoke.py        # frugal live check (spends cents)
uv run python pocs/crawler/demo.py            # safe sandbox crawl
```
