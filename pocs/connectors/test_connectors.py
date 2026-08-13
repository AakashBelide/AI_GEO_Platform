"""Offline tests for the connectors (Task F3). No keys, no network — fixtures only."""

from __future__ import annotations

import pytest
from budget import BudgetExceeded, CostLedger
from connectors import (
    Engine,
    EngineResponse,
    normalize_domain,
    parse_anthropic,
    parse_gemini,
    parse_openai,
    parse_perplexity,
    usage_from_raw,
)

# --- representative payload fixtures (shapes the SDKs / REST APIs return) --- #
OPENAI_RAW = {
    "output": [{"type": "message", "content": [{
        "type": "output_text",
        "text": "HubSpot and Salesforce are top CRMs.",
        "annotations": [
            {"type": "url_citation", "url": "https://www.hubspot.com/", "title": "HubSpot"},
            {"type": "url_citation", "url": "https://g2.com/crm", "title": "G2"},
        ]}]}],
    "usage": {"input_tokens": 1200, "output_tokens": 300},
}
PERPLEXITY_RAW = {
    "choices": [{"message": {"content": "HubSpot is popular."}}],
    "search_results": [
        {"title": "HubSpot", "url": "https://hubspot.com"},
        {"title": "Reddit", "url": "https://reddit.com/r/crm"},
    ],
    "usage": {"prompt_tokens": 500, "completion_tokens": 150},
}
GEMINI_RAW = {  # snake_case, as google-genai's model_dump() produces
    "candidates": [{
        "content": {"parts": [{"text": "Top CRMs include HubSpot."}]},
        "grounding_metadata": {"grounding_chunks": [
            {"web": {"uri": "https://hubspot.com", "title": "hubspot.com"}}]},
    }],
    "usage_metadata": {"prompt_token_count": 800, "candidates_token_count": 200},
}
ANTHROPIC_RAW = {
    "content": [
        {"type": "text", "text": "Let me search. "},
        {"type": "web_search_tool_result", "content": [
            {"type": "web_search_result", "url": "https://hubspot.com", "title": "HubSpot"},
            {"type": "web_search_result", "url": "https://salesforce.com", "title": "Salesforce"},
        ]},
        {"type": "text", "text": "HubSpot and Salesforce lead."},
    ],
    "usage": {"input_tokens": 1000, "output_tokens": 250},
}


def test_normalize_domain():
    assert normalize_domain("https://www.HubSpot.com/page") == "hubspot.com"
    assert normalize_domain("https://g2.com/crm") == "g2.com"
    assert normalize_domain("reddit.com/r/x") == "reddit.com"
    assert normalize_domain(None) is None


def test_parse_openai():
    answer, cites = parse_openai(OPENAI_RAW)
    assert "top CRMs" in answer
    assert [c.domain for c in cites] == ["hubspot.com", "g2.com"]
    assert [c.position for c in cites] == [1, 2]


def test_parse_perplexity_prefers_search_results():
    answer, cites = parse_perplexity(PERPLEXITY_RAW)
    assert answer == "HubSpot is popular."
    assert [c.domain for c in cites] == ["hubspot.com", "reddit.com"]


def test_parse_perplexity_falls_back_to_citations_list():
    raw = {"choices": [{"message": {"content": "x"}}],
           "citations": ["https://a.com", "https://b.com/p"]}
    _, cites = parse_perplexity(raw)
    assert [c.domain for c in cites] == ["a.com", "b.com"]


def test_parse_gemini_snake_case():
    answer, cites = parse_gemini(GEMINI_RAW)
    assert "HubSpot" in answer
    assert [c.domain for c in cites] == ["hubspot.com"]


def test_parse_gemini_handles_camel_case_too():
    raw = {"candidates": [{"content": {"parts": [{"text": "hi"}]},
           "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://z.com"}}]}}]}
    _, cites = parse_gemini(raw)
    assert [c.domain for c in cites] == ["z.com"]


def test_parse_anthropic():
    answer, cites = parse_anthropic(ANTHROPIC_RAW)
    assert "HubSpot and Salesforce lead." in answer
    assert [c.domain for c in cites] == ["hubspot.com", "salesforce.com"]


@pytest.mark.parametrize("provider,raw,expected", [
    ("openai", OPENAI_RAW, (1200, 300)),
    ("perplexity", PERPLEXITY_RAW, (500, 150)),
    ("gemini", GEMINI_RAW, (800, 200)),
    ("anthropic", ANTHROPIC_RAW, (1000, 250)),
])
def test_usage_from_raw(provider, raw, expected):
    assert usage_from_raw(provider, raw) == expected


# --- budget-gated flow, exercised with a fake engine (no network) --- #
class FakeEngine(Engine):
    called: bool = False

    def _raw_call(self, prompt: str) -> dict:
        object.__setattr__(self, "called", True)
        return OPENAI_RAW


def test_query_flow_records_cost_and_caches(tmp_path):
    ledger = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    eng = FakeEngine("openai", "gpt-4o-mini", ledger, cache_dir=tmp_path / "cache")
    resp = eng.query("best crm for startups", run_index=0)
    assert isinstance(resp, EngineResponse)
    assert resp.domains == ["hubspot.com", "g2.com"]
    assert eng.called is True
    assert ledger.spent("openai") > 0                      # cost recorded
    # raw payload cached to disk (so re-analysis never re-calls)
    cached = list((tmp_path / "cache" / "openai").glob("*.json"))
    assert len(cached) == 1


def test_query_blocked_when_over_budget_never_calls_network(tmp_path):
    ledger = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    ledger.record("openai", 1.999)  # essentially exhausted
    eng = FakeEngine("openai", "gpt-4o-mini", ledger, cache_dir=tmp_path / "cache")
    with pytest.raises(BudgetExceeded):
        eng.query("a very long prompt " * 50)
    assert eng.called is False  # guard tripped BEFORE any network call
