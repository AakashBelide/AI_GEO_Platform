# AI_GEO Platform — reproducibility one-liners.
# Everything here runs OFFLINE and spends $0 except `run-live` (guarded to $2/provider).

.PHONY: help install test lint verify demos report audit clean

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## sync the uv-managed environment
	uv sync

test:  ## run the full test suite (offline, no keys, no network)
	uv run pytest

lint:  ## ruff lint the whole repo
	uv run ruff check .

verify: test lint  ## the "prove it all passes" gate: tests + lint

demos:  ## run every offline demo ($0 — synthetic/simulated data)
	uv run python pocs/metrics/demo.py
	uv run python pocs/reconcile/demo.py
	uv run python pocs/causal/demo.py

report:  ## regenerate the dark dashboard from the saved Asana report + fact store
	uv run python app/geo.py report \
	  --input data/reports/asana_2026-08-14.json \
	  --store data/geo.sqlite \
	  --output data/reports/asana_2026-08-14.html

audit:  ## site-side AI-readability audit of the scrape-safe sandbox (books.toscrape.com)
	uv run python app/geo.py audit

clean:  ## remove Python/test caches (keeps data/ and .venv)
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
