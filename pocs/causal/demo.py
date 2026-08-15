"""Causal attribution demo (Task O2) — the drift trap, on simulated data ($0, offline).

Simulates a before/after experiment where the edit's TRUE effect is +0.15 but the whole
category also drifted +0.10 over the window. Shows that the naive before/after delta (what
competitors report) reads ~+0.25 and looks like a big win, while the difference-in-differences
estimate — netting out the drift the holdout reveals — recovers ~+0.15 with a confidence
interval. Same idea run with a zero true effect shows the naive delta still looks positive
(pure drift) while DiD correctly reports "no effect shown".
"""

from __future__ import annotations

from causal import difference_in_differences, simulate_experiment


def _run(label: str, *, true_effect: float, drift: float, seed: int) -> None:
    treated, control = simulate_experiment(
        baseline=0.20, true_effect=true_effect, drift=drift,
        n_prompts=50, runs_per_prompt=30, seed=seed)
    res = difference_in_differences(treated, control, n_boot=4000, seed=seed)
    print(f"== {label} (true effect {true_effect:+.2f}, background drift {drift:+.2f}) ==")
    print(f"  naive before/after delta : {res.naive_delta:+.3f}   <- what competitors report")
    print(f"  background drift (holdout): {res.background_drift:+.3f}")
    print(f"  causal uplift (DiD)       : {res.did:+.3f} "
          f"[{res.lo:+.3f}, {res.hi:+.3f}] (95% CI)")
    print(f"  verdict: {'SIGNIFICANT' if res.significant else 'not significant'} "
          f"(CI {'excludes' if res.significant else 'includes'} 0)\n")


def main() -> None:
    _run("Real edit that worked", true_effect=0.15, drift=0.10, seed=1)
    _run("No real edit — only drift", true_effect=0.00, drift=0.12, seed=4)
    print("The naive delta is positive in BOTH cases; only the holdout-controlled DiD tells")
    print("them apart. Reporting a raw before/after delta as 'impact' is the trap O2 avoids.")


if __name__ == "__main__":
    main()
