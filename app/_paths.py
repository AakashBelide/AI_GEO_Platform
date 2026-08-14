"""Make the validated POC modules importable from `app/` (Task A1 integration).

The POCs were each built self-contained (a sibling-dir sys.path shim is their reuse
mechanism). The app layer reuses them as-is rather than copying code, so it adds every
`pocs/<name>/` directory to sys.path once. Importing this module has that side effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

_POCS = Path(__file__).resolve().parent.parent / "pocs"
_MODULES = (
    "rigor", "factstore", "connectors", "onboarding",
    "metrics", "keyword_to_prompt", "reconcile", "crawler", "dashboard", "insights",
)

for _sub in _MODULES:
    _p = _POCS / _sub
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
