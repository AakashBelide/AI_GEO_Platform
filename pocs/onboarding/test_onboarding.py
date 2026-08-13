"""Offline tests for the onboarding POC (Task R1). No keys, no network."""

from __future__ import annotations

import pytest
from onboarding import (
    DEFAULT_MAX_BRANDED_RATIO,
    BrandProfile,
    Prompt,
    branded_ratio,
    build_prompt_set,
    generate_prompts,
    intent_distribution,
    paraphrase,
    skew_check,
)

ACME = BrandProfile(
    name="Acme Board",
    category="project management tools",
    domain="acme.example",
    aliases=("Acme", "AcmeBoard"),
    competitors=("Trellix", "Mondayish", "ClickIt"),
    use_cases=("remote teams", "agencies"),
)


# --- profile validation ---------------------------------------------------- #
def test_profile_requires_name_and_category():
    with pytest.raises(ValueError):
        BrandProfile(name="", category="x")
    with pytest.raises(ValueError):
        BrandProfile(name="X", category="  ")


def test_all_names_dedupes_and_keeps_order():
    p = BrandProfile(name="Acme", category="c", aliases=("Acme", "ACME2"))
    assert p.all_names() == ["Acme", "ACME2"]


# --- generation: size + intent distribution -------------------------------- #
def test_generate_hits_exact_total():
    prompts = generate_prompts(ACME, n_total=30)
    assert len(prompts) == 30


def test_intent_distribution_matches_80_10_10():
    prompts = generate_prompts(ACME, n_total=30)
    dist = intent_distribution(prompts)
    # 80/10/10 of 30 => 24 / 3 / 3
    assert dist["informational"]["count"] == 24
    assert dist["commercial"]["count"] == 3
    assert dist["navigational"]["count"] == 3
    assert dist["informational"]["fraction"] == pytest.approx(0.8)


def test_intent_mix_must_sum_to_one():
    with pytest.raises(ValueError):
        generate_prompts(ACME, intent_mix={"informational": 0.5, "commercial": 0.2,
                                            "navigational": 0.2})


def test_n_total_must_be_positive():
    with pytest.raises(ValueError):
        generate_prompts(ACME, n_total=0)


def test_largest_remainder_sums_to_total_for_awkward_n():
    # 17 with 80/10/10 must still sum to exactly 17
    prompts = generate_prompts(ACME, n_total=17)
    assert len(prompts) == 17
    dist = intent_distribution(prompts)
    assert sum(int(dist[i]["count"]) for i in dist) == 17


# --- branded skew guard (the honesty layer) -------------------------------- #
def test_informational_prompts_are_unbranded():
    prompts = generate_prompts(ACME, n_total=30)
    info = [p for p in prompts if p.intent == "informational"]
    assert all(not p.branded for p in info)
    # and none of them literally name the brand
    assert all("acme" not in p.text.lower() for p in info)


def test_navigational_prompts_are_branded_and_name_brand():
    prompts = generate_prompts(ACME, n_total=30)
    nav = [p for p in prompts if p.intent == "navigational"]
    assert nav and all(p.branded for p in nav)
    assert all("acme" in p.text.lower() for p in nav)


def test_default_set_passes_skew_check():
    prompts = generate_prompts(ACME, n_total=30)
    report = skew_check(prompts)
    assert report.ok
    assert report.branded_ratio <= DEFAULT_MAX_BRANDED_RATIO


def test_all_branded_set_fails_skew_check():
    branded = [Prompt(f"Acme review {i}", "navigational", True, "c") for i in range(10)]
    report = skew_check(branded)
    assert not report.ok
    assert "SKEW" in report.message
    assert report.branded_ratio == 1.0


def test_branded_ratio_empty_is_zero():
    assert branded_ratio([]) == 0.0


# --- paraphrase variants --------------------------------------------------- #
def test_paraphrase_returns_n_plus_one_and_keeps_original_first():
    base = Prompt("What is the best project management tool?", "informational", False, "c")
    variants = paraphrase(base, n=3)
    assert len(variants) == 4
    assert variants[0].text == base.text
    assert all(v.paraphrase_of == base.text for v in variants)
    assert all(v.intent == "informational" and not v.branded for v in variants)


def test_paraphrase_zero_returns_only_original():
    base = Prompt("What is X?", "informational", False, "c")
    assert [p.text for p in paraphrase(base, n=0)] == ["What is X?"]


def test_paraphrase_negative_raises():
    base = Prompt("What is X?", "informational", False, "c")
    with pytest.raises(ValueError):
        paraphrase(base, n=-1)


# --- bundle ---------------------------------------------------------------- #
def test_build_prompt_set_bundles_guards():
    ps = build_prompt_set(ACME, n_total=30)
    assert ps.skew.ok
    assert ps.intents["informational"]["count"] == 24
    assert len(ps.prompts) == 30
