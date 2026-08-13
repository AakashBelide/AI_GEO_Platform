"""Frugal LIVE cross-engine reconciliation (Task O3 validation).

Runs a small set of commercial / current-information prompts (chosen to actually trigger
web search — see ANALYSIS_REPORT observation O-2) through all four engines, 1 repeat each,
budget-gated, then reconciles: our own cross-engine citation-overlap number, per-engine SoV,
the divergence explainer, and the methodology card.

Deliberately minimal (4 prompts × 4 engines = 16 calls) — enough to measure overlap, cheap
enough to stay in cents. Every call passes the CostLedger guard; a provider can never exceed
its $2 cap. Engines that error (or return no citations) are skipped, not fatal.

    uv run python pocs/reconcile/reconcile_live.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "connectors"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metrics"))

from budget import CostLedger  # noqa: E402
from connectors import ENGINES  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from metrics import RunRecord  # noqa: E402
from reconcile import reconcile  # noqa: E402

load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))

# Public brand universe (project-management category) — no PII, all public companies.
TARGET = ["asana.com"]
COMPETITORS = ["monday.com", "trello.com", "clickup.com"]

PROMPTS = [
    "What are the best project management tools in 2026? Include sources.",
    "Which project management software do agencies recommend right now, with citations?",
    "Compare the top project management platforms for remote teams, cite sources.",
    "Best affordable project management software in 2026 — list options with links.",
]

MODELS = {
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "perplexity": os.getenv("PERPLEXITY_MODEL", "sonar"),
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
}

LEDGER = CostLedger(path=Path("data/cost_ledger.json"),
                    cap_usd=float(os.getenv("BUDGET_USD_PER_PROVIDER", "2.00")))


def main() -> None:
    runs_by_engine: dict[str, list[RunRecord]] = {}
    total_cost = 0.0
    print(f"Live reconciliation: {len(PROMPTS)} prompts × {len(ENGINES)} engines\n")

    for provider, cls in ENGINES.items():
        eng = cls(provider, MODELS[provider], LEDGER)
        records: list[RunRecord] = []
        for pid, prompt in enumerate(PROMPTS):
            try:
                r = eng.query(prompt, run_index=pid)
            except Exception as e:  # noqa: BLE001 - report and continue
                print(f"[FAIL] {provider:<11} p{pid}: {type(e).__name__}: {e}")
                continue
            total_cost += r.est_cost_usd
            records.append(RunRecord(pid, provider, r.answer_text, tuple(r.domains)))
        if records:
            runs_by_engine[provider] = records
        n_cites = sum(len(r.cited_domains) for r in records)
        print(f"[OK]   {provider:<11} {len(records)} runs, {n_cites} citations, "
              f"spend ${LEDGER.spent(provider):.4f}/${LEDGER.cap_usd:.2f}")

    engines_with_data = {e: r for e, r in runs_by_engine.items()
                         if any(rr.cited_domains for rr in r)}
    if len(engines_with_data) < 2:
        print("\nNot enough engines returned citations to reconcile (need >= 2).")
        return

    report = reconcile(
        engines_with_data, target_domains=TARGET, competitor_domains=COMPETITORS,
        models={e: MODELS[e] for e in engines_with_data},
        generated_utc=datetime.now(UTC).isoformat(),
        n_prompts=len(PROMPTS), repeats_per_prompt=1,
    )

    print("\n== cross-engine citation overlap (OUR measured number) ==")
    print(f"  mean pairwise Jaccard: {report.overlap.mean_pairwise_jaccard:.3f}")
    for pair, j in report.overlap.pairwise_jaccard.items():
        print(f"    {pair}: {j:.3f}")
    print(f"  unique domains/engine: {report.overlap.per_engine_unique_domains}")

    print("\n== per-engine Share of Voice (asana.com vs monday/trello/clickup) ==")
    for engine, est in report.share_of_voice.items():
        print(f"  {engine:<11} {est}")

    print("\n== divergence explainer ==")
    for f in report.divergence or []:
        print(f"  {f.engine} over-indexes '{f.ecosystem}': "
              f"{f.engine_share:.0%} vs {f.mean_share:.0%} (+{f.delta:.0%})")
    if not report.divergence:
        print("  (no ecosystem over-indexes beyond threshold at this sample size)")

    print(f"\n=== total spend this run: ${total_cost:.4f} ===")


if __name__ == "__main__":
    main()
