"""Keyword -> prompt conversion / bootstrapping (Task R3).

The cheap seeding trick every SEO-adjacent GEO tool uses (Otterly/Semrush): take an
existing keyword list and wrap each keyword in a natural-language question, then merge
it into the R1 prompt set. Deterministic and offline — no keys.

Two honest details:
  * **Intent is inferred from keyword modifiers**, not guessed by an LLM: commercial
    modifiers ("best", "pricing", "vs", "review", ...) -> commercial; brand-name in the
    keyword -> navigational (or commercial for "{brand} vs"); everything else ->
    informational. This keeps the R1 intent labels meaningful (R1.4 / skew guard R1.3).
  * **Merging de-duplicates** against the existing set on a normalized form (casefold,
    trimmed, trailing punctuation/whitespace collapsed), so keyword-derived prompts never
    double-count ones the R1 generator already produced.

Reuses `pocs/onboarding` (`Prompt`, `BrandProfile`) via the POC path shim below; the app/
package will import these normally once integrated.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path

# POC path shim: reuse the sibling onboarding POC's types without duplicating them.
_ONBOARDING = Path(__file__).resolve().parent.parent / "onboarding"
if str(_ONBOARDING) not in sys.path:
    sys.path.insert(0, str(_ONBOARDING))

from onboarding import BrandProfile, Prompt  # noqa: E402

# Modifiers that signal buying/comparison intent (commercial).
COMMERCIAL_MODIFIERS = frozenset({
    "best", "top", "cheap", "cheapest", "affordable", "price", "pricing", "cost",
    "deal", "deals", "discount", "vs", "versus", "comparison", "compare", "review",
    "reviews", "alternative", "alternatives", "buy",
})

# Question frames per intent (frame[0] is the primary; extras give paraphrase breadth).
_FRAMES = {
    "informational": [
        "What is {kw}?",
        "Tell me about {kw}.",
        "What should I know about {kw}?",
    ],
    "commercial": [
        "What is the best {kw}?",
        "Compare options for {kw}.",
        "Which {kw} would you recommend?",
    ],
    "navigational": [
        "Tell me about {kw}.",
        "What is {kw}?",
    ],
}

_WORD = re.compile(r"[a-z0-9.]+")


def _tokens(keyword: str) -> list[str]:
    return _WORD.findall(keyword.lower())


def _names_brand(keyword: str, profile: BrandProfile | None) -> bool:
    if profile is None:
        return False
    low = keyword.lower()
    return any(name.lower() in low for name in profile.all_names())


def classify_keyword(keyword: str, profile: BrandProfile | None = None) -> tuple[str, bool]:
    """Return (intent, branded) for a keyword from its modifiers + brand match.

    Rules (checked in order):
      * branded + a comparison/commercial modifier -> ("commercial", True)
      * branded (no modifier)                      -> ("navigational", True)
      * has a commercial modifier                  -> ("commercial", False)
      * otherwise                                  -> ("informational", False)
    """
    branded = _names_brand(keyword, profile)
    toks = set(_tokens(keyword))
    has_commercial = bool(toks & COMMERCIAL_MODIFIERS)
    if branded and has_commercial:
        return "commercial", True
    if branded:
        return "navigational", True
    if has_commercial:
        return "commercial", False
    return "informational", False


def keyword_to_prompts(
    keyword: str, profile: BrandProfile | None = None, *, max_variants: int = 1,
) -> list[Prompt]:
    """Turn one keyword into up to `max_variants` intent-labeled prompts."""
    kw = keyword.strip()
    if not kw:
        return []
    if max_variants < 1:
        raise ValueError("max_variants must be >= 1")
    intent, branded = classify_keyword(kw, profile)
    category = profile.category if profile is not None else kw
    frames = _FRAMES[intent]
    out: list[Prompt] = []
    for frame in frames[:max_variants]:
        out.append(Prompt(text=frame.format(kw=kw), intent=intent,
                          branded=branded, category=category))
    return out


def _norm(text: str) -> str:
    """Normalized key for de-duplication: casefold, collapse ws, strip trailing punct."""
    return re.sub(r"\s+", " ", text.strip().casefold()).rstrip(" ?.!")


def keywords_to_prompts(
    keywords: Sequence[str], profile: BrandProfile | None = None, *, max_variants: int = 1,
) -> list[Prompt]:
    """Convert a keyword list to deduped, intent-labeled prompts (no existing set)."""
    return merge_keyword_prompts([], keywords, profile, max_variants=max_variants)


def merge_keyword_prompts(
    existing: Sequence[Prompt], keywords: Sequence[str],
    profile: BrandProfile | None = None, *, max_variants: int = 1,
) -> list[Prompt]:
    """Append keyword-derived prompts to an R1 set, de-duplicating on normalized text.

    Order is preserved: the existing set first, then new keyword prompts in input order.
    A keyword prompt whose normalized text already appears (in `existing` or earlier in
    this batch) is dropped.
    """
    seen: set[str] = {_norm(p.text) for p in existing}
    out: list[Prompt] = list(existing)
    for kw in keywords:
        for p in keyword_to_prompts(kw, profile, max_variants=max_variants):
            key = _norm(p.text)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out
