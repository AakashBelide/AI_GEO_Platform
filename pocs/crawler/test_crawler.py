"""Offline tests for the crawler POC (Task C1). Fake clock + fake transport.

NO LIVE CRAWL happens here — every fetch is served from an in-memory fixture site,
so the suite is deterministic, fast, and cannot touch the network or any real IP.
"""

from __future__ import annotations

import pytest
from audit import audit_html, js_buried_ratio
from crawler import (
    CrawlLimitReached,
    FetchResult,
    PoliteFetcher,
    crawl,
    extract_links,
)
from robots import RobotsPolicy, bot_access_report, same_registrable_site

# --------------------------------------------------------------------------- #
# Fixture "site" (served by a fake transport — never hits the network)
# --------------------------------------------------------------------------- #
BASE = "https://sandbox.test"
SITE = {
    f"{BASE}/": """
        <html><head><title>Sandbox Home Page</title>
        <meta name="description" content="A tiny test site."></head>
        <body><h1>Home</h1><h2>Sections</h2>
        <a href="/a.html">A</a><a href="/private/secret.html">secret</a>
        <a href="https://external.example/x">ext</a></body></html>
    """,
    f"{BASE}/a.html": """
        <html><head><title>Page A — Stats and Structure</title></head>
        <body><h1>A</h1><h2>Data</h2>
        <p>Revenue grew 42% to 1,200,000 in 2025, up 3.5 points.</p>
        <script type="application/ld+json">{"@type":"Article","headline":"A"}</script>
        <a href="/b.html">B</a><a href="/">home</a></body></html>
    """,
    f"{BASE}/b.html": """
        <html><head><title>Page B</title></head>
        <body><h1>B</h1><p>Plain page with little of interest.</p></body></html>
    """,
    f"{BASE}/private/secret.html": "<html><body><h1>secret</h1></body></html>",
}


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, secs: float) -> None:
        self.sleeps.append(secs)
        self.t += secs


def fake_fetch(url: str, ua: str, timeout: float) -> FetchResult:
    html = SITE.get(url)
    if html is None:
        return FetchResult(url=url, status=404, html="")
    return FetchResult(url=url, status=200, html=html)


def make_fetcher(clock: FakeClock, **kw) -> PoliteFetcher:
    return PoliteFetcher(
        delay=kw.pop("delay", 1.5),
        max_pages=kw.pop("max_pages", 25),
        fetch_fn=fake_fetch,
        clock=clock,
        sleep_fn=clock.sleep,
        **kw,
    )


# --------------------------------------------------------------------------- #
# robots.txt policy
# --------------------------------------------------------------------------- #
ROBOTS = """
User-agent: *
Disallow: /private/

User-agent: GPTBot
Disallow: /
"""


def test_robots_allows_and_denies_by_path():
    policy = RobotsPolicy.from_string(ROBOTS)
    assert policy.can_fetch("AnyBot", f"{BASE}/a.html")
    assert not policy.can_fetch("AnyBot", f"{BASE}/private/secret.html")


def test_bot_access_report_flags_gptbot_blocked():
    report = bot_access_report(ROBOTS, BASE, ["/", "/a.html"], bots=("GPTBot", "PerplexityBot"))
    assert report["GPTBot"]["/"] is False  # GPTBot disallowed entirely
    assert report["GPTBot"]["/a.html"] is False
    assert report["PerplexityBot"]["/a.html"] is True  # covered by "*", /a.html allowed


def test_same_registrable_site():
    assert same_registrable_site(f"{BASE}/a", f"{BASE}/b")
    assert not same_registrable_site(f"{BASE}/a", "https://external.example/a")


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_audit_rich_page_scores_higher_than_plain():
    rich = audit_html(SITE[f"{BASE}/a.html"], f"{BASE}/a.html")
    plain = audit_html(SITE[f"{BASE}/b.html"], f"{BASE}/b.html")
    assert rich.ai_readability_score > plain.ai_readability_score
    assert rich.json_ld_present and "Article" in rich.schema_types
    assert rich.statistic_density > 0
    assert plain.json_ld_present is False


def test_audit_title_length_flag():
    a = audit_html("<html><head><title>Good descriptive title here</title></head><body>"
                   "<h1>x</h1></body></html>")
    assert a.title_len_ok is True
    short = audit_html("<html><head><title>Hi</title></head><body></body></html>")
    assert short.title_len_ok is False


def test_js_buried_ratio():
    raw = "<html><body><p>one two three</p></body></html>"
    rendered = "<html><body><p>one two three</p><p>four five six seven</p></body></html>"
    ratio = js_buried_ratio(raw, rendered)
    assert ratio == pytest.approx(4 / 7, abs=1e-6)  # 4 of 7 words were JS-injected
    assert js_buried_ratio(raw, raw) == 0.0


# --------------------------------------------------------------------------- #
# Link extraction
# --------------------------------------------------------------------------- #
def test_extract_links_same_site_only():
    links = extract_links(SITE[f"{BASE}/"], BASE + "/")
    assert f"{BASE}/a.html" in links
    assert f"{BASE}/private/secret.html" in links
    assert all("external.example" not in link for link in links)  # external dropped


# --------------------------------------------------------------------------- #
# Rate limiting + page cap (safety rails)
# --------------------------------------------------------------------------- #
def test_fetcher_enforces_delay_between_requests():
    clock = FakeClock()
    f = make_fetcher(clock, delay=1.5)
    f.fetch(f"{BASE}/")       # first: no wait
    f.fetch(f"{BASE}/a.html")  # second: must wait full delay
    f.fetch(f"{BASE}/b.html")  # third: must wait full delay
    assert clock.sleeps == [1.5, 1.5]


def test_fetcher_enforces_page_cap():
    clock = FakeClock()
    f = make_fetcher(clock, delay=0.0, max_pages=2)
    f.fetch(f"{BASE}/")
    f.fetch(f"{BASE}/a.html")
    with pytest.raises(CrawlLimitReached):
        f.fetch(f"{BASE}/b.html")


# --------------------------------------------------------------------------- #
# Full crawl (obeys robots, cap, stays on-site)
# --------------------------------------------------------------------------- #
def test_crawl_respects_robots_disallow():
    clock = FakeClock()
    f = make_fetcher(clock, delay=0.0)
    records = crawl(f"{BASE}/", f, respect_robots=True, robots_txt=ROBOTS)
    urls = {r.result.url for r in records}
    assert f"{BASE}/private/secret.html" not in urls  # robots-disallowed, never fetched
    assert f"{BASE}/a.html" in urls and f"{BASE}/b.html" in urls


def test_crawl_respects_page_cap():
    clock = FakeClock()
    f = make_fetcher(clock, delay=0.0, max_pages=2)
    records = crawl(f"{BASE}/", f, respect_robots=True, robots_txt=ROBOTS)
    assert len(records) == 2  # stops cleanly at the cap


def test_crawl_stays_on_host_and_audits():
    clock = FakeClock()
    f = make_fetcher(clock, delay=0.0)
    records = crawl(f"{BASE}/", f, respect_robots=False)
    urls = {r.result.url for r in records}
    assert all(u.startswith(BASE) for u in urls)  # never left the sandbox host
    assert all(r.audit is not None for r in records)
