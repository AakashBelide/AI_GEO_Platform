"""Core GEO metric set with uncertainty (Task R2).

The metrics every GEO tool reports — mention rate, citation rate, share of voice,
position, sentiment — but computed the honest way: as **estimates with confidence
intervals**, reusing the `rigor` POC (Task O1) rather than emitting single-run point
scores. Each metric treats a run as one Bernoulli/observed sample, so 30 runs of a
prompt give a Wilson interval, not a lone percentage.

Design:
  * Pure functions over lightweight `RunRecord`s (decoupled from the fact store and
    the live connectors), so the whole suite runs offline on synthetic fixtures.
  * Brand-mention detection is regex word-boundary + alias matching (the cheap,
    deterministic layer). Sentiment is LLM-as-judge — the judge is an **injectable
    `Callable`** and is validated against a hand-labeled gold set via Cohen's kappa
    (RESEARCH.md §3.3/§4.1); the offline tests use a stub judge, never the network.

Reuses `rigor.proportion_estimate` (Wilson CI) and `rigor.share_of_voice_ci`
(cluster bootstrap) — see the path shim below (POC layout; the app/ package will
import these normally once integrated).
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# POC path shim: reuse the sibling rigor POC's statistics without duplicating them.
_RIGOR = Path(__file__).resolve().parent.parent / "rigor"
if str(_RIGOR) not in sys.path:
    sys.path.insert(0, str(_RIGOR))

from rigor import Estimate, proportion_estimate, share_of_voice_ci  # noqa: E402


# --------------------------------------------------------------------------- #
# Input record: one engine answer to one prompt
# --------------------------------------------------------------------------- #
@dataclass
class RunRecord:
    """One immutable engine answer (mirrors a `runs` row + its citations)."""

    prompt_id: int
    engine: str
    answer_text: str = ""
    cited_domains: tuple[str, ...] = ()  # normalized domains, in citation order


# --------------------------------------------------------------------------- #
# Domain / brand matching helpers
# --------------------------------------------------------------------------- #
def domain_matches(domain: str | None, targets: Sequence[str]) -> bool:
    """True if `domain` equals or is a subdomain of any target (normalized)."""
    if not domain:
        return False
    d = domain.lower().lstrip(".")
    for t in targets:
        t = (t or "").lower().lstrip(".")
        if not t:
            continue
        if d == t or d.endswith("." + t):
            return True
    return False


def detect_mention(text: str, aliases: Sequence[str]) -> tuple[bool, int | None]:
    """Word-boundary, case-insensitive brand detection.

    Returns (found, first_char_offset). Aliases are regex-escaped so brand names
    with dots/spaces (e.g. "Monday.com") match literally. The earliest offset
    across all aliases is returned (feeds position/Princeton weighting, R2.4).
    """
    best: int | None = None
    for alias in aliases:
        alias = (alias or "").strip()
        if not alias:
            continue
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m and (best is None or m.start() < best):
            best = m.start()
    return (best is not None, best)


# --------------------------------------------------------------------------- #
# Rate metrics (Bernoulli per run -> Wilson CI)
# --------------------------------------------------------------------------- #
def mention_estimate(
    records: Sequence[RunRecord], aliases: Sequence[str], *, confidence: float = 0.95
) -> Estimate:
    """Mention rate (R2.1): fraction of runs naming the brand, with a Wilson CI."""
    n = len(records)
    hits = sum(1 for r in records if detect_mention(r.answer_text, aliases)[0])
    return proportion_estimate(hits, n, confidence)


def citation_estimate(
    records: Sequence[RunRecord], target_domains: Sequence[str], *,
    confidence: float = 0.95,
) -> Estimate:
    """Citation rate (R2.2): fraction of runs citing the target domain, Wilson CI."""
    n = len(records)
    hits = sum(1 for r in records
               if any(domain_matches(d, target_domains) for d in r.cited_domains))
    return proportion_estimate(hits, n, confidence)


def share_of_voice(
    records: Sequence[RunRecord], target_domains: Sequence[str],
    competitor_domains: Sequence[str], *, confidence: float = 0.95,
    n_boot: int = 5000, seed: int = 0,
) -> Estimate:
    """Share of Voice (R2.3): target citations / (target+competitor) citations.

    Clustered by prompt (all repeats of a prompt share retrieval context), so the
    CI is a cluster bootstrap over prompts — matching how the rigor POC handles
    correlated GEO non-determinism. Universe = target domains + competitor domains.
    """
    universe = list(target_domains) + list(competitor_domains)
    per_prompt: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # [target, total]
    for r in records:
        for d in r.cited_domains:
            if domain_matches(d, universe):
                per_prompt[r.prompt_id][1] += 1
                if domain_matches(d, target_domains):
                    per_prompt[r.prompt_id][0] += 1
    counts = [(v[0], v[1]) for v in per_prompt.values()]
    return share_of_voice_ci(counts, n_boot=n_boot, confidence=confidence, seed=seed)


# --------------------------------------------------------------------------- #
# Position (R2.4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PositionSummary:
    n_cited: int          # runs that cited the target at all
    mean_rank: float | None       # mean 1-based citation position when cited
    mean_first_offset: float | None  # mean first-mention char offset when mentioned


def position_summary(
    records: Sequence[RunRecord], target_domains: Sequence[str],
    aliases: Sequence[str] = (),
) -> PositionSummary:
    """Citation rank + first-mention offset (lower = more prominent)."""
    ranks: list[int] = []
    offsets: list[int] = []
    for r in records:
        for i, d in enumerate(r.cited_domains, start=1):
            if domain_matches(d, target_domains):
                ranks.append(i)
                break
        if aliases:
            found, off = detect_mention(r.answer_text, aliases)
            if found and off is not None:
                offsets.append(off)
    return PositionSummary(
        n_cited=len(ranks),
        mean_rank=(sum(ranks) / len(ranks)) if ranks else None,
        mean_first_offset=(sum(offsets) / len(offsets)) if offsets else None,
    )


# --------------------------------------------------------------------------- #
# Sentiment (R2.5): LLM-as-judge, validated with Cohen's kappa
# --------------------------------------------------------------------------- #
SENTIMENTS = ("positive", "neutral", "negative")


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float:
    """Cohen's kappa for two raters over the same items (categorical agreement).

    Corrects raw agreement for the agreement expected by chance. 1.0 = perfect,
    0.0 = chance-level, <0 = worse than chance. Used to prove the LLM sentiment
    judge actually tracks a human gold set before any score is trusted.
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("label sequences must be the same length")
    n = len(labels_a)
    if n == 0:
        raise ValueError("need at least one labeled item")
    cats = set(labels_a) | set(labels_b)
    po = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b) / n
    pe = 0.0
    for c in cats:
        pa = sum(1 for x in labels_a if x == c) / n
        pb = sum(1 for x in labels_b if x == c) / n
        pe += pa * pb
    if pe >= 1.0:  # both raters used a single identical category
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


