"""Interpretation layer for a GEO report (A2 reporting): findings + GEO recommendations.

Every commercial GEO tool ships an opaque "visibility score" and a pile of generic
advice. This module does the honest version: it reads the numbers already produced by
the measurement pipeline (`per_engine_metrics`, `reconciliation`, `top_domains`) and
turns them into **short factual findings** and **evidence-tied, hedged recommendations**.

Design rules (non-negotiable, mirror the rest of the platform):
  * **Deterministic.** Pure functions over a report dict — no LLM call, no network, no
    fabrication. The same report always yields the same findings.
  * **Evidence-tied.** Every finding is a restatement of a number already in the report;
    every recommendation names a concrete domain / engine / count from THIS run.
  * **Honestly hedged.** Recommendations are framed as hypotheses to test, not proven
    levers — causal proof needs a controlled before/after (Task O2). We say so.
  * **Loud about synthetic data.** A dry-run report is prefixed as illustrative only.

Reuses `pocs/rigor.two_proportion_test` (the same test the dashboard uses) via the
sibling-dir path shim used across the POCs — the statistics live in one place only.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

# POC path shim: reuse the sibling rigor POC's statistics without duplicating them
# (identical pattern to pocs/metrics/metrics.py and pocs/dashboard/dashboard.py).
_RIGOR = Path(__file__).resolve().parent.parent / "rigor"
if str(_RIGOR) not in sys.path:
    sys.path.insert(0, str(_RIGOR))

from rigor import two_proportion_test  # noqa: E402

# Thresholds mirror pocs/dashboard so "the gap" means the same thing everywhere.
_GAP_MENTION_MIN = 0.40
_GAP_CITATION_MAX = 0.05
# A Share-of-Voice interval is treated as under-powered below this many clusters
# (prompts with target/competitor citations) or above this CI width.
_SOV_MIN_CLUSTERS = 5
_SOV_WIDE_CI = 0.5
# Community ecosystems that warrant a "presence" (not on-site SEO) recommendation.
_COMMUNITY_DOMAINS = ("reddit.com", "quora.com", "stackoverflow.com")

_SYNTHETIC_NOTE = (
    "ILLUSTRATIVE ONLY — this is a synthetic dry-run, not a real measurement; the "
    "findings and recommendations below are deterministic fabrications for demo/wiring."
)
_CAUSAL_HEDGE = (
    "All recommendations are directional hypotheses, not proven levers: causal proof "
    "needs a controlled before/after test (Task O2)."
)


# --------------------------------------------------------------------------- #
# Small typed accessors (a report dict survives a JSON round-trip, so tuples
# may arrive as lists — everything here is index/key based, never isinstance).
# --------------------------------------------------------------------------- #
def _is_synthetic(report: Mapping) -> bool:
    mode = str(report.get("mode", "")).lower()
    return "synthetic" in mode or "dry-run" in mode


def _est(metrics: Mapping, engine: str, key: str) -> dict:
    return (metrics.get(engine) or {}).get(key) or {}


def _point(metrics: Mapping, engine: str, key: str) -> float:
    return float(_est(metrics, engine, key).get("point", 0.0) or 0.0)


def _n(metrics: Mapping, engine: str, key: str) -> int:
    return int(_est(metrics, engine, key).get("n", 0) or 0)


def _k_n(metrics: Mapping, engine: str, key: str) -> tuple[int, int]:
    """Recover an integer success count from a proportion estimate ({point, n})."""
    n = _n(metrics, engine, key)
    return round(_point(metrics, engine, key) * n), n


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _own_domain(report: Mapping) -> str:
    """The brand's own domain phrase used in findings ('asana.com' or 'its own domain')."""
    td = report.get("target_domain")
    return str(td) if td else "its own domain"


# --------------------------------------------------------------------------- #
# top_domains — the "what actually gets cited" view
# --------------------------------------------------------------------------- #
def top_domains(
    citations_by_engine: Mapping[str, Sequence[str]], k: int = 10
) -> dict[str, list[tuple[str, int]]]:
    """Most-cited domains per engine with counts, highest first.

    ``citations_by_engine`` maps an engine to *every* cited domain it emitted (with
    repeats). Domains are lower-cased and a leading '.' is stripped so counts collapse
    the same way the reconciliation normalization does.
    """
    out: dict[str, list[tuple[str, int]]] = {}
    for engine, domains in citations_by_engine.items():
        counts: Counter[str] = Counter(
            d.lower().lstrip(".") for d in domains if d
        )
        out[engine] = counts.most_common(k)
    return out


