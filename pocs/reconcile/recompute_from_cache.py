"""Re-derive cross-engine overlap from CACHED payloads — offline, $0 (R-5).

The live run (`reconcile_live.py`) cached every raw API response under `data/cache/<provider>/`.
This script re-parses those exact payloads with the current parsers — no network, no spend — so
the O3 overlap number can be re-derived after a parser change (e.g. the Gemini redirect fix, O-7)
without paying for the calls again. It reconstructs each run's cache path from the same
(provider|model|run_index|prompt) key the connector uses.

    uv run python pocs/reconcile/recompute_from_cache.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "connectors"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "metrics"))

from connectors import _PARSERS  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from metrics import RunRecord  # noqa: E402
from reconcile import overlap_report  # noqa: E402

# Must match reconcile_live.py so the cache keys line up.
from reconcile_live import MODELS, PROMPTS  # noqa: E402

load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))
CACHE = Path("data/cache")


def _cache_path(provider: str, model: str, run_index: int, prompt: str) -> Path:
    key = f"{provider}|{model}|{run_index}|{prompt}".encode()
    h = hashlib.sha256(key).hexdigest()[:16]
    return CACHE / provider / f"{h}.json"


def main() -> None:
    runs: dict[str, list[RunRecord]] = {}
    for provider, model in MODELS.items():
        recs: list[RunRecord] = []
        for pid, prompt in enumerate(PROMPTS):
            path = _cache_path(provider, model, pid, prompt)
            if not path.exists():
                continue
            raw = json.loads(path.read_text())
            _, cites = _PARSERS[provider](raw)
            recs.append(RunRecord(pid, provider, "",
                                  tuple(c.domain for c in cites if c.domain)))
        if recs:
            runs[provider] = recs

    if not runs:
        print("No cached payloads found under data/cache/ — run reconcile_live.py first.")
        return

    rep = overlap_report(runs)
    print("Re-derived from cache (offline, $0):")
    print(f"  unique domains/engine: {rep.per_engine_unique_domains}")
    print(f"  mean pairwise Jaccard ({rep.n_engines} engines): "
          f"{rep.mean_pairwise_jaccard:.3f}")
    for pair, j in sorted(rep.pairwise_jaccard.items()):
        print(f"    {pair}: {j:.3f}")


if __name__ == "__main__":
    main()
