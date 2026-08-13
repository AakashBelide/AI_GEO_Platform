# POC: `crawler` — safe site crawler + AI-readability audit (Task C1 / §7.3)

A small, **safety-railed** crawler that scans a site the way an AI bot would and audits each
page for the *proven* citability levers (structure, statistic density, schema, title/meta).
This is the §7.3 "try whole-site crawling locally" task — a learning exercise, not a
production crawler.

## ⚠️ Safety (non-negotiable)
- **Sandbox targets only** — default `books.toscrape.com` (built for scraping practice; zero
  ToS/blocking risk). Also fine: `quotes.toscrape.com`.
- **Respects `robots.txt`**, enforces a per-request **delay**, a hard **page cap**, single
  concurrency, stays on the seed host, and sends an **honest custom user-agent**.
- **Never** point this at Google AI Overviews, consumer ChatGPT/Perplexity, or a real client
  site. Nothing here can get your IP blocked when used as intended.
- All I/O is injected, so **no live crawl happens in the test suite** (fixtures + fake clock).

## Files
- `robots.py` — robots.txt policy parse + `bot_access_report` for AI bots (GPTBot, ClaudeBot,
  PerplexityBot, …). Does the **policy** check; `crawler.py` can add a live UA-response probe.
- `audit.py` — `audit_html` (heading structure, statistic density, JSON-LD schema, title/meta,
  overall AI-readability score) + `js_buried_ratio` (content only visible after JS rendering).
- `crawler.py` — `PoliteFetcher` (delay + cap + injectable transport/clock) and `crawl` (BFS,
  robots-obeying, same-host).
- `demo.py` — a live, capped demo run.

## Run
```bash
uv run pytest pocs/crawler/ -v      # 12 tests, fully offline
uv run python pocs/crawler/demo.py  # live, safe, capped at 4 pages
```

## Verified live (books.toscrape.com, capped)
```
[200] https://books.toscrape.com/
    AI-readability=0.65 | words=317 | H1=1 | stat_density=7.9/100w | schema=none
Fetched 3 page(s); fetcher stopped at count=4.
```

## Integration
Feeds `content_scores` (F2 schema) and the app's Content Analysis component (RESEARCH.md §3.1).
The `js_buried_ratio` step can later use Playwright for a real rendered DOM (optional; degrades
gracefully without it).

## Limits / future work
- Rendered-DOM comparison currently takes a rendered HTML string as input; wiring a real
  headless browser (Playwright) is a stretch goal and intentionally optional (no heavy setup).
- `same_registrable_site` uses exact host match (conservative); a true public-suffix check is
  future work.