def _overall_top(top: Mapping[str, Sequence], k: int = 5) -> list[tuple[str, int]]:
    """Aggregate per-engine top-domain lists into one cross-engine ranking."""
    agg: Counter[str] = Counter()
    for entries in top.values():
        for entry in entries:
            agg[str(entry[0])] += int(entry[1])
    return agg.most_common(k)


# --------------------------------------------------------------------------- #
# Findings — restated numbers, nothing invented
# --------------------------------------------------------------------------- #
def generate_findings(report: Mapping) -> list[str]:
    """Short factual statements pulled straight from the report's own numbers."""
    per = report.get("per_engine_metrics") or {}
    recon = report.get("reconciliation") or {}
    top = report.get("top_domains") or {}
    brand = str(report.get("brand", "the brand"))
    own = _own_domain(report)
    engines = sorted(per)
    out: list[str] = []

    # 1) The headline: mentioned a lot, but own domain cited ~never (per engine).
    for e in engines:
        mp, cp = _point(per, e, "mention"), _point(per, e, "citation")
        if mp >= _GAP_MENTION_MIN and cp <= _GAP_CITATION_MAX:
            out.append(
                f"{e} mentions {brand} in {_pct(mp)} of answers but cites {own} in "
                f"{_pct(cp)} of them — it recommends the brand without linking it."
            )

    # 2) Which engines DO vs DON'T cite the target domain.
    citers = [e for e in engines if _point(per, e, "citation") > 0]
    non_citers = [
        e for e in engines if _point(per, e, "citation") == 0 and _n(per, e, "citation") > 0
    ]
    if citers and non_citers:
        out.append(
            f"{_join(citers)} cite {own} (target-domain citation rate > 0); "
            f"{_join(non_citers)} never do on this run."
        )

    # 3) Cross-engine overlap and what it implies for portability.
    overlap = (recon.get("overlap") or {})
    mj = overlap.get("mean_pairwise_jaccard")
    if mj is not None and overlap.get("n_engines", 0) >= 2:
        out.append(
            f"Mean pairwise cited-domain overlap across engines is {float(mj):.2f} "
            "(Jaccard) — the engines barely cite the same sources, so share-of-voice is "
            "not portable across engines."
        )

    # 4) The domains that actually get cited for the category.
    overall = _overall_top(top, k=4)
    if overall:
        named = ", ".join(f"{d} ({c})" for d, c in overall)
        out.append(
            f"The most-cited domains for this category are {named} — third-party "
            "roundups/aggregators, not the brands' own sites."
        )

    # 5) Ecosystem divergence, only if the reconciler actually flagged one.
    for f in recon.get("divergence") or []:
        out.append(
            f"{f.get('engine')} over-indexes the '{f.get('ecosystem')}' ecosystem "
            f"(+{float(f.get('delta', 0.0)) * 100:.0f}pp vs the cross-engine mean)."
        )

    # 6) Engine pairs whose citation rates are NOT statistically distinguishable.
    for i in range(len(engines)):
        for j in range(i + 1, len(engines)):
            a, b = engines[i], engines[j]
            k1, n1 = _k_n(per, a, "citation")
            k2, n2 = _k_n(per, b, "citation")
            if n1 <= 0 or n2 <= 0:
                continue
            res = two_proportion_test(k1, n1, k2, n2)
            if not res.distinguishable:
                out.append(
                    f"{a} and {b} are NOT statistically distinguishable on target "
                    f"citation rate (p={res.p_value:.2f}) — do not claim one cites "
                    f"{brand} more than the other."
                )

    # 7) Data-sufficiency caveat when SoV intervals are degenerate / very wide.
    weak = _underpowered_sov(per)
    if weak:
        out.append(
            "Share-of-Voice is under-powered — " + "; ".join(weak) + " — do not rank "
            "brands on SoV from this run."
        )

    if _is_synthetic(report):
        out.insert(0, _SYNTHETIC_NOTE)
    return out


