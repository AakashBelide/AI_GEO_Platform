"""Offline tests for the causal-attribution POC (Task O2). No keys, no network."""

from __future__ import annotations

import pytest
from causal import (
    PROVEN_LEVERS,
    PrePost,
    difference_in_differences,
    naive_delta,
    simulate_experiment,
)


# --- input validation ------------------------------------------------------ #
def test_prepost_rejects_impossible_counts():
    with pytest.raises(ValueError):
        PrePost(pre_hits=5, pre_n=3, post_hits=0, post_n=3)  # hits > n


def test_did_requires_treated_and_control():
    good = [PrePost(2, 10, 5, 10)]
    with pytest.raises(ValueError):
        difference_in_differences([], good)
    with pytest.raises(ValueError):
        difference_in_differences(good, [])  # no control => cannot separate drift


# --- the core property: DiD recovers the true effect, naive delta does not -- #
def test_did_recovers_true_effect_within_ci():
    treated, control = simulate_experiment(
        baseline=0.2, true_effect=0.15, drift=0.05, n_prompts=40, seed=1)
    res = difference_in_differences(treated, control, n_boot=2000, seed=1)
    # the causal estimate brackets the injected 0.15 ...
    assert res.lo <= 0.15 <= res.hi
    # ... and is meaningfully below the naive delta, which is inflated by the +0.05 drift
    assert res.naive_delta > res.did
    assert res.background_drift == pytest.approx(res.naive_delta - res.did, abs=1e-9)


def test_naive_delta_is_biased_by_drift():
    treated, control = simulate_experiment(
        baseline=0.2, true_effect=0.15, drift=0.10, n_prompts=40, seed=2)
    res = difference_in_differences(treated, control, n_boot=1500, seed=2)
    # naive delta ~= effect + drift; it overstates the truth by roughly the drift
    assert res.naive_delta > 0.15
    assert res.did < res.naive_delta - 0.03


def test_real_effect_is_significant():
    treated, control = simulate_experiment(
        baseline=0.2, true_effect=0.25, drift=0.05, n_prompts=50, seed=3)
    res = difference_in_differences(treated, control, n_boot=2000, seed=3)
    assert res.significant  # CI excludes 0
    assert res.lo > 0.0


def test_zero_effect_is_not_significant():
    # only drift, no real edit effect -> DiD should NOT flag an effect
    treated, control = simulate_experiment(
        baseline=0.25, true_effect=0.0, drift=0.12, n_prompts=50, seed=4)
    res = difference_in_differences(treated, control, n_boot=2000, seed=4)
    assert not res.significant
    assert res.lo <= 0.0 <= res.hi
    # the naive delta, however, is large and positive purely from drift — the trap
    assert res.naive_delta > 0.08


# --- determinism + summary ------------------------------------------------- #
def test_bootstrap_is_deterministic_for_a_seed():
    treated, control = simulate_experiment(n_prompts=25, seed=5)
    a = difference_in_differences(treated, control, n_boot=1000, seed=7)
    b = difference_in_differences(treated, control, n_boot=1000, seed=7)
    assert (a.did, a.lo, a.hi) == (b.did, b.lo, b.hi)


def test_naive_delta_helper_matches_treated_delta():
    treated, control = simulate_experiment(n_prompts=15, seed=6)
    res = difference_in_differences(treated, control, n_boot=500, seed=6)
    assert naive_delta(treated) == pytest.approx(res.naive_delta)


def test_summary_states_the_verdict():
    treated, control = simulate_experiment(true_effect=0.3, n_prompts=40, seed=8)
    res = difference_in_differences(treated, control, n_boot=1000, seed=8)
    text = res.summary()
    assert "causal uplift" in text and "background drift" in text
    assert ("distinguishable" in text)


def test_levers_reference_present():
    assert set(PROVEN_LEVERS) == {"quotation", "statistics", "cite_sources"}
