"""GEO web API (FastAPI) — dynamic, multi-brand analysis over the existing pipeline.

Reuses `app/pipeline.py` (brand-agnostic already) + the POCs unchanged; persists runs and
their `GeoReport`s to a SQLite index (`server/db.py`). This slice supports **dry-run**
(synthetic, $0, offline) end-to-end; live runs are gated (use the CLI or a later phase).

    uvicorn server.main:app --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import bootstrap, db
from .schemas import (
    KNOWN_ENGINES,
    BrandIn,
    EstimateOut,
    RunCreated,
    RunDetail,
    RunRequest,
    RunSummary,
)

bootstrap.ensure_paths()  # put the pipeline + POCs (app/, pocs/*) on sys.path before importing

from budget import preflight_estimate  # noqa: E402
from dashboard import render_dashboard  # noqa: E402
from pipeline import DEFAULT_MODELS, GeoConfig, run_pipeline  # noqa: E402

app = FastAPI(title="AI_GEO Platform API", version="1.0")

_origins = os.getenv("GEO_CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"], allow_headers=["*"],
)


def _config(req: RunRequest) -> GeoConfig:
    engines = tuple(e for e in req.engines if e in KNOWN_ENGINES) or KNOWN_ENGINES
    return GeoConfig(
        brand=req.brand, category=req.category, aliases=tuple(req.aliases),
        competitors=tuple(req.competitors), target_domain=req.target_domain,
        competitor_domains=tuple(req.competitor_domains), engines=engines,
        n_prompts=req.n_prompts, repeats=req.repeats, live=(req.mode == "live"),
        locale=req.locale, seed=req.seed,
    )


def _run_row_to_detail(row: dict) -> RunDetail:
    return RunDetail(
        id=row["id"], brand=row["brand"], category=row["category"], mode=row["mode"],
        status=row["status"], progress_pct=row.get("progress_pct", 0.0) or 0.0,
        actual_cost=row.get("actual_cost", 0.0) or 0.0, created_at=row.get("created_at"),
        finished_at=row.get("finished_at"), error=row.get("error"),
    )


@app.get("/api/health")
def health() -> dict:
    """Liveness + which engine keys are configured (booleans only — no key values)."""
    env = {
        "openai": "OPENAI_API_KEY", "perplexity": "PERPLEXITY_API_KEY",
        "gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
    }
    return {
        "ok": True,
        "engines": {e: bool(os.getenv(k)) for e, k in env.items()},
        "known_engines": list(KNOWN_ENGINES),
    }


@app.post("/api/estimate", response_model=EstimateOut)
def estimate(req: RunRequest) -> EstimateOut:
    """Rough per-provider cost estimate for a live run (no spend)."""
    cfg = _config(req)
    calls_per_engine = cfg.n_prompts * cfg.repeats
    per: dict[str, float] = {}
    for e in cfg.engines:
        one = preflight_estimate(e, DEFAULT_MODELS[e], prompt_chars=120)
        per[e] = round(one * calls_per_engine, 4)
    return EstimateOut(
        per_provider=per, total=round(sum(per.values()), 4),
        calls=calls_per_engine * len(cfg.engines),
        note="Conservative upper-bound estimate; each provider is still hard-capped at $2.",
    )


@app.post("/api/runs", response_model=RunCreated)
def create_run(req: RunRequest) -> RunCreated:
    """Create + execute an analysis run. Dry-run is synchronous ($0, offline)."""
    if req.mode == "live":
        raise HTTPException(
            status_code=400,
            detail="Live runs are not enabled in the web UI in this build (they spend real "
                   "money). Use the CLI: `geo run … --live`, or a later app phase.",
        )
    cfg = _config(req)
    run_id = db.create_run(req.brand, req.category, req.mode, req.model_dump(), status="running")
    try:
        report = run_pipeline(cfg)
    except Exception as exc:  # noqa: BLE001 - surface as a failed run, not a 500
        db.finish_run(run_id, status="error", error=str(exc), progress_pct=0.0)
        raise HTTPException(status_code=500, detail=f"pipeline failed: {exc}") from exc
    report_dict = report.to_dict()
    db.save_report(run_id, report_dict)
    db.finish_run(run_id, status="done", actual_cost=0.0)
    if req.save_brand:
        db.upsert_brand(req.brand, req.category, domain=req.target_domain,
                        aliases=req.aliases, competitors=req.competitors,
                        competitor_domains=req.competitor_domains)
    return RunCreated(run=_run_row_to_detail(db.get_run(run_id)), report=report_dict)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(limit: int = 100, offset: int = 0) -> list[RunSummary]:
    return [RunSummary(**r) for r in db.list_runs(limit=limit, offset=offset)]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: int) -> RunDetail:
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_row_to_detail(row)


@app.get("/api/runs/{run_id}/report")
def get_report(run_id: int) -> dict:
    report = db.get_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found (run may still be running)")
    return report


@app.get("/api/runs/{run_id}/report.html", response_class=HTMLResponse)
def get_report_html(run_id: int) -> HTMLResponse:
    report = db.get_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return HTMLResponse(render_dashboard(report))


@app.get("/api/brands")
def get_brands() -> list[dict]:
    return db.list_brands()


@app.post("/api/brands")
def save_brand(brand: BrandIn) -> dict:
    bid = db.upsert_brand(
        brand.name, brand.category, domain=brand.domain, aliases=brand.aliases,
        competitors=brand.competitors, competitor_domains=brand.competitor_domains)
    return {"id": bid}
