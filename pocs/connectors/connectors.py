"""Cross-engine citation connectors (Task F3).

Four answer engines behind one uniform interface:
  - OpenAI Responses API + `web_search` tool
  - Perplexity Sonar (OpenAI-compatible REST)
  - Gemini + Google Search grounding  (documented PROXY for AI Overviews)
  - Anthropic + web_search tool  (basic `web_search_20250305` variant on Haiku)

Design for cost-safety and testability:
  * Every live call is gated by the CostLedger budget guard (§budget.py) and its
    actual cost is recorded after — a provider can never exceed its $2 cap.
  * Raw payloads are cached to disk so re-analysis never re-calls the API.
  * Citation PARSING is a set of pure functions (`parse_*`) tested offline with
    saved fixtures; the network layer is a thin wrapper exercised only by the
    frugal live smoke test.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from budget import CostLedger, estimate_cost, preflight_estimate


# --------------------------------------------------------------------------- #
# Normalized result types
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Citation:
    url: str | None
    title: str | None
    domain: str | None
    position: int


@dataclass
class EngineResponse:
    engine: str
    model: str
    answer_text: str
    citations: list[Citation] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)

    @property
    def domains(self) -> list[str]:
        return [c.domain for c in self.citations if c.domain]

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)  # keep summary light; raw is persisted separately
        return d


def normalize_domain(url: str | None) -> str | None:
    """Lowercase host with a leading 'www.' stripped (conservative canonical)."""
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    if not host and "//" not in url:  # bare domain passed in
        host = urlparse("//" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


def _first(d: dict, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return None


# --------------------------------------------------------------------------- #
# Pure parsers (offline-testable). Each takes the provider's raw payload dict.
# --------------------------------------------------------------------------- #
def parse_openai(raw: dict) -> tuple[str, list[Citation]]:
    """OpenAI Responses API: url_citation annotations on output_text blocks."""
    text_parts: list[str] = []
    citations: list[Citation] = []
    pos = 0
    for item in raw.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for block in item.get("content", []) or []:
            if block.get("type") in ("output_text", "text"):
                text_parts.append(block.get("text", ""))
                for ann in block.get("annotations", []) or []:
                    if ann.get("type") == "url_citation":
                        pos += 1
                        url = ann.get("url")
                        citations.append(Citation(url, ann.get("title"),
                                                  normalize_domain(url), pos))
    return "".join(text_parts), citations


def parse_perplexity(raw: dict) -> tuple[str, list[Citation]]:
    """Perplexity Sonar: search_results[] (preferred) or citations[] URLs."""
    answer = ""
    choices = raw.get("choices") or []
    if choices:
        answer = (choices[0].get("message") or {}).get("content", "") or ""
    citations: list[Citation] = []
    results = raw.get("search_results")
    if results:
        for i, r in enumerate(results, start=1):
            url = r.get("url")
            citations.append(Citation(url, r.get("title"), normalize_domain(url), i))
    else:
        for i, url in enumerate(raw.get("citations") or [], start=1):
            citations.append(Citation(url, None, normalize_domain(url), i))
    return answer, citations


def parse_gemini(raw: dict) -> tuple[str, list[Citation]]:
    """Gemini grounding: groundingChunks[].web.{uri,title}. Handles snake/camel."""
    candidates = raw.get("candidates") or []
    if not candidates:
        return "", []
    cand = candidates[0]
    content = cand.get("content") or {}
    parts = content.get("parts") or []
    answer = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p)

    gm = _first(cand, "groundingMetadata", "grounding_metadata") or {}
    chunks = _first(gm, "groundingChunks", "grounding_chunks") or []
    citations: list[Citation] = []
    for i, ch in enumerate(chunks, start=1):
        web = (ch or {}).get("web") or {}
        url = _first(web, "uri", "url")
        citations.append(Citation(url, web.get("title"), normalize_domain(url), i))
    return answer, citations


def parse_anthropic(raw: dict) -> tuple[str, list[Citation]]:
    """Anthropic: text blocks + web_search_tool_result blocks (web_search_result)."""
    text_parts: list[str] = []
    citations: list[Citation] = []
    pos = 0
    for block in raw.get("content", []) or []:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "web_search_tool_result":
            for r in block.get("content", []) or []:
                if isinstance(r, dict) and r.get("type") == "web_search_result":
                    pos += 1
                    url = r.get("url")
                    citations.append(Citation(url, r.get("title"),
                                              normalize_domain(url), pos))
    return "".join(text_parts), citations


def usage_from_raw(provider: str, raw: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a provider payload."""
    if provider == "openai":
        u = raw.get("usage") or {}
        return int(_first(u, "input_tokens") or 0), int(_first(u, "output_tokens") or 0)
    if provider == "perplexity":
        u = raw.get("usage") or {}
        return int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
    if provider == "gemini":
        u = _first(raw, "usageMetadata", "usage_metadata") or {}
        return (int(_first(u, "promptTokenCount", "prompt_token_count") or 0),
                int(_first(u, "candidatesTokenCount", "candidates_token_count") or 0))
    if provider == "anthropic":
        u = raw.get("usage") or {}
        return int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    return 0, 0