@dataclass
class SentimentReport:
    kappa: float
    raw_agreement: float
    n: int
    trustworthy: bool  # kappa >= 0.6 (substantial agreement) by convention


def sentiment_kappa_report(
    gold: Sequence[str], predicted: Sequence[str], *, threshold: float = 0.6
) -> SentimentReport:
    """Validate an LLM sentiment judge against a hand-labeled gold set (R2.5)."""
    n = len(gold)
    if n != len(predicted):
        raise ValueError("gold and predicted must be the same length")
    kappa = cohen_kappa(gold, predicted)
    raw = sum(1 for g, p in zip(gold, predicted, strict=True) if g == p) / n if n else 0.0
    return SentimentReport(kappa=kappa, raw_agreement=raw, n=n,
                           trustworthy=kappa >= threshold)


def judge_sentiments(
    records: Sequence[RunRecord], brand: str,
    judge: Callable[[str, str], str],
) -> list[str]:
    """Apply an injected sentiment judge to each run's answer text (R2.5).

    `judge(answer_text, brand) -> one of SENTIMENTS`. Kept injectable so the offline
    suite uses a deterministic stub; a live LLM judge plugs in unchanged. Only runs
    whose validation (kappa) passed should have their sentiment trusted downstream.
    """
    out: list[str] = []
    for r in records:
        label = judge(r.answer_text, brand)
        if label not in SENTIMENTS:
            raise ValueError(f"judge returned invalid label {label!r}")
        out.append(label)
    return out


# --------------------------------------------------------------------------- #
# Bundled report
# --------------------------------------------------------------------------- #
@dataclass
class BrandMetrics:
    engine: str
    mention: Estimate
    citation: Estimate
    share_of_voice: Estimate
    position: PositionSummary
    n_runs: int = 0
    extras: dict = field(default_factory=dict)


def compute_brand_metrics(
    records: Sequence[RunRecord], *, aliases: Sequence[str],
    target_domains: Sequence[str], competitor_domains: Sequence[str],
    engine: str = "all", confidence: float = 0.95,
) -> BrandMetrics:
    """One-call bundle of the standard metric set, each with its CI."""
    return BrandMetrics(
        engine=engine,
        mention=mention_estimate(records, aliases, confidence=confidence),
        citation=citation_estimate(records, target_domains, confidence=confidence),
        share_of_voice=share_of_voice(records, target_domains, competitor_domains,
                                      confidence=confidence),
        position=position_summary(records, target_domains, aliases),
        n_runs=len(records),
    )
