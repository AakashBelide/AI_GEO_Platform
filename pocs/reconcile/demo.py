"""Offline reconciliation demo on SYNTHETIC multi-engine citations (no keys, no network).

Shows the O3 output: cross-engine overlap, per-engine SoV with CIs, the divergence explainer,
and the auto-generated methodology card. The citation sets are fabricated with a deliberate
Reddit-heavy Perplexity vs vendor-heavy OpenAI split so the explainer has something to find.
Swap `_synthetic_runs` for real `pocs/connectors` output to run it live under the budget guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metrics"))

from metrics import RunRecord  # noqa: E402
from reconcile import reconcile  # noqa: E402

TARGET = ["acme.example"]
COMPETITORS = ["rival.example"]
MODELS = {"openai": "gpt-4o-mini", "perplexity": "sonar"}


def _synthetic_runs() -> dict[str, list[RunRecord]]:
    openai = [
        RunRecord(0, "openai", "", ("acme.example", "vendorblog.com")),
        RunRecord(1, "openai", "", ("rival.example", "g2.com")),
        RunRecord(2, "openai", "", ("acme.example", "capterra.com")),
    ]
    perplexity = [
        RunRecord(0, "perplexity", "", ("reddit.com", "acme.example")),
        RunRecord(1, "perplexity", "", ("reddit.com", "rival.example")),
        RunRecord(2, "perplexity", "", ("reddit.com", "wikipedia.org")),
    ]
    return {"openai": openai, "perplexity": perplexity}


def main() -> None:
    runs = _synthetic_runs()
    report = reconcile(
        runs, target_domains=TARGET, competitor_domains=COMPETITORS, models=MODELS,
        generated_utc="2026-08-13T00:00:00+00:00", n_prompts=3, repeats_per_prompt=1,
    )

    print("== O3.1 cross-engine citation overlap ==")
    print(f"  mean pairwise Jaccard: {report.overlap.mean_pairwise_jaccard:.2f}")
    for pair, j in report.overlap.pairwise_jaccard.items():
        print(f"    {pair}: {j:.2f}")

    print("\n== O3.2 per-engine Share of Voice (same normalization, 95% CI) ==")
    for engine, est in report.share_of_voice.items():
        print(f"  {engine:<11} {est}")

    print("\n== O3.3 divergence explainer ==")
    if not report.divergence:
        print("  (no ecosystem over-indexes beyond threshold)")
    for f in report.divergence:
        print(f"  {f.engine} over-indexes '{f.ecosystem}': "
              f"{f.engine_share:.0%} vs {f.mean_share:.0%} mean (+{f.delta:.0%})")

    print("\n== O3.4 methodology card ==")
    print(report.methodology.to_markdown())
    print("\n  (SoV numbers only mean the same thing because the method is disclosed & shared.)")


if __name__ == "__main__":
    main()
