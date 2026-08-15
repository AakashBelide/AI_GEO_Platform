"""Offline tests for the GEO web API (FastAPI). Dry-run only — no keys, no network."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the app DB at a throwaway file so tests never touch data/app.db.
    monkeypatch.setenv("GEO_APP_DB", str(tmp_path / "app.db"))
    return TestClient(app)


BODY = {
    "brand": "Acme Board",
    "category": "project management tools",
    "aliases": ["Acme"],
    "competitors": ["Trellix", "Mondayish"],
    "target_domain": "acme.example",
    "competitor_domains": ["trellix.example", "mondayish.example"],
    "engines": ["openai", "perplexity", "gemini"],
    "n_prompts": 20,
    "repeats": 6,
    "seed": 1,
}


def test_health_reports_engine_booleans(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["engines"]) == {"openai", "perplexity", "gemini", "anthropic"}
    assert all(isinstance(v, bool) for v in body["engines"].values())  # never key values


def test_dry_run_creates_run_and_returns_report(client):
    r = client.post("/api/runs", json=BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["run"]["status"] == "done"
    assert data["run"]["mode"] == "dry-run"
    rep = data["report"]
    assert rep["brand"] == "Acme Board"
    assert set(rep["per_engine_metrics"]) == {"openai", "perplexity", "gemini"}
    # honesty: every rate carries an interval
    m = rep["per_engine_metrics"]["openai"]["citation"]
    assert m["lo"] <= m["point"] <= m["hi"]
    assert rep["findings"] and rep["recommendations"]


def test_report_and_history_persist(client):
    run_id = client.post("/api/runs", json=BODY).json()["run"]["id"]
    # report fetchable
    rep = client.get(f"/api/runs/{run_id}/report")
    assert rep.status_code == 200 and rep.json()["brand"] == "Acme Board"
    # html render
    html = client.get(f"/api/runs/{run_id}/report.html")
    assert html.status_code == 200 and "<!DOCTYPE html>" in html.text
    assert "Acme Board" in html.text
    # history lists it
    hist = client.get("/api/runs").json()
    assert any(row["id"] == run_id for row in hist)


def test_live_mode_is_gated(client):
    r = client.post("/api/runs", json={**BODY, "mode": "live"})
    assert r.status_code == 400
    assert "live" in r.json()["detail"].lower()


def test_validation_rejects_out_of_range(client):
    r = client.post("/api/runs", json={**BODY, "n_prompts": 999})
    assert r.status_code == 422  # ge/le bounds enforced by pydantic


def test_estimate_sums_per_provider(client):
    r = client.post("/api/estimate", json=BODY)
    assert r.status_code == 200
    est = r.json()
    assert set(est["per_provider"]) == {"openai", "perplexity", "gemini"}
    assert est["total"] == pytest.approx(sum(est["per_provider"].values()), abs=1e-6)
    assert est["calls"] == 20 * 6 * 3


def test_missing_run_is_404(client):
    assert client.get("/api/runs/99999").status_code == 404
    assert client.get("/api/runs/99999/report").status_code == 404


def test_save_brand_then_list(client):
    client.post("/api/runs", json={**BODY, "save_brand": True})
    brands = client.get("/api/brands").json()
    assert any(b["name"] == "Acme Board" for b in brands)
    assert brands[0]["competitors"]  # JSON round-trips back to a list
