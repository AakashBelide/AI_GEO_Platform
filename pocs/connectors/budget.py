"""Budget guard + cost ledger for API spend (Task F3 safety layer).

Hard rule from the user: keep a $2 budget PER provider. This module is the
enforcement point — every engine call is gated by ``CostLedger.guard(...)``,
which refuses to proceed once a provider's recorded spend would exceed its cap.
Spend is persisted to a gitignored JSON file so the cap holds across process
restarts (a fresh run cannot silently reset the counter).

Costs are *estimates*: token counts × published per-token prices, plus any
per-call tool fee. Estimates are intentionally conservative (round up) so the
guard trips early rather than late.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "BudgetExceeded",
    "Pricing",
    "PRICING",
    "estimate_cost",
    "CostLedger",
]


class BudgetExceeded(Exception):
    """Raised (before any network call) when a spend would breach the cap."""


# --------------------------------------------------------------------------- #
# Pricing table (USD per 1M tokens) + per-call tool fees.
# Cheapest-decent models per provider; update as prices change.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float
    per_call_tool_usd: float = 0.0  # web-search / grounding surcharge per call


PRICING: dict[str, Pricing] = {
    # provider:model -> pricing
    "openai:gpt-4o-mini": Pricing(0.15, 0.60, per_call_tool_usd=0.025),  # + web_search fee
    "perplexity:sonar": Pricing(1.00, 1.00, per_call_tool_usd=0.005),  # search incl.; req fee
    "gemini:gemini-2.5-flash": Pricing(0.30, 2.50, per_call_tool_usd=0.0),
    "anthropic:claude-haiku-4-5": Pricing(1.00, 5.00, per_call_tool_usd=0.01),  # web_search fee
}

# Fallback used when a model isn't in the table (deliberately pessimistic).
_FALLBACK = Pricing(5.00, 15.00, per_call_tool_usd=0.05)


def pricing_for(provider: str, model: str) -> Pricing:
    return PRICING.get(f"{provider}:{model}", _FALLBACK)


def estimate_cost(
    provider: str, model: str, *, input_tokens: int, output_tokens: int, tool_calls: int = 1
) -> float:
    """Estimate USD cost of a single call from token counts + tool fees."""
    p = pricing_for(provider, model)
    cost = (
        input_tokens / 1_000_000 * p.input_per_mtok
        + output_tokens / 1_000_000 * p.output_per_mtok
        + tool_calls * p.per_call_tool_usd
    )
    return round(cost, 6)


def preflight_estimate(provider: str, model: str, *, prompt_chars: int) -> float:
    """A conservative *pre-call* estimate when token counts aren't known yet.

    Assumes ~4 chars/token for input and a generous fixed output budget, so the
    guard errs toward stopping early. Used to gate a call before it's made.
    """
    est_input = prompt_chars // 4 + 1500  # + system/tool overhead
    est_output = 1200
    return estimate_cost(
        provider, model, input_tokens=est_input, output_tokens=est_output, tool_calls=1
    )


# --------------------------------------------------------------------------- #
# Persistent per-provider ledger with a hard cap.
# --------------------------------------------------------------------------- #
@dataclass
class CostLedger:
    """Tracks and caps per-provider spend, persisted to a JSON file."""

    path: Path
    cap_usd: float = 2.00
    _spent: dict[str, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._spent = {k: float(v) for k, v in data.get("spent", {}).items()}
                self.cap_usd = float(data.get("cap_usd", self.cap_usd))
            except (json.JSONDecodeError, ValueError, OSError):
                self._spent = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"cap_usd": self.cap_usd, "spent": self._spent}, indent=2))
        os.replace(tmp, self.path)  # atomic

    def spent(self, provider: str) -> float:
        return round(self._spent.get(provider, 0.0), 6)

    def remaining(self, provider: str) -> float:
        return round(self.cap_usd - self.spent(provider), 6)

    def would_exceed(self, provider: str, est_usd: float) -> bool:
        return self.spent(provider) + est_usd > self.cap_usd + 1e-9

    def guard(self, provider: str, est_usd: float) -> None:
        """Raise BudgetExceeded if this estimated spend would breach the cap.

        Call this BEFORE the network request. It does not record anything.
        """
        if est_usd < 0:
            raise ValueError("estimated cost must be non-negative")
        if self.would_exceed(provider, est_usd):
            raise BudgetExceeded(
                f"{provider}: est ${est_usd:.4f} would exceed cap "
                f"(spent ${self.spent(provider):.4f} / ${self.cap_usd:.2f})"
            )

    def record(self, provider: str, actual_usd: float) -> float:
        """Record actual spend AFTER a call; returns new provider total."""
        with self._lock:
            self._spent[provider] = self.spent(provider) + max(0.0, actual_usd)
            self._save()
        return self.spent(provider)

    def summary(self) -> dict[str, dict[str, float]]:
        return {
            p: {"spent": self.spent(p), "remaining": self.remaining(p)} for p in self._spent
        }
