"""Cross-engine reconciliation with a transparent, disclosed methodology (Task O3).

Every GEO vendor's "Share of Voice" means something different because each answer engine
cites a different slice of the web (reported ChatGPT-Perplexity domain overlap is ~11%).
This module does the honest version: it **normalizes citations the same documented way
across engines, quantifies how much they actually disagree, explains where the divergence
comes from, and auto-emits a machine-readable methodology card** so a reader can see exactly
how every number was produced.

  * O3.1 overlap: pairwise Jaccard on cited-domain sets + a mean-overlap headline.
  * O3.2 per-engine Share of Voice under ONE documented normalization (reuses R2/O1 — the
    same cluster-bootstrap CI, so cross-engine SoV is comparable and honest about noise).
  * O3.3 divergence explainer: which engine over-indexes which source ecosystem
    (Reddit / Wikipedia / YouTube / ...).
  * O3.4 methodology card: sampling, per-engine access method, dates, normalization, caveats.

Pure computation — no keys, no network — so the suite runs offline. Reuses `pocs/metrics`
(and through it `pocs/rigor`) via the POC path shim below.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from itertools import combinations
from pathlib import Path

# POC path shim: reuse the sibling metrics POC (which itself reuses rigor).
_METRICS = Path(__file__).resolve().parent.parent / "metrics"
if str(_METRICS) not in sys.path:
    sys.path.insert(0, str(_METRICS))

from metrics import Estimate, RunRecord, domain_matches, share_of_voice  # noqa: E402

RunsByEngine = Mapping[str, Sequence[RunRecord]]


# --------------------------------------------------------------------------- #
# O3.1 — cross-engine citation overlap (Jaccard on cited-domain sets)
# --------------------------------------------------------------------------- #
def cited_domain_sets(runs_by_engine: RunsByEngine) -> dict[str, set[str]]:
    """Aggregate the set of unique cited domains per engine (lower-cased)."""
    out: dict[str, set[str]] = {}
    for engine, records in runs_by_engine.items():
        domains: set[str] = set()
        for r in records:
            for d in r.cited_domains:
                if d:
                    domains.add(d.lower().lstrip("."))
        out[engine] = domains
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    """|A ∩ B| / |A ∪ B|; two empty sets are defined as fully overlapping (1.0)."""
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


@dataclass(frozen=True)
class OverlapReport:
    per_engine_unique_domains: dict[str, int]
    pairwise_jaccard: dict[str, float]  # "engineA|engineB" -> overlap
    mean_pairwise_jaccard: float
    n_engines: int

    def to_dict(self) -> dict:
        return asdict(self)


def overlap_report(runs_by_engine: RunsByEngine) -> OverlapReport:
    """Pairwise + mean cited-domain overlap across engines (replicates the ~11% metric)."""
    sets = cited_domain_sets(runs_by_engine)
    engines = sorted(sets)
    pair: dict[str, float] = {}
    vals: list[float] = []
    for a, b in combinations(engines, 2):
        j = jaccard(sets[a], sets[b])
        pair[f"{a}|{b}"] = j
        vals.append(j)
    mean = sum(vals) / len(vals) if vals else (1.0 if len(engines) <= 1 else 0.0)
    return OverlapReport(
        per_engine_unique_domains={e: len(sets[e]) for e in engines},
        pairwise_jaccard=pair,
        mean_pairwise_jaccard=mean,
        n_engines=len(engines),
    )


# --------------------------------------------------------------------------- #
# O3.2 — per-engine Share of Voice under ONE documented normalization
# --------------------------------------------------------------------------- #
DOMAIN_NORMALIZATION = (
    "URLs are reduced to their host, lower-cased, with a leading 'www.' stripped "
    "(see connectors.normalize_domain); a citation counts toward a brand if its domain "
    "equals or is a subdomain of that brand's registrable domain. Identical rule for "
    "every engine, so cross-engine SoV is comparable."
)


def per_engine_share_of_voice(
    runs_by_engine: RunsByEngine, target_domains: Sequence[str],
    competitor_domains: Sequence[str], *, confidence: float = 0.95, seed: int = 0,
) -> dict[str, Estimate]:
    """SoV (target ÷ target+competitor citations) per engine, each with a bootstrap CI.

    Uses the exact same `metrics.share_of_voice` normalization/estimator for every engine,
    so a difference between engines is a real difference, not a methodology artifact.
    """
    return {
        engine: share_of_voice(records, target_domains, competitor_domains,
                               confidence=confidence, seed=seed)
        for engine, records in runs_by_engine.items()
    }


# --------------------------------------------------------------------------- #
# O3.3 — divergence explainer (which engine favors which source ecosystem)
# --------------------------------------------------------------------------- #
# Documented, deliberately small mapping. Anything unmatched is "other"
# (vendor sites / blogs / news / uncategorized) — transparency over completeness.
ECOSYSTEM_RULES: dict[str, tuple[str, ...]] = {
    "reddit": ("reddit.com",),
    "wikipedia": ("wikipedia.org",),
    "youtube": ("youtube.com", "youtu.be"),
    "github": ("github.com",),
    "stackexchange": ("stackoverflow.com", "stackexchange.com"),
    "qna": ("quora.com",),
    "social": ("linkedin.com", "x.com", "twitter.com", "facebook.com"),
    "publishing": ("medium.com", "substack.com"),
}
ECOSYSTEMS = (*ECOSYSTEM_RULES.keys(), "other")


def classify_source(domain: str | None) -> str:
    """Map a cited domain to a documented source-ecosystem bucket ('other' if none)."""
    if not domain:
        return "other"
    for bucket, hosts in ECOSYSTEM_RULES.items():
        if domain_matches(domain, hosts):
            return bucket
    return "other"


def ecosystem_profile(runs_by_engine: RunsByEngine) -> dict[str, dict[str, float]]:
    """Per-engine fraction of *citations* (not deduped) falling in each ecosystem bucket."""
    out: dict[str, dict[str, float]] = {}
    for engine, records in runs_by_engine.items():
        counts: dict[str, int] = defaultdict(int)
        total = 0
        for r in records:
            for d in r.cited_domains:
                counts[classify_source(d)] += 1
                total += 1
        out[engine] = ({b: counts.get(b, 0) / total for b in ECOSYSTEMS}
                       if total else {b: 0.0 for b in ECOSYSTEMS})
    return out


@dataclass(frozen=True)
class DivergenceFinding:
    ecosystem: str
    engine: str          # the engine that most over-indexes this ecosystem
    engine_share: float
    mean_share: float
    delta: float         # engine_share - mean_share


def ecosystem_divergence(
    profile: Mapping[str, Mapping[str, float]], *, min_delta: float = 0.15
) -> list[DivergenceFinding]:
    """Flag ecosystems where one engine over-indexes vs the cross-engine mean by >= min_delta.

    Answers "which engine leans on Reddit / Wikipedia / ...?" — the disclosed reason two
    engines' Share-of-Voice numbers legitimately disagree.
    """
    engines = list(profile)
    if len(engines) < 2:
        return []
    findings: list[DivergenceFinding] = []
    for eco in ECOSYSTEMS:
        shares = {e: profile[e].get(eco, 0.0) for e in engines}
        mean = sum(shares.values()) / len(engines)
        top_engine = max(shares, key=lambda e: shares[e])
        delta = shares[top_engine] - mean
        if delta >= min_delta:
            findings.append(DivergenceFinding(
                ecosystem=eco, engine=top_engine, engine_share=shares[top_engine],
                mean_share=mean, delta=delta))
    findings.sort(key=lambda f: f.delta, reverse=True)
    return findings


# --------------------------------------------------------------------------- #
# O3.4 — machine-readable methodology card
# --------------------------------------------------------------------------- #
DEFAULT_ACCESS_METHODS = {
    "openai": "Responses API web_search tool → url_citation annotations",
    "perplexity": "Sonar REST → search_results[] / citations[]",
    "gemini": "Google Search grounding → groundingChunks[].web (PROXY for AI Overviews)",
    "anthropic": "web_search_20250305 tool → web_search_result blocks",
}

METRIC_DEFINITIONS = {
    "citation_overlap": "Pairwise Jaccard on the set of unique cited domains per engine.",
    "share_of_voice": "target citations ÷ (target + competitor) citations, "
                      "cluster-bootstrapped over prompts for a 95% CI.",
    "ecosystem_profile": "fraction of citations per documented source bucket "
                        f"({', '.join(ECOSYSTEMS)}).",
}


@dataclass
class MethodologyCard:
    generated_utc: str
    engines: dict[str, str]              # engine -> model
    access_method: dict[str, str]        # engine -> how citations were obtained
    n_prompts: int
    repeats_per_prompt: int
    locale: str
    domain_normalization: str
    metric_definitions: dict[str, str]
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_markdown(self) -> str:
        lines = ["## Methodology card", "",
                 f"- **Generated (UTC):** {self.generated_utc}",
                 f"- **Prompts × repeats:** {self.n_prompts} × {self.repeats_per_prompt}",
                 f"- **Locale:** {self.locale}",
                 f"- **Domain normalization:** {self.domain_normalization}",
                 "- **Engines / access:**"]
        for e in sorted(self.engines):
            lines.append(f"    - `{e}` ({self.engines[e]}): "
                         f"{self.access_method.get(e, 'n/a')}")
        lines.append("- **Metric definitions:**")
        for k, v in self.metric_definitions.items():
            lines.append(f"    - *{k}*: {v}")
        if self.caveats:
            lines.append("- **Caveats:**")
            lines += [f"    - {c}" for c in self.caveats]
        return "\n".join(lines)


def build_methodology_card(
    models: Mapping[str, str], *, generated_utc: str, n_prompts: int,
    repeats_per_prompt: int, locale: str = "us",
    access_methods: Mapping[str, str] | None = None,
    caveats: Sequence[str] | None = None,
) -> MethodologyCard:
    """Assemble the disclosed methodology for a reconciliation report (deterministic)."""
    access = dict(DEFAULT_ACCESS_METHODS)
    if access_methods:
        access.update(access_methods)
    base_caveats = [
        "Gemini grounding is a documented PROXY for Google AI Overviews, not the product.",
        "Gemini grounding URIs are 'vertexaisearch.cloud.google.com/grounding-api-redirect/...' "
        "wrappers, so its cited DOMAINS collapse to one host and are NOT comparable to other "
        "engines' domains without following the redirect (measured 2026-08-13). Exclude Gemini "
        "from domain-overlap until un-wrapped.",
        "Cited-source sets are locale-sensitive; SoV/overlap hold only for the stated locale.",
        "Single-run scores are omitted by design; all rates carry confidence intervals.",
    ]
    return MethodologyCard(
        generated_utc=generated_utc,
        engines={e: models[e] for e in sorted(models)},
        access_method={e: access.get(e, "n/a") for e in sorted(models)},
        n_prompts=n_prompts, repeats_per_prompt=repeats_per_prompt, locale=locale,
        domain_normalization=DOMAIN_NORMALIZATION,
        metric_definitions=dict(METRIC_DEFINITIONS),
        caveats=list(caveats) if caveats is not None else base_caveats,
    )


# --------------------------------------------------------------------------- #
# Bundle
# --------------------------------------------------------------------------- #
@dataclass
class ReconciliationReport:
    overlap: OverlapReport
    share_of_voice: dict[str, Estimate]
    ecosystem_profile: dict[str, dict[str, float]]
    divergence: list[DivergenceFinding]
    methodology: MethodologyCard

    def to_dict(self) -> dict:
        return {
            "overlap": self.overlap.to_dict(),
            "share_of_voice": {e: vars(est) for e, est in self.share_of_voice.items()},
            "ecosystem_profile": self.ecosystem_profile,
            "divergence": [asdict(f) for f in self.divergence],
            "methodology": self.methodology.to_dict(),
        }


def reconcile(
    runs_by_engine: RunsByEngine, *, target_domains: Sequence[str],
    competitor_domains: Sequence[str], models: Mapping[str, str],
    generated_utc: str, n_prompts: int, repeats_per_prompt: int,
    locale: str = "us", min_divergence: float = 0.15,
) -> ReconciliationReport:
    """One-call cross-engine reconciliation + methodology card."""
    profile = ecosystem_profile(runs_by_engine)
    return ReconciliationReport(
        overlap=overlap_report(runs_by_engine),
        share_of_voice=per_engine_share_of_voice(
            runs_by_engine, target_domains, competitor_domains),
        ecosystem_profile=profile,
        divergence=ecosystem_divergence(profile, min_delta=min_divergence),
        methodology=build_methodology_card(
            models, generated_utc=generated_utc, n_prompts=n_prompts,
            repeats_per_prompt=repeats_per_prompt, locale=locale),
    )
