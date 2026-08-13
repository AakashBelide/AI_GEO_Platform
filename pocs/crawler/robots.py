"""robots.txt parsing + AI-bot access reporting (Task C1).

Two complementary checks (addressing the Otterly caveat that a user-agent probe
alone is not a policy audit):
  1. robots.txt *policy* parse — what the site declares for each bot UA.
  2. (live, optional) UA *response* probe — what the server actually returns.

This module implements (1) fully offline; (2) lives in ``crawler.py`` and is only
used against safe sandbox targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

# AI crawler user-agents worth auditing (subset; extend as needed).
AI_BOTS: tuple[str, ...] = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "Googlebot",
)


@dataclass(frozen=True)
class RobotsPolicy:
    """Wraps a parsed robots.txt so we can query it per user-agent."""

    _parser: RobotFileParser

    @classmethod
    def from_string(cls, content: str) -> RobotsPolicy:
        rp = RobotFileParser()
        rp.parse(content.splitlines())
        return cls(rp)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        return self._parser.can_fetch(user_agent, url)

    def crawl_delay(self, user_agent: str) -> float | None:
        try:
            d = self._parser.crawl_delay(user_agent)
        except Exception:
            return None
        return float(d) if d is not None else None


def bot_access_report(
    robots_txt: str, base_url: str, paths: list[str], bots: tuple[str, ...] = AI_BOTS
) -> dict[str, dict[str, bool]]:
    """For each bot UA, report allow/deny on each path per the robots.txt policy.

    Returns ``{bot: {path: allowed_bool}}``. Purely a policy read — no requests.
    """
    policy = RobotsPolicy.from_string(robots_txt)
    report: dict[str, dict[str, bool]] = {}
    for bot in bots:
        report[bot] = {p: policy.can_fetch(bot, urljoin(base_url, p)) for p in paths}
    return report


def same_registrable_site(url_a: str, url_b: str) -> bool:
    """True if two URLs share the same host (conservative same-site check)."""
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()
