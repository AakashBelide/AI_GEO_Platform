"""Onboarding: brand -> auto-generated, intent-labeled, skew-checked prompt set (Task R1).

Industry-standard GEO onboarding (Otterly/Semrush/Profound) turns a brand into a
tracked set of prompts. The *reusable* pattern is the UX; the honesty this project
adds is the two guards competitors skip:

  * **Branded-query skew guard (R1.3).** A prompt set dominated by "{brand} reviews"
    style queries inflates visibility numbers — the brand is in the question, so of
    course it's in the answer. We enforce a ceiling on the branded ratio and flag it.
  * **Intent distribution (R1.4).** We label every prompt informational / commercial /
    navigational and target an 80/10/10 split (RESEARCH.md §5.2), so the tracked set
    reflects real discovery, not just people already searching the brand by name.

The generator is **pure and deterministic** (template-driven), so the whole suite runs
offline. An optional LLM-drafting step (R1.2c) is injectable — a `Callable` the caller
supplies — and is never invoked by the tests.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import cycle, islice

INTENTS = ("informational", "commercial", "navigational")

# Target discovery mix (RESEARCH.md §5.2): mostly unbranded/category discovery.
DEFAULT_INTENT_MIX = {"informational": 0.8, "commercial": 0.1, "navigational": 0.1}

# A prompt set should not be dominated by queries that name the brand (skew).
DEFAULT_MAX_BRANDED_RATIO = 0.30


# --------------------------------------------------------------------------- #
# Inputs / outputs
# --------------------------------------------------------------------------- #
@dataclass
class BrandProfile:
    """What we track: the brand, how it's named, and who it competes with."""

    name: str
    category: str
    domain: str | None = None
    aliases: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("brand name is required")
        if not self.category or not self.category.strip():
            raise ValueError("brand category is required")

    def all_names(self) -> list[str]:
        """Brand name + aliases, de-duplicated, for mention detection (feeds R2)."""
        seen: list[str] = []
        for n in (self.name, *self.aliases):
            if n and n not in seen:
                seen.append(n)
        return seen


@dataclass(frozen=True)
class Prompt:
    """One tracked query, labeled with intent and whether it names the brand."""

    text: str
    intent: str
    branded: bool
    category: str
    paraphrase_of: str | None = None


@dataclass(frozen=True)
class SkewReport:
    branded: int
    total: int
    branded_ratio: float
    max_branded_ratio: float
    ok: bool
    message: str


# --------------------------------------------------------------------------- #
# Template pools. `{category}` = unbranded discovery; `{brand}` = branded.
# --------------------------------------------------------------------------- #
_INFORMATIONAL = [
    "What is the best {category}?",
    "What are the top {category} in {year}?",
    "Which {category} should a small team choose?",
    "Compare the leading {category}.",
    "What features matter most when picking {category}?",
    "What are good alternatives in {category}?",
    "How do I evaluate {category}?",
    "What is the most popular {category} right now?",
]

_COMMERCIAL_UNBRANDED = [
    "Best {category} for {use_case}",
    "Most affordable {category} for {use_case}",
    "{category} pricing compared for {use_case}",
]

_COMMERCIAL_BRANDED = [
    "Is {brand} or {competitor} better for {use_case}?",
    "{brand} vs {competitor} pricing",
]

_NAVIGATIONAL_BRANDED = [
    "What is {brand}?",
    "{brand} reviews",
    "{brand} vs {competitor}",
    "Is {brand} any good?",
]


def _fill(template: str, profile: BrandProfile, *, competitor: str,
          use_case: str, year: int) -> str:
    return template.format(
        category=profile.category, brand=profile.name,
        competitor=competitor, use_case=use_case, year=year,
    )


def _rotate(values: Iterable[str], fallback: str) -> cycle[str]:
    vals = [v for v in values if v] or [fallback]
    return cycle(vals)


def _emit(templates: list[str], count: int, *, intent: str, branded: bool,
          profile: BrandProfile, year: int) -> list[Prompt]:
    """Round-robin templates x competitors x use_cases to produce `count` prompts."""
    comps = _rotate(profile.competitors, "the alternatives")
    uses = _rotate(profile.use_cases, "a growing team")
    out: list[Prompt] = []
    for template in islice(cycle(templates), count):
        text = _fill(template, profile, competitor=next(comps),
                     use_case=next(uses), year=year)
        out.append(Prompt(text=text, intent=intent, branded=branded,
                          category=profile.category))
    return out


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate_prompts(
    profile: BrandProfile,
    *,
    n_total: int = 30,
    intent_mix: dict[str, float] | None = None,
    year: int = 2026,
    llm_draft: Callable[[BrandProfile, int], list[str]] | None = None,
) -> list[Prompt]:
    """Deterministically build an intent-labeled prompt set for a brand.

    `intent_mix` fractions are turned into integer counts that sum to `n_total`
    (largest-remainder rounding). Informational prompts are all unbranded;
    commercial is split unbranded/branded; navigational is branded (it names the
    brand by definition). `llm_draft`, if given, supplies extra unbranded
    informational prompts (R1.2c) — never called by the offline tests.
    """
    if n_total <= 0:
        raise ValueError("n_total must be positive")
    mix = intent_mix or DEFAULT_INTENT_MIX
    if abs(sum(mix.values()) - 1.0) > 1e-6:
        raise ValueError("intent_mix must sum to 1.0")
    counts = _largest_remainder(mix, n_total)

    prompts: list[Prompt] = []
    prompts += _emit(_INFORMATIONAL, counts["informational"],
                     intent="informational", branded=False,
                     profile=profile, year=year)

    n_comm = counts["commercial"]
    n_comm_branded = n_comm // 2
    prompts += _emit(_COMMERCIAL_UNBRANDED, n_comm - n_comm_branded,
                     intent="commercial", branded=False, profile=profile, year=year)
    prompts += _emit(_COMMERCIAL_BRANDED, n_comm_branded,
                     intent="commercial", branded=True, profile=profile, year=year)

    prompts += _emit(_NAVIGATIONAL_BRANDED, counts["navigational"],
                     intent="navigational", branded=True, profile=profile, year=year)

    if llm_draft is not None:  # pragma: no cover - injected/live only
        for text in llm_draft(profile, n_total):
            prompts.append(Prompt(text=text, intent="informational",
                                  branded=_names_brand(text, profile),
                                  category=profile.category))
    return prompts


