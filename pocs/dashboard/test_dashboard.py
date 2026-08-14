"""Offline tests for the reporting dashboard POC (Task A2). No network, no keys.

Builds a small synthetic GeoReport dict fixture (same shape as `app/pipeline.py`
emits) and asserts the rendered HTML carries every honesty-first section: CI bars,
the mention-vs-citation gap callout, a distinguishability verdict, the methodology
caveats — plus an empty-reconciliation edge case.
"""

from __future__ import annotations

from dashboard import ci_bar_svg, render_dashboard


def _est(point: float, lo: float, hi: float, n: int = 50) -> dict:
    return {"point": point, "lo": lo, "hi": hi, "n": n, "confidence": 0.95}


def _report() -> dict:
    """A synthetic report mirroring the real Asana finding: mentioned ~a lot, cited ~0."""
    return {
        "brand": "Asana",
        "category": "project management software",
        "mode": "live",
        "generated_utc": "2026-08-14T04:55:30+00:00",
        "prompt_set": {
            "count": 10,
            "intents": {
                "informational": {"count": 8, "fraction": 0.8},
                "commercial": {"count": 1, "fraction": 0.1},
                "navigational": {"count": 1, "fraction": 0.1},
            },
            "skew": {"ok": True, "message": "OK: 1/10 prompts are branded (10% <= 30%)."},
        },
        "per_engine_metrics": {
            "openai": {
                "n_runs": 50,
                "mention": _est(0.82, 0.69, 0.90),
                "citation": _est(0.0, 0.0, 0.07),   # mentioned a lot, cites brand 0%
                "share_of_voice": _est(0.0, 0.0, 0.0, n=1),
                "position": {"n_cited": 0, "mean_rank": None, "mean_first_offset": 413.2},
            },
            "perplexity": {
                "n_runs": 50,
                "mention": _est(0.74, 0.60, 0.84),
                "citation": _est(0.40, 0.28, 0.54),  # actually cites the brand
                "share_of_voice": _est(0.875, 0.57, 1.0, n=4),
                "position": {"n_cited": 20, "mean_rank": 8.05, "mean_first_offset": 322.1},
            },
        },
        "reconciliation": {
            "overlap": {
                "mean_pairwise_jaccard": 0.127,
                "n_engines": 2,
                "pairwise_jaccard": {"openai|perplexity": 0.04},
                "per_engine_unique_domains": {"openai": 23, "perplexity": 81},
            },
            "divergence": [
                {"engine": "perplexity", "ecosystem": "reddit", "delta": 0.05},
            ],
            "methodology": {
                "generated_utc": "2026-08-14T04:55:30+00:00",
                "n_prompts": 10,
                "repeats_per_prompt": 5,
                "locale": "us",
                "domain_normalization": "host lower-cased, leading www. stripped",
                "engines": {"openai": "gpt-4o-mini", "perplexity": "sonar"},
                "access_method": {
                    "openai": "Responses API web_search tool",
                    "perplexity": "Sonar REST search_results[]",
                },
                "caveats": [
                    "Gemini grounding is a documented PROXY for Google AI Overviews.",
                    "Single-run scores are omitted by design; all rates carry CIs.",
                ],
            },
        },
        "spend": {
            "openai": {"spent": 1.41, "cap": 2.0},
            "perplexity": {"spent": 0.30, "cap": 2.0},
        },
        "notes": ["Locale-sensitive; holds only for the stated locale."],
        "target_domain": "asana.com",
        "prompts": [
            {"text": "What is the best project management software?",
             "intent": "informational", "category": "pm"},
            {"text": "Is Asana good for small teams?",
             "intent": "commercial", "category": "pm"},
        ],
        "top_domains": {
            "openai": [["techradar.com", 14], ["capterra.com", 8]],
            "perplexity": [["reddit.com", 70], ["asana.com", 30]],
        },
        "transcript": {
            "openai": [
                {"prompt_text": "What is the best project management software?",
                 "answer": "The best options include Asana, Trello and Monday.",
                 "citations": [
                     {"url": "https://www.techradar.com/best", "domain": "techradar.com",
                      "position": 1}]},
            ],
            "perplexity": [
                {"prompt_text": "Is Asana good for small teams?",
                 "answer": "Yes — Asana is widely recommended for small teams.",
                 "citations": [
                     {"url": "https://asana.com/product", "domain": "asana.com",
                      "position": 1}]},
            ],
        },
        "findings": [
            "openai mentions Asana in 82% of answers but cites asana.com in 0% of them "
            "— it recommends the brand without linking it.",
        ],
        "recommendations": [
            "openai never cites asana.com but does cite techradar.com (14) — pursue "
            "presence there (PR & listings, not on-site SEO).",
        ],
    }


# --- ci_bar_svg ------------------------------------------------------------- #
def test_ci_bar_svg_is_valid_svg_with_point_and_band():
    svg = ci_bar_svg(0.5, 0.3, 0.7, n=50, label="citation")
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "<rect" in svg      # the CI band
    assert "<circle" in svg    # the point estimate
    assert "50%" in svg        # the point value label
    assert "citation" in svg   # accessible label / tooltip


