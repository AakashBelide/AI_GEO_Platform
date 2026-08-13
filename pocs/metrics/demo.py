"""End-to-end R1 -> R2 demo on SYNTHETIC runs (no keys, no network).

Shows the honest headline output: a brand's prompt set is generated (R1) with its skew
and intent guards, then metrics are computed (R2) as estimates *with confidence intervals*.
The engine answers here are fabricated deterministically so the demo spends nothing — swap
`_fake_runs` for real `pocs/connectors` output to run it live under the $2 budget guard.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "onboarding"))

from metrics import RunRecord, compute_brand_metrics  # noqa: E402
from onboarding import BrandProfile, build_prompt_set  # noqa: E402

PROFILE = BrandProfile(
    name="Acme Board",
    category="project management tools",
    domain="acme.example",
    aliases=("Acme", "Acme Board"),
    competitors=("Trellix", "Mondayish"),
    use_cases=("remote teams", "agencies"),
)

TARGET = ["acme.example"]
COMPETITORS = ["trellix.example", "mondayish.example"]


def _fake_runs(prompts, *, repeats: int = 20, seed: int = 7) -> list[RunRecord]:
    """Fabricate engine answers with a KNOWN ~35% citation propensity for the brand."""
    rng = random.Random(seed)
    recs: list[RunRecord] = []
    for pid in range(len(prompts)):
        for _ in range(repeats):
            cites = []
            if rng.random() < 0.35:  # brand cited ~35% of the time
                cites.append("acme.example")
            if rng.random() < 0.55:
                cites.append(rng.choice(COMPETITORS))
            rng.shuffle(cites)  # citation order varies -> a realistic mean rank
            names_brand = rng.random() < 0.45
            text = "Acme Board is a solid option." if names_brand else "Consider the alternatives."
            recs.append(RunRecord(pid, "synthetic", text, tuple(cites)))
    return recs


def main() -> None:
    ps = build_prompt_set(PROFILE, n_total=30)
    print("== R1: prompt set ==")
    print(f"  {len(ps.prompts)} prompts | skew: {ps.skew.message}")
    for intent, d in ps.intents.items():
        print(f"    {intent:<14} {int(d['count']):>2}  ({d['fraction']:.0%})")

    runs = _fake_runs(ps.prompts, repeats=20)
    m = compute_brand_metrics(
        runs, aliases=list(PROFILE.all_names()),
        target_domains=TARGET, competitor_domains=COMPETITORS, engine="synthetic",
    )
    print(f"\n== R2: metrics with 95% CIs (n={m.n_runs} synthetic runs) ==")
    print(f"  mention rate   {m.mention}")
    print(f"  citation rate  {m.citation}")
    print(f"  share of voice {m.share_of_voice}")
    pos = m.position
    rank = f"{pos.mean_rank:.2f}" if pos.mean_rank is not None else "n/a"
    print(f"  position       cited in {pos.n_cited} runs, mean rank {rank}")
    print("\n  (single-run scores would hide these intervals — that's the whole point.)")


if __name__ == "__main__":
    main()
