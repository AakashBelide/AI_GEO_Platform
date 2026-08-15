r"""Causal attribution: did an edit *cause* the visibility change? (Task O2).

No GEO tool proves an edit caused a citation change — they show a raw before/after delta and
call it impact. But AI answers drift 40-60% month-to-month on their own, so a raw delta is
mostly noise + background drift. This module does the honest version: a **difference-in-
differences (DiD)** estimator with a **holdout control group** that nets out background drift,
reporting the causal uplift **with a confidence interval**, not a point delta.

    causal uplift  =  (treated_post - treated_pre)  -  (control_post - control_pre)
                       \_______ raw delta ________/    \____ background drift ____/

The control prompts are on *unedited* topics measured over the same window, so whatever moved
them is drift we subtract off. The CI is a cluster bootstrap over prompts (the same philosophy
as `pocs/rigor`): resample whole prompts, recompute DiD, take percentiles. If the CI includes 0
the edit is **not** shown to have worked — we say so rather than reporting the raw delta.

Pure computation: no keys, no network. The live workflow (run the pipeline pre-edit, apply a
lever, run it post-edit, feed both here) is documented in the README; the estimator itself is
validated offline on simulated data with a known effect + known drift.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Proven content levers (RESEARCH.md §2.2) — what an experiment would apply to the treated pages.
PROVEN_LEVERS = {
    "quotation": "Add direct quotations from authoritative sources.",
    "statistics": "Add specific statistics / numbers.",
    "cite_sources": "Add explicit citations/references to sources.",
}


@dataclass(frozen=True)
class PrePost:
    """One prompt's binary citation outcome before and after the intervention window.

    ``pre_hits`` of ``pre_n`` runs cited the target before the edit; ``post_hits`` of
    ``post_n`` after. (A "hit" = the target domain/brand was cited in that run.)
    """

    pre_hits: int
    pre_n: int
    post_hits: int
    post_n: int

    def __post_init__(self) -> None:
        for h, n in ((self.pre_hits, self.pre_n), (self.post_hits, self.post_n)):
            if n < 0 or h < 0 or h > n:
                raise ValueError("require 0 <= hits <= n")


@dataclass(frozen=True)
class CausalResult:
    did: float               # difference-in-differences = the causal uplift estimate
    lo: float
    hi: float
    naive_delta: float       # treated post-pre, ignoring drift (the misleading number)
    background_drift: float   # control post-pre (what the holdout reveals)
    treated_delta: float
    confidence: float
    significant: bool         # does the CI exclude 0?
    n_treated: int
    n_control: int

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def summary(self) -> str:
        pct = int(self.confidence * 100)
        verdict = (
            "distinguishable from zero — the edit plausibly caused a change"
            if self.significant
            else "NOT distinguishable from zero — no causal effect shown"
        )
        return (
            f"causal uplift {self.did:+.3f} [{self.lo:+.3f}, {self.hi:+.3f}] ({pct}% CI); "
            f"raw delta {self.naive_delta:+.3f} minus background drift "
            f"{self.background_drift:+.3f}. {verdict}."
        )


def _rate(hits: int, n: int) -> float:
    return hits / n if n else 0.0


def _group_delta(items: list[PrePost]) -> float:
    """Pooled post-rate minus pooled pre-rate for a group of prompts."""
    pre_h = sum(i.pre_hits for i in items)
    pre_n = sum(i.pre_n for i in items)
    post_h = sum(i.post_hits for i in items)
    post_n = sum(i.post_n for i in items)
    return _rate(post_h, post_n) - _rate(pre_h, pre_n)


def _did(treated: list[PrePost], control: list[PrePost]) -> float:
    return _group_delta(treated) - _group_delta(control)


def naive_delta(treated: list[PrePost]) -> float:
    """The number competitors report: treated post-rate minus pre-rate, no drift control."""
    if not treated:
        raise ValueError("need at least one treated prompt")
    return _group_delta(treated)


def difference_in_differences(
    treated: list[PrePost],
    control: list[PrePost],
    *,
    n_boot: int = 5000,
    confidence: float = 0.95,
    seed: int = 0,
) -> CausalResult:
    """Causal uplift via difference-in-differences with a cluster-bootstrap CI.

    ``treated`` = prompts whose target pages were edited; ``control`` = unedited holdout
    prompts measured over the same window. The bootstrap resamples whole prompts within each
    group (their runs are correlated), so the interval reflects between-prompt variability.
    ``significant`` is True only when the CI excludes 0.
    """
    if not treated:
        raise ValueError("need at least one treated prompt")
    if not control:
        raise ValueError(
            "need a control/holdout group — without it drift cannot be separated from effect"
        )
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")

    t, c = list(treated), list(control)
    point = _did(t, c)
    rng = np.random.default_rng(seed)
    mt, mc = len(t), len(c)
    boots = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        ti = rng.integers(0, mt, size=mt)
        ci = rng.integers(0, mc, size=mc)
        boots[b] = _did([t[i] for i in ti], [c[i] for i in ci])
    alpha = 1.0 - confidence
    lo = float(np.quantile(boots, alpha / 2.0))
    hi = float(np.quantile(boots, 1.0 - alpha / 2.0))
    return CausalResult(
        did=float(point),
        lo=lo,
        hi=hi,
        naive_delta=float(_group_delta(t)),
        background_drift=float(_group_delta(c)),
        treated_delta=float(_group_delta(t)),
        confidence=confidence,
        significant=bool(lo > 0.0 or hi < 0.0),
        n_treated=mt,
        n_control=mc,
    )


def simulate_experiment(
    *,
    baseline: float = 0.20,
    true_effect: float = 0.15,
    drift: float = 0.05,
    n_prompts: int = 20,
    runs_per_prompt: int = 30,
    seed: int = 0,
) -> tuple[list[PrePost], list[PrePost]]:
    """Simulate a before/after experiment with a KNOWN effect and KNOWN drift.

    Treated prompts move by ``drift + true_effect``; control prompts move by ``drift`` only.
    A correct estimator recovers ``true_effect`` (not ``true_effect + drift``). Used by the
    tests and the demo to prove the DiD nets out drift that the naive delta does not.
    """
    rng = np.random.default_rng(seed)

    def draw(rate: float) -> int:
        return int(rng.binomial(runs_per_prompt, min(1.0, max(0.0, rate))))

    treated = [
        PrePost(draw(baseline), runs_per_prompt,
                draw(baseline + drift + true_effect), runs_per_prompt)
        for _ in range(n_prompts)
    ]
    control = [
        PrePost(draw(baseline), runs_per_prompt, draw(baseline + drift), runs_per_prompt)
        for _ in range(n_prompts)
    ]
    return treated, control
