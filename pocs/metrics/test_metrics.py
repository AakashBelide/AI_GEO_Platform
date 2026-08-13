"""Offline tests for the metrics POC (Task R2). No keys, no network — synthetic runs."""

from __future__ import annotations

import pytest
from metrics import (
    RunRecord,
    citation_estimate,
    cohen_kappa,
    compute_brand_metrics,
    detect_mention,
    domain_matches,
    judge_sentiments,
    mention_estimate,
    position_summary,
    sentiment_kappa_report,
    share_of_voice,
)


# --- domain matching ------------------------------------------------------- #
def test_domain_exact_and_subdomain_match():
    assert domain_matches("acme.com", ["acme.com"])
    assert domain_matches("blog.acme.com", ["acme.com"])
    assert not domain_matches("acme.com", ["notacme.com"])
    assert not domain_matches("fakeacme.com", ["acme.com"])  # not a subdomain
    assert not domain_matches(None, ["acme.com"])


# --- mention detection ----------------------------------------------------- #
def test_detect_mention_word_boundary_and_offset():
    found, off = detect_mention("The best tool is Acme Board, hands down.", ["Acme Board"])
    assert found and off == 17


def test_detect_mention_is_case_insensitive():
    found, _ = detect_mention("i like acme", ["Acme"])
    assert found


def test_detect_mention_no_substring_false_positive():
    # "Acme" must not match inside "Acmentor"
    found, _ = detect_mention("Acmentor is unrelated", ["Acme"])
    assert not found


def test_detect_mention_alias_with_dot():
    found, _ = detect_mention("Try Monday.com today", ["Monday.com"])
    assert found


# --- rate metrics carry CIs ------------------------------------------------ #
def _runs(mention_flags, cite_flags, target="acme.com", prompt_ids=None):
    recs = []
    for i, (m, c) in enumerate(zip(mention_flags, cite_flags, strict=True)):
        pid = prompt_ids[i] if prompt_ids else 0
        recs.append(RunRecord(
            prompt_id=pid,
            engine="openai",
            answer_text="Acme is great." if m else "Some other tool.",
            cited_domains=(target,) if c else ("other.com",),
        ))
    return recs


def test_mention_estimate_point_and_interval():
    recs = _runs([1, 1, 1, 0], [0, 0, 0, 0])  # 3/4 mention
    est = mention_estimate(recs, ["Acme"])
    assert est.point == pytest.approx(0.75)
    assert est.n == 4
    assert est.lo < est.point < est.hi  # a real interval, not a point


def test_citation_estimate_counts_target_domain():
    recs = _runs([0, 0, 0, 0], [1, 1, 0, 0])  # 2/4 cite target
    est = citation_estimate(recs, ["acme.com"])
    assert est.point == pytest.approx(0.5)
    assert est.n == 4


def test_empty_records_give_maximal_uncertainty():
    est = mention_estimate([], ["Acme"])
    assert est.n == 0
    assert (est.lo, est.hi) == (0.0, 1.0)


# --- share of voice (clustered) -------------------------------------------- #
def test_share_of_voice_half_when_target_equals_competitor():
    # 4 prompts, each cites target once and competitor once -> SoV 0.5
    recs = []
    for pid in range(4):
        recs.append(RunRecord(pid, "openai", "", ("acme.com", "trellix.com")))
    est = share_of_voice(recs, ["acme.com"], ["trellix.com"], n_boot=500)
    assert est.point == pytest.approx(0.5)
    assert 0.0 <= est.lo <= est.point <= est.hi <= 1.0


def test_share_of_voice_ignores_out_of_universe_domains():
    recs = [RunRecord(0, "openai", "", ("acme.com", "randomblog.com"))]
    est = share_of_voice(recs, ["acme.com"], ["trellix.com"], n_boot=200)
    assert est.point == pytest.approx(1.0)  # only acme is in-universe


# --- position -------------------------------------------------------------- #
def test_position_summary_rank_and_offset():
    recs = [
        RunRecord(0, "openai", "Acme leads here.", ("trellix.com", "acme.com")),  # rank 2
        RunRecord(1, "openai", "First up, Acme.", ("acme.com",)),                 # rank 1
    ]
    ps = position_summary(recs, ["acme.com"], aliases=["Acme"])
    assert ps.n_cited == 2
    assert ps.mean_rank == pytest.approx(1.5)
    assert ps.mean_first_offset is not None


def test_position_summary_none_when_never_cited():
    recs = [RunRecord(0, "openai", "no brand", ("other.com",))]
    ps = position_summary(recs, ["acme.com"])
    assert ps.n_cited == 0 and ps.mean_rank is None


# --- sentiment: Cohen's kappa --------------------------------------------- #
def test_cohen_kappa_perfect_agreement():
    a = ["positive", "neutral", "negative", "positive"]
    assert cohen_kappa(a, a) == pytest.approx(1.0)


def test_cohen_kappa_chance_level_is_zero_ish():
    # independent-ish labels -> kappa near 0
    a = ["positive", "negative", "positive", "negative"]
    b = ["positive", "positive", "negative", "negative"]
    k = cohen_kappa(a, b)
    assert -0.5 <= k <= 0.5


def test_cohen_kappa_length_mismatch_raises():
    with pytest.raises(ValueError):
        cohen_kappa(["positive"], ["positive", "neutral"])


def test_cohen_kappa_all_same_single_category():
    a = ["neutral", "neutral", "neutral"]
    assert cohen_kappa(a, a) == pytest.approx(1.0)


def test_sentiment_kappa_report_trustworthy_flag():
    gold = ["positive", "positive", "neutral", "negative", "neutral"]
    good = list(gold)
    rep = sentiment_kappa_report(gold, good)
    assert rep.trustworthy and rep.kappa == pytest.approx(1.0)

    bad = ["negative", "negative", "negative", "positive", "positive"]
    rep2 = sentiment_kappa_report(gold, bad)
    assert not rep2.trustworthy


# --- injectable judge ------------------------------------------------------ #
def test_judge_sentiments_uses_injected_callable():
    recs = [RunRecord(0, "openai", "Acme is excellent"),
            RunRecord(1, "openai", "Acme is terrible")]

    def stub(text, brand):
        return "positive" if "excellent" in text else "negative"

    assert judge_sentiments(recs, "Acme", stub) == ["positive", "negative"]


def test_judge_rejects_invalid_label():
    recs = [RunRecord(0, "openai", "x")]
    with pytest.raises(ValueError):
        judge_sentiments(recs, "Acme", lambda t, b: "meh")


# --- bundle ---------------------------------------------------------------- #
def test_compute_brand_metrics_bundle():
    recs = []
    for pid in range(5):
        recs.append(RunRecord(pid, "openai", "Acme is good.", ("acme.com", "trellix.com")))
    m = compute_brand_metrics(
        recs, aliases=["Acme"], target_domains=["acme.com"],
        competitor_domains=["trellix.com"], engine="openai",
    )
    assert m.n_runs == 5
    assert m.mention.point == pytest.approx(1.0)
    assert m.citation.point == pytest.approx(1.0)
    assert m.share_of_voice.point == pytest.approx(0.5)
    assert m.position.n_cited == 5
