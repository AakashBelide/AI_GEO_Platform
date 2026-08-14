"""Offline tests for the app pipeline + CLI (Task A1). No keys, no network."""

from __future__ import annotations

import json

import pytest
from geo import _csv, _slug, build_parser, cmd_report, render, write_report
from pipeline import GeoConfig, GeoReport, run_pipeline

CONFIG = GeoConfig(
    brand="Acme Board",
    category="project management tools",
    aliases=("Acme",),
    competitors=("Trellix", "Mondayish"),
    target_domain="acme.example",
    competitor_domains=("trellix.example", "mondayish.example"),
    engines=("openai", "perplexity", "gemini"),
    n_prompts=20, repeats=6, seed=1,
)


# --- pipeline (dry-run) ---------------------------------------------------- #
def test_dry_run_is_deterministic():
    a = run_pipeline(CONFIG, generated_utc="2026-08-14T00:00:00+00:00")
    b = run_pipeline(CONFIG, generated_utc="2026-08-14T00:00:00+00:00")
    assert a.to_dict() == b.to_dict()


def test_dry_run_labels_synthetic_and_needs_no_ledger():
    rep = run_pipeline(CONFIG, generated_utc="t")
    assert rep.mode == "dry-run (synthetic)"
    assert any("SYNTHETIC" in n for n in rep.notes)


def test_report_has_prompt_set_and_per_engine_metrics_with_cis():
    rep = run_pipeline(CONFIG, generated_utc="t")
    assert rep.prompt_set["count"] == 20
    assert rep.prompt_set["skew"]["ok"]
    assert set(rep.per_engine_metrics) == {"openai", "perplexity", "gemini"}
    m = rep.per_engine_metrics["openai"]
    for key in ("mention", "citation", "share_of_voice"):
        est = m[key]
        assert est["lo"] <= est["point"] <= est["hi"]  # a real interval


def test_reconciliation_present_with_multiple_engines():
    rep = run_pipeline(CONFIG, generated_utc="t")
    assert rep.reconciliation
    assert rep.reconciliation["overlap"]["n_engines"] == 3
    assert "methodology" in rep.reconciliation


def test_engine_base_rates_differ_across_engines():
    # synthetic generator gives each engine a distinct propensity -> citation points differ
    rep = run_pipeline(CONFIG, generated_utc="t")
    pts = {e: m["citation"]["point"] for e, m in rep.per_engine_metrics.items()}
    assert len(set(pts.values())) > 1


def test_single_engine_skips_reconciliation():
    cfg = GeoConfig(brand="X", category="c", engines=("openai",),
                    target_domain="x.example", n_prompts=10, repeats=5)
    rep = run_pipeline(cfg, generated_utc="t")
    assert rep.reconciliation == {}


def test_no_domains_skips_sov_and_reconcile_with_note():
    cfg = GeoConfig(brand="X", category="c", engines=("openai", "perplexity"),
                    n_prompts=10, repeats=5)
    rep = run_pipeline(cfg, generated_utc="t")
    assert rep.reconciliation == {}
    assert any("No target/competitor domains" in n for n in rep.notes)


def test_empty_engines_raises():
    with pytest.raises(ValueError):
        run_pipeline(GeoConfig(brand="X", category="c", engines=()))


def test_live_without_ledger_raises():
    with pytest.raises(ValueError):
        run_pipeline(GeoConfig(brand="X", category="c", live=True))


# --- CLI helpers ----------------------------------------------------------- #
def test_csv_parsing():
    assert _csv("a, b ,c") == ("a", "b", "c")
    assert _csv("") == ()
    assert _csv(None) == ()


def test_slug():
    assert _slug("Acme Board!") == "acme-board"
    assert _slug("") == "brand"


def test_parser_requires_brand_and_category():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--brand", "X"])  # missing --category


def test_parser_defaults_to_dry_run():
    args = build_parser().parse_args(["run", "--brand", "X", "--category", "c"])
    assert args.live is False
    assert args.repeats == 5 and args.prompts == 30


# --- rendering + artifact -------------------------------------------------- #
def test_render_contains_key_sections():
    rep = run_pipeline(CONFIG, generated_utc="t")
    text = render(rep)
    assert "GEO report: Acme Board" in text
    assert "per-engine metrics" in text
    assert "cross-engine reconciliation" in text
    assert "methodology card" in text


def test_write_report_creates_valid_json(tmp_path):
    rep = run_pipeline(CONFIG, generated_utc="t")
    path = write_report(rep, tmp_path)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["brand"] == "Acme Board"
    assert loaded["mode"] == "dry-run (synthetic)"
    assert "per_engine_metrics" in loaded


def test_geo_report_roundtrips_through_dict():
    rep = run_pipeline(CONFIG, generated_utc="t")
    d = rep.to_dict()
    assert GeoReport(**d).to_dict() == d


# --- report subcommand (Task A2 HTML dashboard) ---------------------------- #
def test_parser_report_subcommand_wiring():
    args = build_parser().parse_args(["report", "--input", "r.json", "--output", "d.html"])
    assert args.command == "report"
    assert args.func is cmd_report
    assert args.input == "r.json" and args.output == "d.html"


def test_report_requires_input():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["report", "--output", "d.html"])  # missing --input


def test_cmd_report_writes_self_contained_html(tmp_path):
    rep = run_pipeline(CONFIG, generated_utc="t")
    json_path = write_report(rep, tmp_path)
    out_path = tmp_path / "dash.html"
    args = build_parser().parse_args(
        ["report", "--input", str(json_path), "--output", str(out_path)]
    )
    assert args.func(args) == 0
    assert out_path.exists()
    html = out_path.read_text()
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in html
    assert "Acme Board" in html


def test_cmd_report_default_output_path(tmp_path):
    rep = run_pipeline(CONFIG, generated_utc="t")
    json_path = write_report(rep, tmp_path)
    args = build_parser().parse_args(
        ["report", "--input", str(json_path), "--out-dir", str(tmp_path)]
    )
    assert args.func(args) == 0
    assert (tmp_path / (json_path.stem + ".html")).exists()
