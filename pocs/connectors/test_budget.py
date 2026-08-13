"""Offline tests for the budget guard (Task F3 safety layer). No keys, no network."""

from __future__ import annotations

import json

import pytest
from budget import (
    BudgetExceeded,
    CostLedger,
    estimate_cost,
    preflight_estimate,
    pricing_for,
)


def test_estimate_cost_matches_pricing():
    # gpt-4o-mini: $0.15/M in, $0.60/M out, $0.025 tool fee
    cost = estimate_cost("openai", "gpt-4o-mini", input_tokens=1_000_000,
                         output_tokens=1_000_000, tool_calls=1)
    assert cost == pytest.approx(0.15 + 0.60 + 0.025)


def test_unknown_model_uses_pessimistic_fallback():
    known = pricing_for("openai", "gpt-4o-mini")
    unknown = pricing_for("openai", "some-future-model")
    assert unknown.input_per_mtok > known.input_per_mtok  # fallback is more expensive


def test_preflight_estimate_positive_and_scales():
    small = preflight_estimate("perplexity", "sonar", prompt_chars=100)
    big = preflight_estimate("perplexity", "sonar", prompt_chars=100_000)
    assert 0 < small < big


def test_ledger_records_and_persists(tmp_path):
    path = tmp_path / "ledger.json"
    a = CostLedger(path=path, cap_usd=2.0)
    a.record("openai", 0.30)
    a.record("openai", 0.20)
    assert a.spent("openai") == pytest.approx(0.50)
    # reload from disk -> spend survives
    b = CostLedger(path=path, cap_usd=2.0)
    assert b.spent("openai") == pytest.approx(0.50)
    assert b.remaining("openai") == pytest.approx(1.50)


def test_ledger_file_is_valid_json(tmp_path):
    path = tmp_path / "ledger.json"
    led = CostLedger(path=path, cap_usd=2.0)
    led.record("gemini", 0.10)
    data = json.loads(path.read_text())
    assert data["cap_usd"] == 2.0
    assert data["spent"]["gemini"] == pytest.approx(0.10)


def test_guard_allows_under_cap(tmp_path):
    led = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    led.record("anthropic", 1.50)
    led.guard("anthropic", 0.40)  # 1.90 <= 2.0 -> ok


def test_guard_blocks_over_cap(tmp_path):
    led = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    led.record("anthropic", 1.90)
    with pytest.raises(BudgetExceeded):
        led.guard("anthropic", 0.20)  # 2.10 > 2.0 -> blocked


def test_guard_boundary_exactly_at_cap_is_allowed(tmp_path):
    led = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    led.record("perplexity", 1.0)
    led.guard("perplexity", 1.0)  # exactly 2.0 -> allowed
    assert led.would_exceed("perplexity", 1.0001)


def test_guard_rejects_negative_estimate(tmp_path):
    led = CostLedger(path=tmp_path / "l.json")
    with pytest.raises(ValueError):
        led.guard("openai", -0.01)


def test_summary_shape(tmp_path):
    led = CostLedger(path=tmp_path / "l.json", cap_usd=2.0)
    led.record("openai", 0.25)
    s = led.summary()
    assert s["openai"]["spent"] == pytest.approx(0.25)
    assert s["openai"]["remaining"] == pytest.approx(1.75)
