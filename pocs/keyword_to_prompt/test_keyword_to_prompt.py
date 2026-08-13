"""Offline tests for the keyword->prompt POC (Task R3). No keys, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "onboarding"))

from keyword_to_prompt import (  # noqa: E402
    classify_keyword,
    keyword_to_prompts,
    keywords_to_prompts,
    merge_keyword_prompts,
)
from onboarding import BrandProfile, Prompt  # noqa: E402

ACME = BrandProfile(
    name="Acme Board",
    category="project management tools",
    aliases=("Acme",),
    competitors=("Trellix",),
)


# --- classification -------------------------------------------------------- #
def test_plain_keyword_is_informational():
    assert classify_keyword("project management software") == ("informational", False)


def test_commercial_modifier_detected():
    assert classify_keyword("best project management software") == ("commercial", False)
    assert classify_keyword("crm pricing") == ("commercial", False)
    assert classify_keyword("trello vs asana") == ("commercial", False)


def test_branded_keyword_is_navigational():
    assert classify_keyword("acme board login", ACME) == ("navigational", True)


def test_branded_plus_modifier_is_commercial():
    intent, branded = classify_keyword("acme board pricing", ACME)
    assert (intent, branded) == ("commercial", True)


def test_modifier_matches_whole_token_only():
    # "buyer" should NOT trigger the "buy" commercial modifier
    assert classify_keyword("buyer personas guide") == ("informational", False)


# --- single keyword -> prompts --------------------------------------------- #
def test_keyword_to_prompts_labels_and_text():
    prompts = keyword_to_prompts("best crm", ACME)
    assert len(prompts) == 1
    p = prompts[0]
    assert isinstance(p, Prompt)
    assert p.intent == "commercial" and not p.branded
    assert "best crm" in p.text.lower()
    assert p.category == ACME.category  # inherits brand category when profile given


def test_keyword_category_falls_back_to_keyword_without_profile():
    p = keyword_to_prompts("note taking apps")[0]
    assert p.category == "note taking apps"


def test_max_variants_returns_multiple_frames():
    prompts = keyword_to_prompts("crm software", max_variants=3)
    assert len(prompts) == 3
    assert len({p.text for p in prompts}) == 3  # distinct frames


def test_empty_keyword_yields_nothing():
    assert keyword_to_prompts("   ") == []


def test_max_variants_must_be_positive():
    with pytest.raises(ValueError):
        keyword_to_prompts("crm", max_variants=0)


# --- merge / dedupe -------------------------------------------------------- #
def test_keywords_to_prompts_dedupes_identical_keywords():
    prompts = keywords_to_prompts(["crm software", "crm software"])
    assert len(prompts) == 1


def test_merge_preserves_existing_and_appends_new():
    existing = [Prompt("What is CRM software?", "informational", False, "crm")]
    merged = merge_keyword_prompts(existing, ["best crm", "crm software"])
    texts = [p.text for p in merged]
    # existing kept first
    assert texts[0] == "What is CRM software?"
    # "crm software" -> "What is crm software?" collides with existing (case/punct-insensitive)
    assert sum("crm software" in t.lower() for t in texts) == 1
    # "best crm" is new
    assert any("best crm" in t.lower() for t in texts)


def test_merge_dedupes_case_and_trailing_punctuation():
    existing = [Prompt("What is CRM?", "informational", False, "crm")]
    merged = merge_keyword_prompts(existing, ["crm"])
    assert len(merged) == 1  # "What is crm?" normalizes to the existing entry


def test_merged_prompts_are_all_prompt_objects_with_intent():
    merged = keywords_to_prompts(["best crm", "crm integrations", "hubspot pricing"])
    assert all(isinstance(p, Prompt) and p.intent for p in merged)
