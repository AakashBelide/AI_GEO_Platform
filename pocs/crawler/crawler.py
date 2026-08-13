"""Polite, safety-railed site crawler (Task C1).

SAFETY FIRST. This crawler is for **scrape-safe sandbox targets only**
(default: books.toscrape.com). It always:
  - respects robots.txt,
  - enforces a per-request delay + a hard page cap,
  - stays on the seed host,
  - identifies with an honest custom user-agent.

External I/O (HTTP + sleep + clock) is injected so the whole thing is testable
offline with fixtures and a fake clock — no live crawl runs in the test suite.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse

from audit import PageAudit, audit_html
from bs4 import BeautifulSoup
from robots import RobotsPolicy, same_registrable_site

DEFAULT_UA = "AI_GEO_Research_Bot/0.1 (local; sandbox-only)"


class CrawlLimitReached(Exception):
    """Raised when the configured page cap is hit — a safety stop, not an error."""


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    elapsed: float = 0.0


@dataclass
class CrawlRecord:
    result: FetchResult
    audit: PageAudit


@dataclass
class PoliteFetcher:
    """Rate-limited fetcher. Enforces a minimum delay between requests."""

    user_agent: str = DEFAULT_UA
    delay: float = 1.5
    timeout: float = 10.0
    max_pages: int = 25
    fetch_fn: Callable[[str, str, float], FetchResult] | None = None
    clock: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep
    _last_ts: float | None = field(default=None, init=False, repr=False)
    count: int = field(default=0, init=False)

    def _respect_delay(self) -> None:
        if self._last_ts is not None:
            waited = self.clock() - self._last_ts
            remaining = self.delay - waited
            if remaining > 0:
                self.sleep_fn(remaining)
        self._last_ts = self.clock()

    def fetch(self, url: str) -> FetchResult:
        if self.count >= self.max_pages:
            raise CrawlLimitReached(f"page cap {self.max_pages} reached")
        self._respect_delay()
        fn = self.fetch_fn or _httpx_fetch
        result = fn(url, self.user_agent, self.timeout)
        self.count += 1
        return result


def _httpx_fetch(url: str, user_agent: str, timeout: float) -> FetchResult:  # pragma: no cover
    # Live path — never exercised by the offline test suite.
    import httpx

    started = time.monotonic()
    resp = httpx.get(
        url, headers={"User-Agent": user_agent}, timeout=timeout, follow_redirects=True
    )
    return FetchResult(
        url=str(resp.url),
        status=resp.status_code,
        html=resp.text,
        elapsed=time.monotonic() - started,
    )


def extract_links(html: str, base_url: str) -> list[str]:
    """Same-host http(s) links, absolutised and de-fragmented, order-preserving."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        absolute = urldefrag(urljoin(base_url, a["href"])).url
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if not same_registrable_site(base_url, absolute):
            continue
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out


def crawl(
    seed_url: str,
    fetcher: PoliteFetcher,
    *,
    respect_robots: bool = True,
    robots_txt: str | None = None,
) -> list[CrawlRecord]:
    """BFS crawl within the seed host, obeying robots + delay + page cap."""
    policy: RobotsPolicy | None = None
    if respect_robots:
        if robots_txt is None:
            robots_txt = _try_get_robots(seed_url, fetcher)
        policy = RobotsPolicy.from_string(robots_txt or "")

    queue: deque[str] = deque([seed_url])
    seen: set[str] = {seed_url}
    records: list[CrawlRecord] = []

    while queue:
        url = queue.popleft()
        if policy is not None and not policy.can_fetch(fetcher.user_agent, url):
            continue  # robots disallow — skip, do not fetch
        try:
            result = fetcher.fetch(url)
        except CrawlLimitReached:
            break  # safety cap hit — stop cleanly
        records.append(CrawlRecord(result=result, audit=audit_html(result.html, url)))
        for link in extract_links(result.html, url):
            if link not in seen:
                seen.add(link)
                queue.append(link)
    return records


def _try_get_robots(seed_url: str, fetcher: PoliteFetcher) -> str:  # pragma: no cover
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        return fetcher.fetch(robots_url).html
    except Exception:
        return ""  # no robots.txt → RobotFileParser treats empty as allow-all
