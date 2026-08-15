"""Request/response models for the GEO web API (pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

KNOWN_ENGINES = ("openai", "perplexity", "gemini", "anthropic")


class RunRequest(BaseModel):
    brand: str = Field(min_length=1)
    category: str = Field(min_length=1)
    aliases: list[str] = []
    competitors: list[str] = []
    target_domain: str | None = None
    competitor_domains: list[str] = []
    engines: list[str] = list(KNOWN_ENGINES)
    n_prompts: int = Field(default=30, ge=1, le=100)
    repeats: int = Field(default=5, ge=1, le=20)
    mode: Literal["dry-run", "live"] = "dry-run"
    locale: str = "us"
    seed: int = 0
    save_brand: bool = False


class RunSummary(BaseModel):
    id: int
    brand: str
    category: str
    mode: str
    status: str
    progress_pct: float = 0.0
    actual_cost: float = 0.0
    created_at: str | None = None
    finished_at: str | None = None


class RunDetail(RunSummary):
    error: str | None = None


class RunCreated(BaseModel):
    run: RunDetail
    report: dict | None = None  # dry-run returns the report inline (it's synchronous)


class BrandIn(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    domain: str | None = None
    aliases: list[str] = []
    competitors: list[str] = []
    competitor_domains: list[str] = []


class EstimateOut(BaseModel):
    per_provider: dict[str, float]
    total: float
    calls: int
    note: str
