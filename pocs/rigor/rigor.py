"""Statistical-rigor primitives for GEO measurement (POC — Task O1).

The headline differentiator of this project: every GEO competitor ships single-run
point estimates despite 40-60% monthly citation drift. This module treats each
"is brand X cited?" as a Bernoulli trial and reports **uncertainty**, not scores.

Pure computation: no API keys, no network, no IP risk. Fully offline-testable.

References: RESEARCH.md §4.4 (handling non-determinism); the Wilson interval for
small-n binary data; cluster bootstrap for share-of-voice; a simplified
generalizability-theory variance decomposition (Zatuchin 2026).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

__all__ = [
    "Estimate",
    "wilson_interval",
    "proportion_estimate",
    "cluster_bootstrap_ci",
    "share_of_voice_ci",
    "two_proportion_test",
    "TwoPropResult",
    "one_way_variance_components",
    "VarianceComponents",
    "variance_budget_recommendation",
    "citation_drift",
]


# --------------------------------------------------------------------------- #
# Binary-proportion estimates (mention rate, citation rate)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Estimate:
    """A point estimate with a confidence interval and its sample size."""

    point: float
    lo: float
    hi: float
    n: int
    confidence: float = 0.95

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        pct = int(self.confidence * 100)
        return f"{self.point:.3f} [{self.lo:.3f}, {self.hi:.3f}] (n={self.n}, {pct}% CI)"


def _z(confidence: float) -> float:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    return float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Correct for small n and for proportions near 0/1, where the normal
    approximation fails. With no data (n == 0) uncertainty is maximal: [0, 1].
    """
    if successes < 0 or n < 0 or successes > n:
        raise ValueError("require 0 <= successes <= n")
    if n == 0:
        return (0.0, 1.0)
    z = _z(confidence)
    p_hat = successes / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return (float(lo), float(hi))


def proportion_estimate(successes: int, n: int, confidence: float = 0.95) -> Estimate:
    """Point estimate + Wilson CI for a Bernoulli metric (e.g. citation rate)."""
    point = successes / n if n else 0.0
    lo, hi = wilson_interval(successes, n, confidence)
    return Estimate(point=point, lo=lo, hi=hi, n=n, confidence=confidence)


# --------------------------------------------------------------------------- #
# Cluster bootstrap (share of voice) — resample the prompt, not the row
# --------------------------------------------------------------------------- #
def cluster_bootstrap_ci(
    clusters: Sequence,
    statistic: Callable[[Sequence], float],
    *,
    n_boot: int = 5000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Estimate:
    """Percentile bootstrap CI where the resampling unit is a *cluster* (prompt).

    Non-determinism in GEO is correlated within a prompt (all repeats of one
    prompt share its retrieval context), so we resample whole prompts, matching
    how the Zatuchin variance study treats the data.
    """
    if len(clusters) == 0:
        return Estimate(point=0.0, lo=0.0, hi=1.0, n=0, confidence=confidence)
    rng = np.random.default_rng(seed)
    clusters = list(clusters)
    m = len(clusters)
    point = float(statistic(clusters))
    boots = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, m, size=m)
        boots[b] = statistic([clusters[i] for i in idx])
    alpha = 1.0 - confidence
    lo = float(np.quantile(boots, alpha / 2.0))
    hi = float(np.quantile(boots, 1.0 - alpha / 2.0))
    return Estimate(point=point, lo=lo, hi=hi, n=m, confidence=confidence)


def share_of_voice_ci(
    per_prompt_counts: Sequence[tuple[int, int]],
    *,
    n_boot: int = 5000,
    confidence: float = 0.95,
    seed: int = 0,
) -> Estimate:
    """Share of Voice with a cluster-bootstrap CI.

    ``per_prompt_counts`` is a list of ``(target_citations, total_citations)`` per
    prompt. SoV = sum(target) / sum(total), bootstrapped over prompts.
    """

    def sov(rows: Sequence[tuple[int, int]]) -> float:
        tgt = sum(r[0] for r in rows)
        tot = sum(r[1] for r in rows)
        return tgt / tot if tot else 0.0

    return cluster_bootstrap_ci(
        per_prompt_counts, sov, n_boot=n_boot, confidence=confidence, seed=seed
    )


# --------------------------------------------------------------------------- #
# Are two brands distinguishable? (two-proportion z-test)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TwoPropResult:
    diff: float
    z: float
    p_value: float
    distinguishable: bool
    alpha: float