def _underpowered_sov(per: Mapping) -> list[str]:
    """Human phrases for engines whose SoV CI is degenerate (few clusters) or very wide."""
    weak: list[str] = []
    for e in sorted(per):
        sov = _est(per, e, "share_of_voice")
        if not sov:
            continue
        n = int(sov.get("n", 0) or 0)
        width = float(sov.get("hi", 0.0)) - float(sov.get("lo", 0.0))
        if n < _SOV_MIN_CLUSTERS or width >= _SOV_WIDE_CI:
            weak.append(
                f"{e} SoV {float(sov.get('point', 0.0)):.2f} on {n} prompt-cluster(s), "
                f"95% CI width {width:.2f}"
            )
    return weak


# --------------------------------------------------------------------------- #
# Recommendations — GEO actions, each hedged and tied to concrete evidence
# --------------------------------------------------------------------------- #
def generate_recommendations(report: Mapping) -> list[str]:
    """GEO actions tied to THIS run's evidence, each honestly hedged as a hypothesis."""
    per = report.get("per_engine_metrics") or {}
    top = report.get("top_domains") or {}
    own = report.get("target_domain")
    own_phrase = str(own) if own else "the brand's own domain"
    engines = sorted(per)
    out: list[str] = []

    citers = [e for e in engines if _point(per, e, "citation") > 0]
    non_citers = [
        e for e in engines if _point(per, e, "citation") == 0 and _n(per, e, "citation") > 0
    ]

    # 1) Non-citing engines cite third-party roundups instead → pursue those NAMED domains.
    if non_citers:
        third_party = _third_party_domains(top, non_citers, exclude={str(own or "")})
        if third_party:
            named = ", ".join(f"{d} ({c})" for d, c in third_party)
            out.append(
                f"{_join(non_citers)} never cite {own_phrase} but do cite {named} — a "
                "hypothesis worth testing is pursuing presence/mentions on those "
                "third-party roundups (PR & listings work, not on-site SEO)."
            )

    # 2) Engines that DO link the brand → keep those cited pages fresh/citation-worthy.
    if citers:
        out.append(
            f"{_join(citers)} already cite {own_phrase} — keep the specific landing "
            "pages they cite fresh and citation-worthy to defend that position."
        )

    # 3) The engine that most leans on a community (Reddit/etc.) → presence (verify).
    best_community: tuple[str, str, int] | None = None  # (engine, domain, count)
    for e in engines:
        for dom, cnt in _community_hits(top.get(e) or []):
            if best_community is None or cnt > best_community[2]:
                best_community = (e, dom, cnt)
    if best_community:
        e, d, c = best_community
        out.append(
            f"{e} leans on {d} ({c} citations, a top source for it) — authentic "
            f"community presence on {d} may help, but verify it is causal before "
            "investing (do not assume)."
        )

    # 4) Under-powered SoV → enlarge the prompt set before ranking brands.
    if _underpowered_sov(per):
        out.append(
            "Share-of-Voice rests on only a handful of prompt-clusters here — enlarge "
            "the prompt set before ranking brands on SoV (breadth over repeats, per the "
            "variance budget in pocs/rigor)."
        )

    if out:
        out.append(_CAUSAL_HEDGE)
    if _is_synthetic(report):
        out.insert(0, _SYNTHETIC_NOTE)
    return out


def _third_party_domains(
    top: Mapping[str, Sequence], engines: Sequence[str], *, exclude: set[str], k: int = 4
) -> list[tuple[str, int]]:
    """Top cited domains across the given engines, minus the brand's own domain."""
    agg: Counter[str] = Counter()
    for e in engines:
        for entry in top.get(e) or []:
            dom = str(entry[0])
            if dom and dom not in exclude:
                agg[dom] += int(entry[1])
    return agg.most_common(k)


def _community_hits(entries: Sequence) -> list[tuple[str, int]]:
    """Community domains (Reddit/Quora/...) present in an engine's top-domain list."""
    hits = [
        (str(e[0]), int(e[1]))
        for e in entries
        if any(str(e[0]) == c or str(e[0]).endswith("." + c) for c in _COMMUNITY_DOMAINS)
    ]
    hits.sort(key=lambda x: x[1], reverse=True)
    return hits


# --------------------------------------------------------------------------- #
def _join(items: Sequence[str]) -> str:
    """'a', 'a and b', 'a, b and c' — deterministic English list joining."""
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
