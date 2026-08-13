"""Live demo of the safe crawler against a scrape-safe sandbox (Task C1).

Target defaults to books.toscrape.com — a site built for scraping practice, so it
raises zero blocking/ToS concerns. Hard-capped and rate-limited. Run:

    uv run python pocs/crawler/demo.py
"""

from __future__ import annotations

import os

from crawler import DEFAULT_UA, PoliteFetcher, crawl

TARGET = os.getenv("CRAWLER_TARGET", "https://books.toscrape.com/")
MAX_PAGES = int(os.getenv("CRAWLER_MAX_PAGES", "4"))
DELAY = float(os.getenv("CRAWLER_DELAY_SECONDS", "1.5"))


def main() -> None:
    print(f"Crawling {TARGET}  (max_pages={MAX_PAGES}, delay={DELAY}s, robots respected)\n")
    fetcher = PoliteFetcher(user_agent=DEFAULT_UA, delay=DELAY, max_pages=MAX_PAGES)
    records = crawl(TARGET, fetcher, respect_robots=True)
    for r in records:
        a = r.audit
        print(f"[{r.result.status}] {r.result.url}")
        print(
            f"    AI-readability={a.ai_readability_score:.2f} | "
            f"words={a.word_count} | H1={a.h1_count} | "
            f"stat_density={a.statistic_density:.1f}/100w | schema={a.schema_types or 'none'}"
        )
    print(f"\nFetched {len(records)} page(s); fetcher stopped at count={fetcher.count}.")


if __name__ == "__main__":
    main()