def _largest_remainder(mix: dict[str, float], n_total: int) -> dict[str, int]:
    """Apportion n_total across intents by fraction, remainders to the largest."""
    raw = {k: mix.get(k, 0.0) * n_total for k in INTENTS}
    floors = {k: int(v) for k, v in raw.items()}
    remainder = n_total - sum(floors.values())
    order = sorted(INTENTS, key=lambda k: raw[k] - floors[k], reverse=True)
    for k in order[:remainder]:
        floors[k] += 1
    return floors


def _names_brand(text: str, profile: BrandProfile) -> bool:
    low = text.lower()
    return any(name.lower() in low for name in profile.all_names())


# --------------------------------------------------------------------------- #
# Paraphrase variants (R1.5) — feeds O1's variance-efficiency design
# --------------------------------------------------------------------------- #
_PARAPHRASE_FRAMES = [
    "{q}",
    "Honestly, {q_lower}",
    "In {year}, {q_lower}",
    "I'm researching options — {q_lower}",
]


def paraphrase(prompt: Prompt, n: int = 3, *, year: int = 2026) -> list[Prompt]:
    """Deterministic surface variants of one prompt (same intent/branded/category).

    Variance-components analysis (O1.4) needs multiple *phrasings* of the same
    underlying question to separate paraphrase noise from model/prompt noise.
    Variant 0 is the original; up to `n` extra frames are applied.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    base = prompt.text
    variants: list[Prompt] = []
    for frame in islice(cycle(_PARAPHRASE_FRAMES), n + 1):
        text = frame.format(q=base, q_lower=base[0].lower() + base[1:] if base else base,
                            year=year)
        variants.append(Prompt(text=text, intent=prompt.intent,
                               branded=prompt.branded, category=prompt.category,
                               paraphrase_of=base))
    # de-dup while preserving order (frame 0 == original)
    seen: set[str] = set()
    out: list[Prompt] = []
    for p in variants:
        if p.text not in seen:
            seen.add(p.text)
            out.append(p)
    return out[: n + 1]


# --------------------------------------------------------------------------- #
# Guards (the honesty layer)
# --------------------------------------------------------------------------- #
def branded_ratio(prompts: list[Prompt]) -> float:
    if not prompts:
        return 0.0
    return sum(1 for p in prompts if p.branded) / len(prompts)


def skew_check(
    prompts: list[Prompt], *, max_branded_ratio: float = DEFAULT_MAX_BRANDED_RATIO
) -> SkewReport:
    """Flag a prompt set that is too dominated by brand-naming queries (R1.3)."""
    total = len(prompts)
    branded = sum(1 for p in prompts if p.branded)
    ratio = branded / total if total else 0.0
    ok = ratio <= max_branded_ratio
    if ok:
        msg = (f"OK: {branded}/{total} prompts are branded "
               f"({ratio:.0%} <= {max_branded_ratio:.0%} ceiling).")
    else:
        msg = (f"SKEW: {branded}/{total} prompts name the brand "
               f"({ratio:.0%} > {max_branded_ratio:.0%}); visibility will be inflated. "
               "Add unbranded/category prompts.")
    return SkewReport(branded=branded, total=total, branded_ratio=ratio,
                      max_branded_ratio=max_branded_ratio, ok=ok, message=msg)


def intent_distribution(prompts: list[Prompt]) -> dict[str, dict[str, float]]:
    """Per-intent counts and fractions, for validating the 80/10/10 target."""
    total = len(prompts)
    out: dict[str, dict[str, float]] = {}
    for intent in INTENTS:
        c = sum(1 for p in prompts if p.intent == intent)
        out[intent] = {"count": float(c), "fraction": (c / total if total else 0.0)}
    return out


@dataclass
class PromptSet:
    """A generated prompt set bundled with its honesty checks."""

    profile: BrandProfile
    prompts: list[Prompt] = field(default_factory=list)

    @property
    def skew(self) -> SkewReport:
        return skew_check(self.prompts)

    @property
    def intents(self) -> dict[str, dict[str, float]]:
        return intent_distribution(self.prompts)


def build_prompt_set(profile: BrandProfile, **kwargs) -> PromptSet:
    """Convenience: generate + bundle with guards attached."""
    return PromptSet(profile=profile, prompts=generate_prompts(profile, **kwargs))
