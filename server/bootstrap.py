"""Put the existing pipeline + POCs on sys.path so the API reuses them unchanged.

`ensure_paths()` adds `app/` and every `pocs/<name>/` directory to sys.path (the same reuse
mechanism `app/` uses). Called as an explicit statement in `main.py` *before* the `from
pipeline import …` lines, so those absolute imports resolve. Named `bootstrap` (not `_paths`)
to avoid clashing with `app/_paths.py`, which `app/pipeline.py` imports internally.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def ensure_paths() -> None:
    for p in [_ROOT / "app", *sorted((_ROOT / "pocs").glob("*"))]:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


ensure_paths()  # also run on import, so a bare `import bootstrap` sets the paths
