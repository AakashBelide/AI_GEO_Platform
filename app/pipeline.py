"""End-to-end GEO pipeline (Task A1): brand → prompts → runs → metrics(CIs) → reconcile.

Wires the validated POCs into one flow, reusing them unchanged:
  onboarding (R1) → connectors (F3, live only) / synthetic → fact store (F2) →
  metrics (R2, with CIs from rigor/O1) → reconcile (O3, overlap + methodology card).

Two modes:
  * **dry-run (default):** fabricates deterministic synthetic engine answers — $0, no network,
    fully reproducible. Exercises the whole metrics/reconcile path so the wiring is testable.
  * **live (`--live`):** calls the real engines through the budget-guarded connectors; a
    provider can never exceed its $2 cap. Every run is persisted to the append-only fact store.

The synthetic answers are clearly labeled as such in the report; they are NOT a measurement of
any real brand and must never be presented as one.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import _paths  # noqa: F401  (side effect: put pocs/* on sys.path)
from connectors import ENGINES
from insights import generate_findings, generate_recommendations
from insights import top_domains as compute_top_domains
from metrics import RunRecord, compute_brand_metrics
from onboarding import BrandProfile, build_prompt_set
from reconcile import reconcile

DEFAULT_ENGINES = ("openai", "perplexity", "gemini", "anthropic")
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini", "perplexity": "sonar",
    "gemini": "gemini-2.5-flash", "anthropic": "claude-haiku-4-5",
}


@dataclass
class GeoConfig:
    brand: str
    category: str
    aliases: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    target_domain: str | None = None
    competitor_domains: tuple[str, ...] = ()
    engines: tuple[str, ...] = DEFAULT_ENGINES
    n_prompts: int = 30
    repeats: int = 5
    live: bool = False
    locale: str = "us"
    seed: int = 0

    def profile(self) -> BrandProfile:
        return BrandProfile(
            name=self.brand, category=self.category, domain=self.target_domain,
            aliases=self.aliases, competitors=self.competitors)

    def target_domains(self) -> list[str]:
        return [self.target_domain] if self.target_domain else []


def _est(e) -> dict:
    return asdict(e)


# --------------------------------------------------------------------------- #
# Run production
# --------------------------------------------------------------------------- #
_ANSWER_TRUNCATE = 700
_MAX_CITATIONS_PER_SAMPLE = 12
# A run producer returns: per-engine RunRecords, a transcript (one representative sample
# per prompt per engine), and every cited domain per engine (for top_domains).
RunProduction = tuple[dict[str, list[RunRecord]], dict[str, list], dict[str, list[str]]]


def _sample(prompt_text: str, answer: str, citations: list[dict]) -> dict:
    """One transcript sample: the prompt, a truncated answer, and its capped citations."""
    return {
        "prompt_text": prompt_text,
        "answer": (answer or "")[:_ANSWER_TRUNCATE],
        "citations": citations[:_MAX_CITATIONS_PER_SAMPLE],
    }


def _synthetic_runs(config: GeoConfig, prompts) -> RunProduction:
    """Deterministic fabricated answers per engine — reproducible, $0, offline.

    Each engine gets a distinct base citation propensity so the reconciliation has real
    cross-engine structure to report. These are NOT real measurements (labeled in the report).
    Also returns a transcript + per-engine cited domains for the evidence/insights layer.
    """
    rng = random.Random(config.seed)
    target = config.target_domain or "brand.example"
    comps = list(config.competitor_domains) or ["rivala.example", "rivalb.example"]
    ecosystems = ["reddit.com", "wikipedia.org", "youtube.com"]
    base_rate = {e: 0.2 + 0.12 * i for i, e in enumerate(config.engines)}
    # Each engine cites its OWN vendor/blog domains too, so cross-engine overlap is partial
    # (not a flat 1.0) and the divergence explainer has structure to find.
    engine_sources = {e: [f"{e}-src{k}.example" for k in range(1, 5)] for e in config.engines}
    runs: dict[str, list[RunRecord]] = {}
    transcript: dict[str, list] = {}
    domains_by_engine: dict[str, list[str]] = {}
    for engine in config.engines:
        recs: list[RunRecord] = []
        samples: list[dict] = []
        all_domains: list[str] = []
        # bias the second engine toward Reddit so divergence fires in the demo
        reddit_bias = 0.9 if engine == config.engines[min(1, len(config.engines) - 1)] else 0.05
        for pid in range(len(prompts)):
            for _ in range(config.repeats):
                cites: list[str] = []
                if rng.random() < base_rate[engine]:
                    cites.append(target)
                if rng.random() < 0.5:
                    cites.append(rng.choice(comps))
                if rng.random() < reddit_bias:
                    cites.append("reddit.com")
                elif rng.random() < 0.3:
                    cites.append(rng.choice(ecosystems))
                cites.append(rng.choice(engine_sources[engine]))
                rng.shuffle(cites)
                names = rng.random() < base_rate[engine]
                text = f"{config.brand} is a strong option." if names else "Consider others."
                recs.append(RunRecord(pid, engine, text, tuple(cites)))
                all_domains.extend(cites)
                if len(samples) == pid:  # first run of this prompt -> representative sample
                    citations = [{"url": f"https://{d}", "domain": d, "position": i}
                                 for i, d in enumerate(cites, start=1)]
                    samples.append(_sample(prompts[pid].text, text, citations))
        runs[engine] = recs
        transcript[engine] = samples
        domains_by_engine[engine] = all_domains
    return runs, transcript, domains_by_engine


def _live_runs(config: GeoConfig, prompts, ledger, store=None) -> RunProduction:
    """Real engine calls via the budget-guarded connectors; persisted to the fact store.

    Also captures the raw evidence (a representative sample per prompt with full
    url/domain/position citations, plus every cited domain) for the insights layer.
    """
    runs: dict[str, list[RunRecord]] = {}
    transcript: dict[str, list] = {}
    domains_by_engine: dict[str, list[str]] = {}
    prompt_ids: dict[int, int] = {}
    if store is not None:
        for pid, p in enumerate(prompts):
            prompt_ids[pid] = store.add_prompt(p.text, intent=p.intent,
                                               category=p.category, locale=config.locale)
    for engine in config.engines:
        cls = ENGINES[engine]
        eng = cls(engine, DEFAULT_MODELS[engine], ledger)
        recs: list[RunRecord] = []
        samples: list[dict] = []
        all_domains: list[str] = []
        for pid, p in enumerate(prompts):
            for rep in range(config.repeats):
                try:
                    resp = eng.query(p.text, run_index=pid * config.repeats + rep)
                except Exception:  # noqa: BLE001 - budget stop / transient; keep partial data
                    break
                recs.append(RunRecord(pid, engine, resp.answer_text, tuple(resp.domains)))
                all_domains.extend(d for d in resp.domains if d)
                if rep == 0:  # representative sample = first repeat of the prompt
                    citations = [{"url": c.url, "domain": c.domain, "position": c.position}
                                 for c in resp.citations]
                    samples.append(_sample(p.text, resp.answer_text, citations))
                if store is not None:
                    rid = store.add_run(prompt_ids[pid], engine=engine, model=eng.model,
                                        run_index=rep, answer_text=resp.answer_text,
                                        est_cost_usd=resp.est_cost_usd)
                    for c in resp.citations:
                        is_t = bool(config.target_domain) and (
                            c.domain == config.target_domain
                            or (c.domain or "").endswith("." + (config.target_domain or "")))
                        store.add_citation(rid, cited_url=c.url, domain=c.domain,
                                           position=c.position, is_target_brand=is_t)
        if recs:
            runs[engine] = recs
            transcript[engine] = samples
            domains_by_engine[engine] = all_domains
    return runs, transcript, domains_by_engine


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
@dataclass
class GeoReport:
    brand: str
    category: str
    mode: str                      # "dry-run (synthetic)" | "live"
    generated_utc: str
    prompt_set: dict
    per_engine_metrics: dict       # engine -> {mention, citation, share_of_voice, position}
    reconciliation: dict
    spend: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    # Evidence + interpretation layer (Task A3)
    prompts: list = field(default_factory=list)          # [{text, intent, category}]
    transcript: dict = field(default_factory=dict)       # engine -> [{prompt_text, answer, ...}]
    top_domains: dict = field(default_factory=dict)      # engine -> [[domain, count], ...]
    findings: list = field(default_factory=list)         # factual, restated numbers
    recommendations: list = field(default_factory=list)  # hedged, evidence-tied GEO actions

    def to_dict(self) -> dict:
        return asdict(self)


def run_pipeline(config: GeoConfig, *, ledger=None, store=None,
                 generated_utc: str | None = None) -> GeoReport:
    """Execute the full pipeline and return a serializable report."""
    if not config.engines:
        raise ValueError("at least one engine is required")
    ts = generated_utc or datetime.now(UTC).isoformat()
    profile = config.profile()
    ps = build_prompt_set(profile, n_total=config.n_prompts)

    if config.live:
        if ledger is None:
            raise ValueError("live mode requires a CostLedger")
        runs, transcript, domains_by_engine = _live_runs(config, ps.prompts, ledger, store)
        mode = "live"
    else:
        runs, transcript, domains_by_engine = _synthetic_runs(config, ps.prompts)
        mode = "dry-run (synthetic)"

    runs = {e: r for e, r in runs.items() if r}
    transcript = {e: transcript[e] for e in runs if e in transcript}
    domains_by_engine = {e: domains_by_engine.get(e, []) for e in runs}
    aliases = profile.all_names()
    target = config.target_domains()
    comps = list(config.competitor_domains)

    per_engine: dict[str, dict] = {}
    for engine, recs in runs.items():
        m = compute_brand_metrics(recs, aliases=aliases, target_domains=target,
                                  competitor_domains=comps, engine=engine)
        per_engine[engine] = {
            "n_runs": m.n_runs,
            "mention": _est(m.mention),
            "citation": _est(m.citation),
            "share_of_voice": _est(m.share_of_voice),
            "position": asdict(m.position),
        }

    recon = {}
    if len(runs) >= 2 and (target or comps):
        recon = reconcile(
            runs, target_domains=target, competitor_domains=comps,
            models={e: DEFAULT_MODELS[e] for e in runs},
            generated_utc=ts, n_prompts=len(ps.prompts),
            repeats_per_prompt=config.repeats, locale=config.locale,
        ).to_dict()

    notes: list[str] = []
    if not config.live:
        notes.append("SYNTHETIC data — deterministic fabrication for wiring/demo, "
                     "NOT a measurement of this brand. Use --live for real engine calls.")
    if not target and not comps:
        notes.append("No target/competitor domains supplied — SoV and reconciliation skipped.")
    if config.repeats < 5:
        notes.append(f"repeats={config.repeats}: intervals will be wide / SoV may be degenerate.")

    spend = {}
    if ledger is not None:
        spend = {e: {"spent": ledger.spent(e), "cap": ledger.cap_usd} for e in config.engines}

    prompts_list = [{"text": p.text, "intent": p.intent, "category": p.category}
                    for p in ps.prompts]
    top_dom = compute_top_domains(domains_by_engine)

    report = GeoReport(
        brand=config.brand, category=config.category, mode=mode, generated_utc=ts,
        prompt_set={"count": len(ps.prompts), "intents": ps.intents,
                    "skew": asdict(ps.skew)},
        per_engine_metrics=per_engine, reconciliation=recon, spend=spend, notes=notes,
        prompts=prompts_list, transcript=transcript, top_domains=top_dom,
    )

    # Interpretation layer: findings/recommendations derived from the assembled report.
    insight_view = report.to_dict()
    insight_view["target_domain"] = config.target_domain
    report.findings = generate_findings(insight_view)
    report.recommendations = generate_recommendations(insight_view)
    return report
