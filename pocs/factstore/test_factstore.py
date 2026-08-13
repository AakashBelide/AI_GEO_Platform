"""Offline tests for the append-only fact store (Task F2). In-memory SQLite."""

from __future__ import annotations

import pytest
from factstore import FactStore


@pytest.fixture()
def store():
    s = FactStore(":memory:")
    yield s
    s.close()


def test_prompt_run_roundtrip(store):
    pid = store.add_prompt("best crm for startups", intent="commercial", category="saas")
    store.add_run(pid, engine="openai", model="gpt-4o-mini", run_index=0,
                  raw_response={"foo": "bar"}, answer_text="HubSpot is popular.",
                  est_cost_usd=0.012)
    runs = store.runs_for_prompt(pid)
    assert len(runs) == 1
    assert runs[0]["engine"] == "openai"
    assert runs[0]["answer_text"] == "HubSpot is popular."
    assert store.total_est_cost() == pytest.approx(0.012)


def test_runs_are_append_only_across_repeats(store):
    pid = store.add_prompt("q")
    for i in range(5):
        store.add_run(pid, engine="perplexity", model="sonar", run_index=i)
    assert store.count("runs") == 5
    # each repeat is a distinct immutable row
    idxs = sorted(r["run_index"] for r in store.runs_for_prompt(pid))
    assert idxs == [0, 1, 2, 3, 4]


def test_citations_and_brand_rate(store):
    pid = store.add_prompt("best crm")
    # 3 runs: 2 cite the target brand, 1 does not
    for i, cites_brand in enumerate([True, True, False]):
        rid = store.add_run(pid, engine="openai", model="gpt-4o-mini", run_index=i)
        store.add_citation(rid, cited_url="https://hubspot.com", domain="hubspot.com",
                           position=1, is_target_brand=cites_brand)
        store.add_citation(rid, cited_url="https://rival.com", domain="rival.com",
                           position=2, is_target_brand=False)
    hits, total = store.brand_citation_rate(pid, "openai")
    assert (hits, total) == (2, 3)


def test_mentions(store):
    pid = store.add_prompt("q")
    rid = store.add_run(pid, engine="gemini", model="gemini-2.5-flash", run_index=0)
    store.add_mention(rid, entity="HubSpot", is_target_brand=True, sentiment="positive",
                      char_offset=10)
    assert store.count("mentions") == 1


def test_content_score_upsert(store):
    store.upsert_content_score("https://x.com/page", stat_density=3.2, quote_count=2,
                               citation_count=5, heading_structure_score=0.8,
                               readability=1.0, has_schema=1)
    store.upsert_content_score("https://x.com/page", stat_density=4.0)  # replace
    assert store.count("content_scores") == 1
    row = store.conn.execute(
        "SELECT stat_density FROM content_scores WHERE page_url=?",
        ("https://x.com/page",)).fetchone()
    assert row["stat_density"] == pytest.approx(4.0)


def test_count_rejects_unknown_table(store):
    with pytest.raises(ValueError):
        store.count("robert'); DROP TABLE runs;--")


def test_raw_response_preserved_as_json(store):
    pid = store.add_prompt("q")
    payload = {"citations": [{"url": "https://a.com"}], "nested": {"x": [1, 2, 3]}}
    rid = store.add_run(pid, engine="anthropic", model="claude-haiku-4-5", run_index=0,
                        raw_response=payload)
    import json
    stored = store.conn.execute(
        "SELECT raw_response FROM runs WHERE run_id=?", (rid,)).fetchone()[0]
    assert json.loads(stored) == payload
