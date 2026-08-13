"""Per-page AI-readability audit (Task C1.4).

Scores the *proven* levers from RESEARCH.md §2.2 that make a page extractable and
citable by AI answer engines: clean structure, statistic density, schema presence,
title/meta quality. Deterministic parse — no network, no LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

_STAT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?%|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?\b")


@dataclass
class PageAudit:
    url: str
    title: str | None
    title_len_ok: bool
    meta_description_present: bool
    h1_count: int
    heading_structure_score: float  # 0..1
    word_count: int
    statistic_density: float  # numeric tokens per 100 words
    json_ld_present: bool
    schema_types: list[str] = field(default_factory=list)
    readability_score: float = 0.0  # 0..1 heuristic
    ai_readability_score: float = 0.0  # 0..1 overall

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def _heading_structure_score(soup: BeautifulSoup) -> tuple[int, float]:
    h1 = soup.find_all("h1")
    h2 = soup.find_all("h2")
    h3 = soup.find_all("h3")
    score = 0.0
    if len(h1) == 1:  # exactly one H1 is ideal
        score += 0.5
    elif len(h1) >= 1:
        score += 0.2
    if h2:
        score += 0.3
    if h3 and h2:  # hierarchy present
        score += 0.2
    return len(h1), min(1.0, score)


def _extract_schema_types(soup: BeautifulSoup) -> tuple[bool, list[str]]:
    types: list[str] = []
    blocks = soup.find_all("script", attrs={"type": "application/ld+json"})
    for b in blocks:
        try:
            data = json.loads(b.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict) and "@type" in obj:
                t = obj["@type"]
                types.extend(t if isinstance(t, list) else [t])
    return bool(blocks), types


def audit_html(html: str, url: str = "") -> PageAudit:
    """Run the full AI-readability audit on a page's raw HTML string."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else None
    title_len_ok = bool(title) and 10 <= len(title) <= 70

    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_present = bool(meta_desc and meta_desc.get("content", "").strip())

    h1_count, heading_score = _heading_structure_score(soup)

    # Extract schema BEFORE _visible_text (which decomposes <script> tags).
    json_ld, schema_types = _extract_schema_types(soup)

    text = _visible_text(soup)
    words = text.split()
    word_count = len(words)
    stat_tokens = len(_STAT_RE.findall(text))
    statistic_density = (stat_tokens / word_count * 100) if word_count else 0.0

    # crude readability proxy: reward substantive but not bloated pages
    readability = 1.0 if 150 <= word_count <= 3000 else (0.5 if word_count else 0.0)

    # overall AI-readability: weighted blend of the proven levers
    overall = (
        0.30 * heading_score
        + 0.20 * (1.0 if title_len_ok else 0.0)
        + 0.10 * (1.0 if meta_present else 0.0)
        + 0.20 * min(1.0, statistic_density / 3.0)  # ~3 stats/100w saturates
        + 0.10 * (1.0 if json_ld else 0.0)
        + 0.10 * readability
    )

    return PageAudit(
        url=url,
        title=title,
        title_len_ok=title_len_ok,
        meta_description_present=meta_present,
        h1_count=h1_count,
        heading_structure_score=round(heading_score, 3),
        word_count=word_count,
        statistic_density=round(statistic_density, 3),
        json_ld_present=json_ld,
        schema_types=schema_types,
        readability_score=round(readability, 3),
        ai_readability_score=round(min(1.0, overall), 3),
    )


def js_buried_ratio(raw_html: str, rendered_html: str) -> float:
    """Fraction of visible text present only after JS rendering (Scrunch-style).

    0.0 = all content in raw HTML (great for AI bots that don't run JS);
    →1.0 = content is JS-injected (bad — many AI crawlers won't see it).
    Requires a rendered DOM (optional Playwright step); tested here with fixtures.
    """
    raw_len = len(_visible_text(BeautifulSoup(raw_html, "html.parser")).split())
    rendered_len = len(_visible_text(BeautifulSoup(rendered_html, "html.parser")).split())
    if rendered_len == 0:
        return 0.0
    return max(0.0, (rendered_len - raw_len) / rendered_len)
