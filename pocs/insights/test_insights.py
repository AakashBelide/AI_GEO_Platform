"""Offline tests for the interpretation layer (Task A3). No network, no keys, no LLM.

Builds small report-dict fixtures (same shape `app/pipeline.py` emits) and asserts the
findings/recommendations name the right engines / domains / verdicts, surface the
mention-vs-citation gap, flag a not-distinguishable pair, and degrade on edge cases.
"""

from __future__ import annotations

from insights import (
    generate_findings,
    generate_recommendations,
    top_domains,
)


def _est(point: float, lo: float, hi: float, n: int = 50) -> dict:
    return {"point": point, "lo": lo, "hi": hi, "n": n, "confidence": 0.95}


def _report() -> dict:
    """Mirrors the real Asana finding: OpenAI/Anthropic mention ~80%, cite asana.com 0%."""
    return {
        "brand": "Asana",
        "category": "project management software",
        "mode": "live",
        "target_domain": "asana.com",
        "per_engine_metrics": {
            "openai": {
                "n_runs": 50,
                "mention": _est(0.82, 0.69, 0.90),
                "citation": _est(0.0, 0.0, 0.07),
                "share_of_voice": _est(0.0, 0.0, 0.0, n=1),
            },
            "anthropic": {
                "n_runs": 50,
                "mention": _est(0.80, 0.67, 0.89),
                "citation": _est(0.0, 0.0, 0.07),
                "share_of_voice": _est(0.0, 0.0, 0.0, n=2),
            },
            "gemini": {
                "n_runs": 50,
                "mention": _est(0.60, 0.46, 0.72),
                "citation": _est(0.14, 0.07, 0.26),
                "share_of_voice": _est(0.96, 0.25, 1.0, n=4),
            },
            "perplexity": {
                "n_runs": 50,
                "mention": _est(0.74, 0.60, 0.84),
                "citation": _est(0.40, 0.28, 0.54),
                "share_of_voice": _est(0.88, 0.57, 1.0, n=4),
            },
        },
        "reconciliation": {
            "overlap": {"mean_pairwise_jaccard": 0.127, "n_engines": 4},
            "divergence": [{"engine": "perplexity", "ecosystem": "reddit", "delta": 0.18}],
        },
        "top_domains": {
            "openai": [("techradar.com", 14), ("kanbanchi.com", 10), ("smartsheet.com", 5)],
            "anthropic": [("thedigitalprojectmanager.com", 23), ("capterra.com", 16)],
            "gemini": [("project-management.com", 32), ("asana.com", 25)],
            "perplexity": [("reddit.com", 70), ("thedigitalprojectmanager.com", 50)],
        },
    }


# --- top_domains ------------------------------------------------------------ #
def test_top_domains_counts_and_orders():
    cbe = {"openai": ["techradar.com", "TechRadar.com", "capterra.com", ".techradar.com"]}
    td = top_domains(cbe, k=10)
    assert td["openai"][0] == ("techradar.com", 3)  # case + leading-dot collapsed
    assert ("capterra.com", 1) in td["openai"]


def test_top_domains_respects_k():
    cbe = {"e": ["a.com", "a.com", "b.com", "c.com"]}
    assert len(top_domains(cbe, k=2)["e"]) == 2


# --- findings --------------------------------------------------------------- #
def test_findings_surface_mention_citation_gap_by_name():
    f = generate_findings(_report())
    assert any("openai" in x and "82%" in x and "asana.com" in x and "0%" in x for x in f)
    assert any("anthropic" in x and "0%" in x for x in f)


def test_findings_split_citers_from_non_citers():
    f = generate_findings(_report())
    blob = " ".join(f)
    assert "cite asana.com" in blob
    # gemini & perplexity cite; openai & anthropic do not
    assert "gemini" in blob and "perplexity" in blob
    assert "never do" in blob


def test_findings_report_overlap_and_portability():
    f = generate_findings(_report())
    assert any("0.13" in x and "not portable" in x for x in f)


def test_findings_name_most_cited_category_domains():
    f = generate_findings(_report())
    assert any("reddit.com" in x and "roundups" in x for x in f)


def test_findings_flag_not_distinguishable_pair():
    f = generate_findings(_report())
    # openai 0/50 vs anthropic 0/50 -> within noise
    assert any(
        "anthropic" in x and "openai" in x and "NOT statistically distinguishable" in x
        for x in f
    )


def test_findings_include_sov_underpower_caveat():
    f = generate_findings(_report())
    assert any("under-powered" in x and "SoV" in x for x in f)


def test_findings_include_divergence_when_flagged():
    f = generate_findings(_report())
    assert any("over-indexes" in x and "reddit" in x for x in f)


# --- recommendations -------------------------------------------------------- #
def test_recommendations_name_third_party_domains_for_non_citers():
    r = generate_recommendations(_report())
    blob = " ".join(r)
    assert "techradar.com" in blob or "thedigitalprojectmanager.com" in blob
    assert "PR & listings" in blob
    assert "not on-site SEO" in blob


def test_recommendations_keep_cited_pages_fresh_for_citers():
    r = generate_recommendations(_report())
    assert any("already cite asana.com" in x and "fresh" in x for x in r)


def test_recommendations_community_presence_for_reddit_over_index():
    r = generate_recommendations(_report())
    assert any("reddit.com" in x and "verify" in x for x in r)


def test_recommendations_enlarge_prompt_set_when_sov_underpowered():
    r = generate_recommendations(_report())
    assert any("enlarge" in x and "prompt set" in x for x in r)


def test_recommendations_always_hedge_causality():
    r = generate_recommendations(_report())
    assert any("Task O2" in x for x in r)


def test_every_recommendation_references_something_concrete():
    r = [x for x in generate_recommendations(_report()) if "Task O2" not in x]
    # each actionable rec should name an engine or a domain
    for rec in r:
        assert any(tok in rec for tok in
                   ("openai", "anthropic", "gemini", "perplexity", ".com", "SoV"))


# --- edge cases ------------------------------------------------------------- #
def test_synthetic_mode_prepends_illustrative_note():
    rep = _report()
    rep["mode"] = "dry-run (synthetic)"
    f = generate_findings(rep)
    r = generate_recommendations(rep)
    assert f[0].startswith("ILLUSTRATIVE ONLY")
    assert r[0].startswith("ILLUSTRATIVE ONLY")


def test_empty_reconciliation_does_not_crash():
    rep = _report()
    rep["reconciliation"] = {}
    f = generate_findings(rep)
    # gap + citer split still present; no overlap/divergence lines
    assert f
    assert not any("Jaccard" in x for x in f)


def test_single_engine_has_no_distinguishability_or_split():
    rep = _report()
    rep["per_engine_metrics"] = {"openai": rep["per_engine_metrics"]["openai"]}
    rep["top_domains"] = {"openai": rep["top_domains"]["openai"]}
    f = generate_findings(rep)
    assert not any("distinguishable" in x for x in f)
    assert not any("never do on this run" in x for x in f)


def test_missing_target_domain_falls_back_to_generic_phrase():
    rep = _report()
    rep.pop("target_domain")
    f = generate_findings(rep)
    assert any("its own domain" in x for x in f)


def test_no_findings_recommendations_reference_fabricated_numbers():
    # determinism: same input -> identical output
    assert generate_findings(_report()) == generate_findings(_report())
    assert generate_recommendations(_report()) == generate_recommendations(_report())
