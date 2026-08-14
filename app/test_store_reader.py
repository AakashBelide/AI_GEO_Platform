"""Offline tests for the fact-store evidence reader (Task A3).

Writes a tiny temp FactStore (reusing `pocs/factstore`), inserts a couple prompts / runs /
citations, and asserts `read_evidence` reconstructs the expected shape. No network, no keys.
"""

from __future__ import annotations

import _paths  # noqa: F401  (side effect: put pocs/* on sys.path)
from factstore import FactStore
from store_reader import read_evidence


def _seed(path: str) -> None:
    s = FactStore(path)
    p1 = s.add_prompt("best pm software?", intent="informational", category="pm")
    p2 = s.add_prompt("asana vs monday?", intent="commercial", category="pm")
    # openai: first run cites a third party, not the brand
    r = s.add_run(p1, engine="openai", model="gpt-4o-mini", run_index=0,
                  answer_text="Asana is popular. " * 60)  # long -> truncation
    s.add_citation(r, cited_url="https://techradar.com/best", domain="techradar.com",
                   position=1, is_target_brand=False)
    s.add_run(p1, engine="openai", model="gpt-4o-mini", run_index=1,
              answer_text="second run, ignored as representative")
    # perplexity: cites the brand's own domain (+ a subdomain)
    r2 = s.add_run(p2, engine="perplexity", model="sonar", run_index=0, answer_text="Try Asana.")
    s.add_citation(r2, cited_url="https://asana.com/product", domain="asana.com",
                   position=1, is_target_brand=True)
    s.add_citation(r2, cited_url="https://help.asana.com/x", domain="help.asana.com",
                   position=2, is_target_brand=True)
    s.close()


def test_read_evidence_shape(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    _seed(db)
    ev = read_evidence(db)

    assert set(ev) == {"prompts", "transcript", "citations_by_engine", "target_domain"}
    # prompts ordered, with intent/category
    assert [p["text"] for p in ev["prompts"]] == ["best pm software?", "asana vs monday?"]
    assert ev["prompts"][0]["intent"] == "informational"


def test_transcript_picks_first_run_and_truncates(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    _seed(db)
    ev = read_evidence(db)
    tr = ev["transcript"]
    assert set(tr) == {"openai", "perplexity"}
    # openai has one prompt with runs; representative = the FIRST run's text
    openai_sample = tr["openai"][0]
    assert openai_sample["prompt_text"] == "best pm software?"
    assert "second run" not in openai_sample["answer"]      # not the second run
    assert len(openai_sample["answer"]) <= 700               # truncated


def test_transcript_citations_have_url_domain_position(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    _seed(db)
    ev = read_evidence(db)
    cites = ev["transcript"]["perplexity"][0]["citations"]
    assert cites[0] == {"url": "https://asana.com/product", "domain": "asana.com", "position": 1}
    assert cites[1]["domain"] == "help.asana.com"


def test_citations_by_engine_lists_every_domain(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    _seed(db)
    ev = read_evidence(db)
    assert ev["citations_by_engine"]["openai"] == ["techradar.com"]
    assert sorted(ev["citations_by_engine"]["perplexity"]) == ["asana.com", "help.asana.com"]


def test_target_domain_is_registrable_host(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    _seed(db)
    ev = read_evidence(db)
    # asana.com preferred over help.asana.com
    assert ev["target_domain"] == "asana.com"


def test_target_domain_none_when_no_brand_citations(tmp_path):
    db = str(tmp_path / "geo.sqlite")
    s = FactStore(db)
    pid = s.add_prompt("q")
    r = s.add_run(pid, engine="openai", model="m", run_index=0, answer_text="a")
    s.add_citation(r, cited_url="https://x.com", domain="x.com", is_target_brand=False)
    s.close()
    assert read_evidence(db)["target_domain"] is None
