"""Offline tests for the reconciliation POC (Task O3). No keys, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metrics"))

from metrics import RunRecord  # noqa: E402
from reconcile import (  # noqa: E402
    DEFAULT_ACCESS_METHODS,
    build_methodology_card,
    cited_domain_sets,
    classify_source,
    ecosystem_divergence,
    ecosystem_profile,
    jaccard,
    overlap_report,
    per_engine_share_of_voice,
    reconcile,
)


# --- overlap math (O3.1) --------------------------------------------------- #
def test_jaccard_basic():
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a"}, set()) == 0.0


def test_cited_domain_sets_dedupes_and_lowercases():
    runs = {"openai": [RunRecord(0, "openai", "", ("Acme.com", "acme.com", "b.com"))]}
    assert cited_domain_sets(runs) == {"openai": {"acme.com", "b.com"}}


def test_overlap_report_pairwise_and_mean():
    runs = {
        "openai": [RunRecord(0, "openai", "", ("a.com", "b.com"))],
        "perplexity": [RunRecord(0, "perplexity", "", ("b.com", "c.com"))],
    }
    rep = overlap_report(runs)
    assert rep.n_engines == 2
    assert rep.per_engine_unique_domains == {"openai": 2, "perplexity": 2}
    assert rep.pairwise_jaccard["openai|perplexity"] == pytest.approx(1 / 3)
    assert rep.mean_pairwise_jaccard == pytest.approx(1 / 3)


def test_overlap_report_disjoint_engines_zero_overlap():
    runs = {
        "openai": [RunRecord(0, "openai", "", ("a.com",))],
        "gemini": [RunRecord(0, "gemini", "", ("z.com",))],
    }
    assert overlap_report(runs).mean_pairwise_jaccard == 0.0


# --- per-engine SoV under one normalization (O3.2) ------------------------- #
def test_per_engine_sov_uses_same_estimator():
    runs = {
        "openai": [RunRecord(i, "openai", "", ("acme.com", "rival.com")) for i in range(4)],
        "perplexity": [RunRecord(i, "perplexity", "", ("acme.com",)) for i in range(4)],
    }
    sov = per_engine_share_of_voice(runs, ["acme.com"], ["rival.com"])
    assert sov["openai"].point == pytest.approx(0.5)
    assert sov["perplexity"].point == pytest.approx(1.0)
    # each carries an interval
    assert sov["openai"].lo <= sov["openai"].point <= sov["openai"].hi


# --- ecosystem classification + divergence (O3.3) -------------------------- #
def test_classify_source_buckets_and_subdomains():
    assert classify_source("reddit.com") == "reddit"
    assert classify_source("old.reddit.com") == "reddit"
    assert classify_source("en.wikipedia.org") == "wikipedia"
    assert classify_source("youtu.be") == "youtube"
    assert classify_source("somevendor.com") == "other"
    assert classify_source(None) == "other"


def test_ecosystem_profile_fractions_sum_to_one():
    runs = {"openai": [RunRecord(0, "openai", "", ("reddit.com", "acme.com"))]}
    prof = ecosystem_profile(runs)["openai"]
    assert prof["reddit"] == pytest.approx(0.5)
    assert prof["other"] == pytest.approx(0.5)
    assert sum(prof.values()) == pytest.approx(1.0)


def test_ecosystem_profile_empty_engine_all_zero():
    runs = {"gemini": [RunRecord(0, "gemini", "", ())]}
    prof = ecosystem_profile(runs)["gemini"]
    assert sum(prof.values()) == 0.0


def test_ecosystem_divergence_flags_reddit_heavy_engine():
    # perplexity leans hard on reddit; openai does not
    runs = {
        "openai": [RunRecord(0, "openai", "", ("acme.com", "vendor.com"))],
        "perplexity": [RunRecord(0, "perplexity", "", ("reddit.com", "reddit.com"))],
    }
    prof = ecosystem_profile(runs)
    findings = ecosystem_divergence(prof, min_delta=0.15)
    reddit = [f for f in findings if f.ecosystem == "reddit"]
    assert reddit and reddit[0].engine == "perplexity"
    assert reddit[0].delta > 0.15


def test_divergence_needs_two_engines():
    runs = {"openai": [RunRecord(0, "openai", "", ("reddit.com",))]}
    assert ecosystem_divergence(ecosystem_profile(runs)) == []


# --- methodology card (O3.4) ----------------------------------------------- #
def test_methodology_card_is_deterministic_and_serializable():
    card = build_methodology_card(
        {"openai": "gpt-4o-mini", "perplexity": "sonar"},
        generated_utc="2026-08-13T00:00:00+00:00", n_prompts=5, repeats_per_prompt=3,
    )
    d = card.to_dict()
    assert d["engines"]["openai"] == "gpt-4o-mini"
    assert d["access_method"]["openai"] == DEFAULT_ACCESS_METHODS["openai"]
    assert d["n_prompts"] == 5 and d["repeats_per_prompt"] == 3
    # default caveats present; JSON + markdown render
    assert any("locale" in c.lower() for c in d["caveats"])
    assert "Methodology card" in card.to_markdown()
    assert card.to_json() == build_methodology_card(
        {"openai": "gpt-4o-mini", "perplexity": "sonar"},
        generated_utc="2026-08-13T00:00:00+00:00", n_prompts=5, repeats_per_prompt=3,
    ).to_json()


def test_methodology_card_custom_caveats_override():
    card = build_methodology_card(
        {"openai": "gpt-4o-mini"}, generated_utc="t", n_prompts=1,
        repeats_per_prompt=1, caveats=["only one"],
    )
    assert card.caveats == ["only one"]


# --- full bundle ----------------------------------------------------------- #
def test_reconcile_bundle_end_to_end():
    runs = {
        "openai": [RunRecord(i, "openai", "", ("acme.com", "rival.com")) for i in range(3)],
        "perplexity": [RunRecord(i, "perplexity", "", ("acme.com", "reddit.com"))
                       for i in range(3)],
    }
    report = reconcile(
        runs, target_domains=["acme.com"], competitor_domains=["rival.com"],
        models={"openai": "gpt-4o-mini", "perplexity": "sonar"},
        generated_utc="2026-08-13T00:00:00+00:00", n_prompts=3, repeats_per_prompt=1,
    )
    d = report.to_dict()
    assert set(d) == {"overlap", "share_of_voice", "ecosystem_profile",
                      "divergence", "methodology"}
    assert d["overlap"]["n_engines"] == 2
    assert "openai" in d["share_of_voice"]
