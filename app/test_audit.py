"""Offline tests for `geo audit` (C1 crawler wired into the CLI). No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The crawler POC dir on sys.path (geo's _paths does this too; explicit here for a clean block).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pocs" / "crawler"))

from crawler import FetchResult  # noqa: E402
from geo import SANDBOX_DEFAULT, build_parser, cmd_audit, run_audit  # noqa: E402

_HTML = (
    "<html><head><title>Best Project Management Tools 2026</title>"
    "<meta name='description' content='A roundup of tools.'>"
    "<script type='application/ld+json'>{\"@type\":\"Article\"}</script></head>"
    "<body><h1>Top tools</h1><p>" + ("word " * 60) + "10 20 30 40</p></body></html>"
)


def _fake_fetch(url, user_agent, timeout):
    # No <a> links in the HTML, so the crawl fetches only the seed page (deterministic).
    return FetchResult(url=url, status=200, html=_HTML)


def test_run_audit_offline_returns_scored_audit():
    records = run_audit(
        "https://sandbox.example/", max_pages=3, delay=0.0,
        fetch_fn=_fake_fetch, respect_robots=False,
    )
    assert len(records) == 1
    a = records[0].audit
    assert 0.0 <= a.ai_readability_score <= 1.0
    assert a.json_ld_present is True          # the JSON-LD block is detected
    assert a.word_count > 0


def test_run_audit_respects_page_cap():
    # HTML that links to two more same-host pages -> cap should bound the crawl.
    linked = _HTML.replace(
        "<body>",
        "<body><a href='https://sandbox.example/a'>a</a>"
        "<a href='https://sandbox.example/b'>b</a>",
    )

    def fake(url, ua, t):
        return FetchResult(url=url, status=200, html=linked)

    records = run_audit("https://sandbox.example/", max_pages=2, delay=0.0,
                        fetch_fn=fake, respect_robots=False)
    assert len(records) <= 2  # never exceeds the cap


def test_audit_parser_defaults_to_sandbox():
    args = build_parser().parse_args(["audit"])
    assert args.command == "audit"
    assert args.func is cmd_audit
    assert args.url == SANDBOX_DEFAULT
    assert args.max_pages == 10


def test_cmd_audit_writes_json(tmp_path, monkeypatch, capsys):
    # Point the crawler at the injected fetcher by monkeypatching run_audit's fetch path.
    import geo

    monkeypatch.setattr(
        geo, "run_audit",
        lambda url, **kw: run_audit(url, fetch_fn=_fake_fetch, respect_robots=False,
                                    max_pages=kw.get("max_pages", 3), delay=0.0),
    )
    args = build_parser().parse_args(["audit", "--out-dir", str(tmp_path)])
    assert geo.cmd_audit(args) == 0
    written = list(tmp_path.glob("audit_*.json"))
    assert written and isinstance(json.loads(written[0].read_text()), list)
    assert "AI-readability" in capsys.readouterr().out
