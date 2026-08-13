"""Frugal live smoke test for all four engines (Task F3 validation).

Runs ONE short prompt through each engine, budget-gated, and prints the parsed
citations + estimated cost. Deliberately minimal — validates wiring without
burning budget. Each engine is isolated so one failure doesn't block the others.

    uv run python pocs/connectors/smoke.py
"""

from __future__ import annotations

import os
from pathlib import Path

from budget import CostLedger
from connectors import ENGINES
from dotenv import load_dotenv

load_dotenv()

PROMPT = "What are the top 2 project management tools? Answer in one sentence."
LEDGER = CostLedger(path=Path("data/cost_ledger.json"),
                    cap_usd=float(os.getenv("BUDGET_USD_PER_PROVIDER", "2.00")))
MODELS = {
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "perplexity": os.getenv("PERPLEXITY_MODEL", "sonar"),
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
}


def main() -> None:
    print(f"Prompt: {PROMPT}\n")
    for provider, cls in ENGINES.items():
        model = MODELS[provider]
        eng = cls(provider, model, LEDGER)
        try:
            r = eng.query(PROMPT)
            doms = ", ".join(r.domains[:5]) or "(none parsed)"
            print(f"[OK]   {provider:<11} {model}")
            print(f"       cost≈${r.est_cost_usd:.4f}  tokens={r.input_tokens}/{r.output_tokens}"
                  f"  citations={len(r.citations)}")
            print(f"       domains: {doms}")
            print(f"       answer:  {r.answer_text[:120].strip()}...")
        except Exception as e:  # noqa: BLE001 - report per-engine and continue
            print(f"[FAIL] {provider:<11} {model}: {type(e).__name__}: {e}")
        print(f"       provider spend: ${LEDGER.spent(provider):.4f} / ${LEDGER.cap_usd:.2f}\n")

    print("=== budget summary ===")
    for p, s in LEDGER.summary().items():
        print(f"  {p:<11} spent ${s['spent']:.4f}  remaining ${s['remaining']:.4f}")


if __name__ == "__main__":
    main()