def test_ci_bar_svg_clamps_out_of_range_values():
    # a malformed estimate must never overflow the 0..1 track
    svg = ci_bar_svg(1.5, -0.2, 2.0)
    assert "<svg" in svg
    assert "100%" in svg       # point clamped to 1.0


# --- full document ---------------------------------------------------------- #
def test_render_is_standalone_html_document():
    html = render_dashboard(_report())
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in html
    # self-contained: no external asset links in the <head>/<style> (the only place a
    # network fetch could be triggered). Citation URLs shown as text in the <body> are fine.
    head = html[: html.index("</head>")]
    assert "http://" not in head
    assert "https://" not in head


def test_render_shows_brand_and_category():
    html = render_dashboard(_report())
    assert "Asana" in html
    assert "project management software" in html


def test_render_flags_synthetic_mode_prominently():
    rep = _report()
    rep["mode"] = "dry-run (synthetic)"
    html = render_dashboard(rep)
    assert "SYNTHETIC" in html
    assert "not a real measurement" in html


def test_live_mode_is_not_flagged_synthetic():
    html = render_dashboard(_report())  # mode == "live"
    assert "SYNTHETIC" not in html


def test_prompt_set_intents_and_skew_message():
    html = render_dashboard(_report())
    assert "informational" in html
    assert "OK: 1/10 prompts are branded" in html


def test_mention_vs_citation_gap_callout_highlights_the_finding():
    html = render_dashboard(_report())
    assert "Mention vs. citation gap" in html
    # openai mentions a lot but cites 0% -> flagged; perplexity cites -> not flagged
    assert "mentioned, not cited" in html
    assert "cites its own domain" in html


def test_reconciliation_overlap_and_unique_domains():
    html = render_dashboard(_report())
    assert "0.127" in html                 # mean pairwise Jaccard
    assert "over-indexes" in html          # divergence finding
    assert "reddit" in html


def test_distinguishability_renders_a_verdict():
    html = render_dashboard(_report())
    assert "distinguishability" in html.lower()
    # openai citation 0/50 vs perplexity 20/50 -> clearly distinguishable
    assert "distinguishable" in html
    assert "openai" in html and "perplexity" in html


def test_methodology_caveats_rendered_verbatim():
    html = render_dashboard(_report())
    assert "Methodology card" in html
    assert "PROXY for Google AI Overviews" in html
    assert "Single-run scores are omitted by design" in html
    assert "gpt-4o-mini" in html           # per-engine model in the access table


def test_notes_section_rendered():
    html = render_dashboard(_report())
    assert "Locale-sensitive" in html


# --- evidence + interpretation layer (Task A3) ------------------------------ #
def test_findings_section_renders_the_gap_finding():
    html = render_dashboard(_report())
    assert "Findings" in html
    assert "mentions Asana in 82% of answers but cites asana.com in 0%" in html


def test_recommendations_section_renders_named_domain():
    html = render_dashboard(_report())
    assert "Recommendations" in html
    assert "techradar.com" in html
    assert "not on-site SEO" in html


def test_prompts_used_section_lists_prompts_with_intent():
    html = render_dashboard(_report())
    assert "Prompts used" in html
    assert "What is the best project management software?" in html
    assert "commercial" in html  # an intent label


def test_top_domains_section_shows_domain_with_count_and_highlights_target():
    html = render_dashboard(_report())
    assert "Top cited domains per engine" in html
    assert "techradar.com" in html and ">14<" in html   # a domain with its count
    assert "reddit.com" in html and ">70<" in html
    assert "tdom-target" in html                          # target (asana.com) highlighted


def test_transcript_section_has_details_block_with_answer_and_citation_url():
    html = render_dashboard(_report())
    assert "Evidence" in html
    assert "<details>" in html and "<summary>" in html
    assert "The best options include Asana" in html      # a real answer
    assert "https://www.techradar.com/best" in html       # a citation URL (as text)


def test_evidence_sections_absent_when_data_missing():
    # a report without the A3 fields still renders (older reports)
    rep = _report()
    for key in ("findings", "recommendations", "prompts", "top_domains", "transcript"):
        rep.pop(key, None)
    html = render_dashboard(rep)
    assert "<!DOCTYPE html>" in html
    assert "<details>" not in html                    # no transcript
    assert "Top cited domains per engine" not in html  # section heading absent
    assert "Prompts used" not in html


# --- edge case: empty / missing reconciliation ------------------------------ #
def test_empty_reconciliation_is_handled_gracefully():
    rep = _report()
    rep["reconciliation"] = {}
    html = render_dashboard(rep)
    assert "Cross-engine reconciliation" in html
    assert "Not available" in html
    # methodology card also degrades gracefully when the card is absent
    assert "No methodology card" in html
    # core sections still render
    assert "Per-engine metrics" in html


def test_single_engine_has_no_distinguishability_pairs():
    rep = _report()
    rep["per_engine_metrics"].pop("perplexity")
    html = render_dashboard(rep)
    assert "Need ≥2 engines" in html


def test_missing_optional_fields_do_not_crash():
    minimal = {"brand": "X", "category": "c", "mode": "live",
               "generated_utc": "t", "prompt_set": {}, "per_engine_metrics": {}}
    html = render_dashboard(minimal)
    assert "<!DOCTYPE html>" in html
    assert "X" in html
    assert "<svg" in html or "no per-engine metrics" in html