_PARSERS = {
    "openai": parse_openai,
    "perplexity": parse_perplexity,
    "gemini": parse_gemini,
    "anthropic": parse_anthropic,
}


# --------------------------------------------------------------------------- #
# Budget-gated adapter base (network call is the one method subclasses override)
# --------------------------------------------------------------------------- #
@dataclass
class Engine:
    provider: str
    model: str
    ledger: CostLedger
    cache_dir: Path = Path("data/cache")

    def _raw_call(self, prompt: str) -> dict:  # pragma: no cover - overridden/live
        raise NotImplementedError

    def _cache_path(self, prompt: str, run_index: int) -> Path:
        key = f"{self.provider}|{self.model}|{run_index}|{prompt}".encode()
        h = hashlib.sha256(key).hexdigest()[:16]
        return self.cache_dir / self.provider / f"{h}.json"

    def query(self, prompt: str, *, run_index: int = 0) -> EngineResponse:
        """Guard budget → live call → parse → record spend → cache raw."""
        est = preflight_estimate(self.provider, self.model, prompt_chars=len(prompt))
        self.ledger.guard(self.provider, est)  # raises BudgetExceeded if over cap

        raw = self._raw_call(prompt)

        answer, citations = _PARSERS[self.provider](raw)
        tin, tout = usage_from_raw(self.provider, raw)
        cost = estimate_cost(self.provider, self.model, input_tokens=tin,
                             output_tokens=tout, tool_calls=1)
        self.ledger.record(self.provider, cost)

        path = self._cache_path(prompt, run_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))

        return EngineResponse(self.provider, self.model, answer, citations,
                              tin, tout, cost, raw)


# --------------------------------------------------------------------------- #
# Live adapters (thin network wrappers; not exercised by the offline suite)
# --------------------------------------------------------------------------- #
class OpenAIEngine(Engine):  # pragma: no cover - live
    def _raw_call(self, prompt: str) -> dict:
        from openai import OpenAI

        client = OpenAI()
        resp = client.responses.create(
            model=self.model, tools=[{"type": "web_search"}], input=prompt)
        return resp.model_dump()


class PerplexityEngine(Engine):  # pragma: no cover - live
    def _raw_call(self, prompt: str) -> dict:
        import os

        import httpx

        r = httpx.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()


class GeminiEngine(Engine):  # pragma: no cover - live
    def _raw_call(self, prompt: str) -> dict:
        import os

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]),
        )
        return resp.model_dump()


class AnthropicEngine(Engine):  # pragma: no cover - live
    def _raw_call(self, prompt: str) -> dict:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model, max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.model_dump()


ENGINES = {
    "openai": OpenAIEngine,
    "perplexity": PerplexityEngine,
    "gemini": GeminiEngine,
    "anthropic": AnthropicEngine,
}