def two_proportion_test(
    k1: int, n1: int, k2: int, n2: int, *, alpha: float = 0.05
) -> TwoPropResult:
    """Pooled two-proportion z-test.

    Answers the question no competitor asks: *are brand A and brand B actually
    distinguishable, or is the gap within noise?* When ``distinguishable`` is
    False, a dashboard must NOT claim one brand beats the other.
    """
    if n1 <= 0 or n2 <= 0:
        raise ValueError("n1 and n2 must be positive")
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        z = 0.0
        p_value = 1.0
    else:
        z = (p1 - p2) / se
        p_value = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
    return TwoPropResult(
        diff=float(p1 - p2),
        z=float(z),
        p_value=p_value,
        distinguishable=p_value < alpha,
        alpha=alpha,
    )


# --------------------------------------------------------------------------- #
# Variance decomposition (where does the noise come from?)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class VarianceComponents:
    """One-way random-effects variance split for a single factor."""

    factor: str
    var_between: float  # variance attributable to the factor's levels
    var_within: float  # residual (within-level) variance
    icc: float  # intraclass correlation = between / (between + within)
    n_levels: int


def one_way_variance_components(
    groups: dict[str, Sequence[float]], factor: str = "factor"
) -> VarianceComponents:
    """Estimate between- vs within-group variance (one-way random effects).

    Uses the classic ANOVA expected-mean-squares estimator:
        var_within  = MS_within
        var_between = max(0, (MS_between - MS_within) / n0)
    where n0 is the (size-corrected) average group size. Negative estimates are
    clamped to 0, as is standard for variance components.
    """
    levels = [np.asarray(v, dtype=float) for v in groups.values() if len(v) > 0]
    a = len(levels)
    if a < 2:
        raise ValueError("need at least 2 non-empty groups")
    sizes = np.array([len(x) for x in levels])
    N = int(sizes.sum())
    grand = float(np.concatenate(levels).mean())
    group_means = np.array([x.mean() for x in levels])

    ss_between = float(np.sum(sizes * (group_means - grand) ** 2))
    ss_within = float(np.sum([np.sum((x - x.mean()) ** 2) for x in levels]))

    df_between = a - 1
    df_within = N - a
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within if df_within > 0 else 0.0

    # size-corrected average group size (n0); equals n for balanced designs
    n0 = (N - float(np.sum(sizes**2)) / N) / (a - 1)
    var_between = max(0.0, (ms_between - ms_within) / n0) if n0 > 0 else 0.0
    var_within = ms_within
    total = var_between + var_within
    icc = var_between / total if total > 0 else 0.0
    return VarianceComponents(
        factor=factor,
        var_between=float(var_between),
        var_within=float(var_within),
        icc=float(icc),
        n_levels=a,
    )


def variance_budget_recommendation(
    components: Sequence[VarianceComponents],
) -> dict[str, object]:
    """Turn variance components into an API-budget recommendation.

    Zatuchin (2026): adding paraphrases/models/languages reduces error variance
    far more per unit cost than repeating the same prompt. So spend calls on the
    highest-variance factors (breadth), not on more repeats.
    """
    ranked = sorted(components, key=lambda c: c.var_between, reverse=True)
    total_between = sum(c.var_between for c in components) or 1.0
    shares = {c.factor: c.var_between / total_between for c in components}
    top = ranked[0].factor if ranked else None
    repeat_share = shares.get("repeat", 0.0)
    breadth_share = 1.0 - repeat_share
    advise_breadth = breadth_share >= repeat_share
    return {
        "variance_share": shares,
        "highest_variance_factor": top,
        "advice": (
            "Prioritise breadth (more paraphrases/models) over repeats: breadth "
            f"factors hold {breadth_share:.0%} of between-variance."
            if advise_breadth
            else "Repeats dominate variance here; a few more repeats are worthwhile."
        ),
        "advise_breadth_over_repeats": advise_breadth,
    }


# --------------------------------------------------------------------------- #
# Drift (how much does the cited-source set churn over time?)
# --------------------------------------------------------------------------- #
def citation_drift(set_a: set[str], set_b: set[str]) -> dict[str, float]:
    """Churn between two cited-domain sets (e.g. this month vs next).

    Replicates the industry finding that 40-60% of cited domains differ month to
    month for identical questions. ``fraction_changed`` = 1 - Jaccard similarity.
    """
    a, b = set(set_a), set(set_b)
    union = a | b
    if not union:
        return {"jaccard": 1.0, "fraction_changed": 0.0, "added": 0.0, "dropped": 0.0}
    inter = a & b
    jaccard = len(inter) / len(union)
    return {
        "jaccard": float(jaccard),
        "fraction_changed": float(1.0 - jaccard),
        "added": float(len(b - a) / len(union)),
        "dropped": float(len(a - b) / len(union)),
    }
