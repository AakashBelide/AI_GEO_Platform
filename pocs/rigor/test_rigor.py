"""Offline tests for the statistical-rigor POC (Task O1). No keys, no network."""

from __future__ import annotations

import math

import numpy as np
import pytest
from rigor import (
    citation_drift,
    cluster_bootstrap_ci,
    one_way_variance_components,
    proportion_estimate,
    share_of_voice_ci,
    two_proportion_test,
    variance_budget_recommendation,
    wilson_interval,
)


# --------------------------------------------------------------------------- #
# Wilson interval
# --------------------------------------------------------------------------- #
def test_wilson_no_data_is_maximally_uncertain():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_zero_successes_known_value():
    lo, hi = wilson_interval(0, 10, confidence=0.95)
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=1e-3)  # classic textbook value


def test_wilson_is_symmetric_at_half():
    lo, hi = wilson_interval(5, 10, confidence=0.95)
    assert lo == pytest.approx(1 - hi, abs=1e-9)
    assert lo < 0.5 < hi


def test_wilson_bounds_stay_in_unit_interval():
    for k, n in [(0, 3), (3, 3), (1, 1), (7, 20), (19, 20)]:
        lo, hi = wilson_interval(k, n)
        assert 0.0 <= lo <= hi <= 1.0


def test_wilson_width_shrinks_with_n():
    w_small = wilson_interval(5, 10)[1] - wilson_interval(5, 10)[0]
    w_large = wilson_interval(50, 100)[1] - wilson_interval(50, 100)[0]
    assert w_large < w_small


def test_wilson_rejects_bad_input():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(-1, 10)


def test_proportion_estimate_contains_point():
    est = proportion_estimate(3, 12)
    assert est.point == pytest.approx(0.25)
    assert est.lo <= est.point <= est.hi
    assert est.n == 12
    assert est.width == pytest.approx(est.hi - est.lo)


# --------------------------------------------------------------------------- #
# Cluster bootstrap / share of voice
# --------------------------------------------------------------------------- #
def test_share_of_voice_point_matches_aggregate():
    rows = [(2, 4), (1, 5), (3, 6)]  # SoV = 6/15 = 0.4
    est = share_of_voice_ci(rows, n_boot=2000, seed=1)
    assert est.point == pytest.approx(0.4)
    assert est.lo <= est.point <= est.hi
    assert 0.0 <= est.lo <= est.hi <= 1.0


def test_share_of_voice_is_deterministic_with_seed():
    rows = [(2, 4), (1, 5), (3, 6), (0, 2)]
    a = share_of_voice_ci(rows, n_boot=1500, seed=42)
    b = share_of_voice_ci(rows, n_boot=1500, seed=42)
    assert (a.lo, a.hi) == (b.lo, b.hi)


def test_bootstrap_empty_is_maximally_uncertain():
    est = cluster_bootstrap_ci([], lambda rows: 0.0)
    assert (est.lo, est.hi, est.n) == (0.0, 1.0, 0)


def test_bootstrap_ci_narrows_with_more_clusters():
    rng = np.random.default_rng(0)
    few = [(int(x), 10) for x in rng.integers(0, 11, size=5)]
    many = [(int(x), 10) for x in rng.integers(0, 11, size=200)]
    w_few = share_of_voice_ci(few, n_boot=2000, seed=3).width
    w_many = share_of_voice_ci(many, n_boot=2000, seed=3).width
    assert w_many < w_few


# --------------------------------------------------------------------------- #
# Two-proportion distinguishability
# --------------------------------------------------------------------------- #
def test_identical_proportions_not_distinguishable():
    res = two_proportion_test(5, 10, 5, 10)
    assert res.diff == pytest.approx(0.0)
    assert not res.distinguishable
    assert res.p_value == pytest.approx(1.0)


def test_large_gap_is_distinguishable():
    res = two_proportion_test(90, 100, 10, 100)
    assert res.distinguishable
    assert res.p_value < 0.05
    assert res.diff == pytest.approx(0.8)


def test_small_gap_small_n_not_distinguishable():
    # 6/10 vs 4/10 — a real gap in point estimate, but not significant at small n
    res = two_proportion_test(6, 10, 4, 10)
    assert not res.distinguishable


def test_two_proportion_rejects_zero_n():
    with pytest.raises(ValueError):
        two_proportion_test(1, 0, 1, 5)


# --------------------------------------------------------------------------- #
# Variance components
# --------------------------------------------------------------------------- #
def test_variance_components_recovers_injected_variance():
    rng = np.random.default_rng(7)
    sigma_between, sigma_within = 2.0, 1.0
    groups = {}
    for g in range(60):
        level_mean = rng.normal(0.0, sigma_between)
        groups[f"g{g}"] = level_mean + rng.normal(0.0, sigma_within, size=40)
    vc = one_way_variance_components(groups, factor="model")
    assert vc.var_between == pytest.approx(sigma_between**2, rel=0.5)
    assert vc.var_within == pytest.approx(sigma_within**2, rel=0.25)
    assert 0.0 <= vc.icc <= 1.0
    assert vc.n_levels == 60


def test_variance_components_needs_two_groups():
    with pytest.raises(ValueError):
        one_way_variance_components({"only": [1.0, 2.0, 3.0]})


def test_budget_recommends_breadth_when_paraphrase_dominates():
    rng = np.random.default_rng(1)
    # paraphrase factor: big between-variance; repeat factor: tiny between-variance
    para = {f"p{i}": rng.normal(rng.normal(0, 3), 0.5, size=20) for i in range(30)}
    repeat = {f"r{i}": rng.normal(rng.normal(0, 0.2), 0.5, size=20) for i in range(30)}
    vc_para = one_way_variance_components(para, factor="paraphrase")
    vc_repeat = one_way_variance_components(repeat, factor="repeat")
    rec = variance_budget_recommendation([vc_para, vc_repeat])
    assert rec["highest_variance_factor"] == "paraphrase"
    assert rec["advise_breadth_over_repeats"] is True


# --------------------------------------------------------------------------- #
# Drift
# --------------------------------------------------------------------------- #
def test_drift_identical_sets_zero_change():
    d = citation_drift({"a.com", "b.com"}, {"a.com", "b.com"})
    assert d["fraction_changed"] == pytest.approx(0.0)
    assert d["jaccard"] == pytest.approx(1.0)


def test_drift_disjoint_sets_full_change():
    d = citation_drift({"a.com"}, {"b.com"})
    assert d["fraction_changed"] == pytest.approx(1.0)
    assert d["jaccard"] == pytest.approx(0.0)


def test_drift_half_overlap_known_jaccard():
    # {a,b} vs {b,c}: intersection 1, union 3 -> jaccard 1/3
    d = citation_drift({"a", "b"}, {"b", "c"})
    assert d["jaccard"] == pytest.approx(1 / 3)
    assert d["added"] == pytest.approx(1 / 3)
    assert d["dropped"] == pytest.approx(1 / 3)


def test_drift_empty_union():
    d = citation_drift(set(), set())
    assert d["fraction_changed"] == 0.0
    assert math.isclose(d["jaccard"], 1.0)
