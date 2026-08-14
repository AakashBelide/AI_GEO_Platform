"""Local reporting dashboard (Task A2): a GeoReport → one modern DARK HTML dashboard.

Turns the machine-readable report emitted by `app/geo.py run` (the `GeoReport`
dataclass in `app/pipeline.py`) into an honesty-first, product-analytics dark dashboard.
Charts are drawn with **D3.js v7** (loaded from a CDN) into responsive SVG and the page is
styled with **Tailwind** (also CDN). Every chart — including the cross-engine overlap
heatmap — is a D3 SVG that reads the injected `#geo-report` JSON. The user chose CDN
delivery, so the page is internet-required.

Honesty-first choices, mirrored from the rest of the platform:
  * every rate is drawn as a point estimate **with its 95% confidence interval** — never a
    bare score (the project's whole thesis; see RESEARCH.md / `pocs/rigor`). The CI charts
    are dot-plots with lo→hi error whiskers + end caps so wide/degenerate intervals look wide.
  * a synthetic dry-run is loudly flagged as NOT a real measurement.
  * the "mentioned a lot, cited ~never" gap is the headline (a dumbbell / connected-dot
    chart making the gap a visible distance + red "mentioned, not cited" flag cards).
  * cross-engine pairs are checked for statistical distinguishability with the rigor
    POC's `two_proportion_test` — the dashboard refuses to imply a difference within noise.
  * findings / hedged recommendations and the methodology card (incl. the Gemini-redirect
    caveat) are rendered verbatim; the evidence transcript keeps real answers + citation URLs.

Reuses `pocs/rigor` via the same sibling-dir sys.path shim `pocs/metrics/metrics.py` uses —
the stats live in one place only.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

# POC path shim: reuse the sibling rigor POC's statistics without duplicating them
# (identical pattern to pocs/metrics/metrics.py).
_RIGOR = Path(__file__).resolve().parent.parent / "rigor"
if str(_RIGOR) not in sys.path:
    sys.path.insert(0, str(_RIGOR))

from rigor import two_proportion_test  # noqa: E402

# --------------------------------------------------------------------------- #
# Dark palette (neon accents on near-black; the exact tokens the Tailwind config uses)
# --------------------------------------------------------------------------- #
ACCENT = "#22d3ee"    # cyan — primary
ACCENT2 = "#f472b6"   # magenta/pink — secondary
WARN = "#fbbf24"      # amber — warning
CRIT = "#f87171"      # red — critical
OK = "#34d399"        # green — ok

# When mention is at/above this and citation at/below that, flag the headline gap.
_GAP_MENTION_MIN = 0.40
_GAP_CITATION_MAX = 0.05


# --------------------------------------------------------------------------- #
# Small formatting helpers
# --------------------------------------------------------------------------- #
def _e(text: object) -> str:
    """HTML-escape any value for safe interpolation."""
    return html.escape(str(text), quote=True)


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def _num(x: float | None, places: int = 2) -> str:
    return "—" if x is None else f"{x:.{places}f}"


def _est_k_n(est: dict) -> tuple[int, int]:
    """Recover an integer success count from a proportion estimate ({point, n})."""
    n = int(est.get("n", 0) or 0)
    return round(float(est.get("point", 0.0)) * n), n


def _f(est: dict, key: str, default: float = 0.0) -> float:
    return float(est.get(key, default) or default)


# --------------------------------------------------------------------------- #
# Reusable dark building blocks
# --------------------------------------------------------------------------- #
_CARD = "rounded-2xl border border-line bg-surface shadow-lg shadow-black/30"
_SECTION = "scroll-mt-24"


def _panel_open(anchor: str, title: str, hint: str = "") -> str:
    hint_html = f'<span class="text-sm font-normal text-muted">{_e(hint)}</span>' if hint else ""
    return (
        f'<section id="{_e(anchor)}" class="{_SECTION}">'
        f'<div class="{_CARD} p-6 sm:p-7">'
        f'<h2 class="mb-4 flex items-center gap-3 text-lg font-semibold text-ink">'
        f"{_e(title)} {hint_html}</h2>"
    )


def _panel_close() -> str:
    return "</div></section>"


def _badge(text: str, tone: str) -> str:
    tones = {
        "ok": "bg-ok/15 text-ok ring-1 ring-ok/30",
        "warn": "bg-warn/15 text-warn ring-1 ring-warn/30",
        "crit": "bg-crit/15 text-crit ring-1 ring-crit/30",
        "accent": "bg-accent/15 text-accent ring-1 ring-accent/30",
    }
    cls = tones.get(tone, tones["accent"])
    return (
        f'<span class="inline-flex items-center rounded-full px-2.5 py-0.5 '
        f'text-xs font-semibold {cls}">{_e(text)}</span>'
    )


# --------------------------------------------------------------------------- #
# Hero + stat tiles
# --------------------------------------------------------------------------- #
def _is_synthetic(mode: str) -> bool:
    m = mode.lower()
    return "synthetic" in m or "dry-run" in m


def _prompts_x_repeats(r: dict) -> str:
    card = ((r.get("reconciliation") or {}).get("methodology")) or {}
    if card.get("n_prompts") and card.get("repeats_per_prompt"):
        return f"{card.get('n_prompts')} × {card.get('repeats_per_prompt')}"
    count = (r.get("prompt_set") or {}).get("count")
    per = r.get("per_engine_metrics") or {}
    repeats = None
    for m in per.values():
        n_runs, n = int(m.get("n_runs", 0) or 0), int((m.get("mention") or {}).get("n", 0) or 0)
        if count and n:
            repeats = round(n / count) if count else None
        elif n_runs and count:
            repeats = round(n_runs / count)
        break
    if count and repeats:
        return f"{count} × {repeats}"
    return _e(count) if count is not None else "—"


def _total_citations(r: dict) -> int:
    total = 0
    for entries in (r.get("top_domains") or {}).values():
        for entry in entries or []:
            try:
                total += int(entry[1])
            except (IndexError, TypeError, ValueError):
                continue
    return total


def _stat_tile(value: str, label: str, tone: str = "accent") -> str:
    tone_cls = {"accent": "text-accent", "warn": "text-warn", "ink": "text-ink"}.get(
        tone, "text-accent"
    )
    return (
        f'<div class="{_CARD} p-4">'
        f'<div class="text-2xl font-bold tabular-nums {tone_cls}">{_e(value)}</div>'
        f'<div class="mt-1 text-xs uppercase tracking-wide text-muted">{_e(label)}</div>'
        f"</div>"
    )


def _hero(r: dict) -> str:
    brand = _e(r.get("brand", "—"))
    category = _e(r.get("category", "—"))
    mode = str(r.get("mode", "—"))
    generated = str(r.get("generated_utc", "—"))
    synthetic = _is_synthetic(mode)
    total_spend = sum(float(v.get("spent", 0.0)) for v in (r.get("spend") or {}).values())
    n_engines = len(r.get("per_engine_metrics") or {})
    mean_j = ((r.get("reconciliation") or {}).get("overlap") or {}).get("mean_pairwise_jaccard")

    mode_badge = _badge(mode, "warn" if synthetic else "ok")
    banner = ""
    if synthetic:
        banner = (
            '<div class="mt-5 rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 '
            'text-sm text-warn">'
            "<span class=\"font-bold\">SYNTHETIC DRY-RUN — not a real measurement</span> "
            f"of {brand}. Deterministic fabricated data for wiring/demo only.</div>"
        )

    tiles = "".join(
        [
            _stat_tile(str(n_engines), "engines tested"),
            _stat_tile(_prompts_x_repeats(r), "prompts × repeats"),
            _stat_tile(str(_total_citations(r)), "total citations"),
            _stat_tile(_num(mean_j, 3), "mean cross-engine overlap"),
            _stat_tile(f"${total_spend:.2f}", "total spend", tone="warn"),
            _stat_tile(_e(generated)[:10], "generated", tone="ink"),
        ]
    )
    return f"""
    <section id="overview" class="{_SECTION} pt-2">
      <div class="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
        Measurement-honest GEO report</div>
      <h1 class="mt-2 text-4xl font-extrabold tracking-tight text-ink sm:text-5xl">{brand}</h1>
      <div class="mt-2 flex flex-wrap items-center gap-3 text-lg text-ink2">
        <span>{category}</span>{mode_badge}
      </div>
      {banner}
      <div class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{tiles}</div>
    </section>
    """


# --------------------------------------------------------------------------- #
# Gap (headline) — D3 dumbbell / connected-dot chart + red flag cards
# --------------------------------------------------------------------------- #
def _gap(r: dict) -> str:
    per = r.get("per_engine_metrics") or {}
    cards: list[str] = []
    flagged = 0
    for engine, m in per.items():
        mp = _f(m.get("mention") or {}, "point")
        cp = _f(m.get("citation") or {}, "point")
        is_gap = mp >= _GAP_MENTION_MIN and cp <= _GAP_CITATION_MAX
        if is_gap:
            flagged += 1
        badge = (
            _badge("mentioned, not cited", "crit")
            if is_gap
            else _badge("cites its own domain", "ok")
        )
        ring = "ring-1 ring-crit/40 bg-crit/5" if is_gap else "ring-1 ring-line"
        cbar = "text-crit" if is_gap else "text-accent2"
        cards.append(
            f'<div class="rounded-xl border border-line p-4 {ring}">'
            f'<div class="mb-2 flex items-center justify-between gap-2">'
            f'<span class="font-semibold text-ink">{_e(engine)}</span>{badge}</div>'
            f'<div class="space-y-1 text-sm">'
            f'<div class="flex justify-between"><span class="text-ink2">mention</span>'
            f'<span class="tabular-nums text-accent">{_pct(mp)}</span></div>'
            f'<div class="flex justify-between"><span class="text-ink2">citation</span>'
            f'<span class="tabular-nums {cbar}">{_pct(cp)}</span></div></div></div>'
        )
    lead = (
        f'<strong class="text-crit">{flagged}</strong> engine(s) mention '
        f"{_e(r.get('brand', 'the brand'))} often but cite its own domain at/near zero — "
        "the answer names the brand while sending the citation elsewhere."
        if flagged
        else "No engine shows the mention-without-citation gap on this run."
    )
    grid = (
        f'<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{"".join(cards)}</div>'
        if cards
        else '<p class="text-muted">no engines</p>'
    )
    return (
        _panel_open("gap", "Mention vs. citation gap", "the headline finding")
        + f'<p class="mb-4 text-ink2">{lead}</p>'
        + '<div id="chart-gap" class="geo-chart mb-5"><svg></svg></div>'
        + grid
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Findings / recommendations (verbatim)
# --------------------------------------------------------------------------- #
def _list_panel(anchor: str, title: str, hint: str, items: list, tone: str) -> str:
    if not items:
        return ""
    dot = {"ok": "bg-ok", "warn": "bg-warn", "accent": "bg-accent"}.get(tone, "bg-accent")
    lis = "".join(
        f'<li class="flex gap-3"><span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full '
        f'{dot}"></span><span class="text-ink2">{_e(x)}</span></li>'
        for x in items
    )
    return (
        _panel_open(anchor, title, hint)
        + f'<ul class="space-y-2.5">{lis}</ul>'
        + _panel_close()
    )


def _findings(r: dict) -> str:
    return _list_panel(
        "findings", "Findings", "what the numbers say", r.get("findings") or [], "accent"
    )


def _recommendations(r: dict) -> str:
    return _list_panel(
        "recommendations",
        "Recommendations",
        "directional hypotheses to test (not proven levers)",
        r.get("recommendations") or [],
        "warn",
    )


# --------------------------------------------------------------------------- #
# Per-engine metrics with CI (D3 dot-plot with lo→hi error whiskers)
# --------------------------------------------------------------------------- #
def _metrics(r: dict) -> str:
    per = r.get("per_engine_metrics") or {}
    if not per:
        return (
            _panel_open("metrics", "Per-engine metrics", "point ● with 95% confidence interval")
            + '<p class="text-muted">no per-engine metrics</p>'
            + _panel_close()
        )
    charts = "".join(
        f'<div class="rounded-xl border border-line p-4">'
        f'<h3 class="mb-2 text-sm font-semibold text-ink">{title}</h3>'
        f'<div id="{cid}" class="geo-chart"><svg></svg></div></div>'
        for title, cid in (
            ("Mention rate", "chart-ci-mention"),
            ("Citation rate", "chart-ci-citation"),
            ("Share of voice", "chart-ci-sov"),
        )
    )
    return (
        _panel_open("metrics", "Per-engine metrics", "point ● with 95% confidence interval")
        + '<p class="mb-4 text-ink2">Every rate carries its 95% interval — the bright dot is the '
        "point estimate, the whisker is [lo, hi]. Wide whiskers = high uncertainty (small n / "
        "near-degenerate). No single-run point score is shown without an interval.</p>"
        + f'<div class="grid grid-cols-1 gap-4 lg:grid-cols-3">{charts}</div>'
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Statistical distinguishability (two-proportion z-test) — verbatim verdicts
# --------------------------------------------------------------------------- #
def _distinguishability(r: dict) -> str:
    per = r.get("per_engine_metrics") or {}
    engines = list(per)
    rows: list[str] = []
    for i in range(len(engines)):
        for j in range(i + 1, len(engines)):
            a, b = engines[i], engines[j]
            k1, n1 = _est_k_n(per[a].get("citation") or {})
            k2, n2 = _est_k_n(per[b].get("citation") or {})
            if n1 <= 0 or n2 <= 0:
                continue
            res = two_proportion_test(k1, n1, k2, n2)
            verdict = (
                _badge("distinguishable", "ok")
                if res.distinguishable
                else _badge("NOT distinguishable (within noise)", "crit")
            )
            rows.append(
                f'<li class="flex flex-wrap items-center gap-2 rounded-lg border border-line '
                f'px-3 py-2"><span class="font-semibold text-ink">{_e(a)}</span>'
                f'<span class="text-muted">vs</span>'
                f'<span class="font-semibold text-ink">{_e(b)}</span>{verdict}'
                f'<span class="ml-auto text-xs tabular-nums text-muted">'
                f"Δ={res.diff * 100:+.0f}pp · p={res.p_value:.3f}</span></li>"
            )
    body = (
        f'<ul class="space-y-2">{"".join(rows)}</ul>'
        if rows
        else '<p class="text-muted">Need ≥2 engines with runs to test distinguishability.</p>'
    )
    return (
        _panel_open(
            "distinguishability",
            "Statistical distinguishability",
            "citation rate, two-proportion z-test (α=0.05)",
        )
        + '<p class="mb-4 text-ink2">Where a pair is <em>not</em> distinguishable, the dashboard '
        "does not claim one engine cites the brand more than the other — the gap is within "
        "noise.</p>"
        + body
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Cross-engine reconciliation: numbers + a D3 Jaccard heatmap
# --------------------------------------------------------------------------- #
def _heatmap(overlap: dict, engines: list[str]) -> str:
    """Mount for the D3 heatmap; the matrix is drawn client-side from the JSON blob.

    Returns nothing for a single engine (no pairs to draw); the D3 code no-ops in the
    same case, so the container is safe to omit here.
    """
    if len(engines) < 2:
        return ""
    return (
        '<div class="mt-2 overflow-x-auto">'
        '<div id="chart-heatmap" class="geo-chart" style="max-width:640px"><svg></svg></div>'
        '<p class="mt-2 text-xs text-muted">Pairwise cited-domain overlap (Jaccard). '
        "Brighter = more shared sources; diagonal is self.</p></div>"
    )


def _reconciliation(r: dict) -> str:
    recon = r.get("reconciliation") or {}
    if not recon:
        return (
            _panel_open("cross-engine", "Cross-engine reconciliation")
            + '<p class="text-muted">Not available — reconciliation needs ≥2 engines and a '
            "target/competitor domain. Skipped for this report.</p>"
            + _panel_close()
        )
    overlap = recon.get("overlap") or {}
    mean_j = overlap.get("mean_pairwise_jaccard")
    uniq = overlap.get("per_engine_unique_domains") or {}
    engines = list((r.get("per_engine_metrics") or {}).keys())
    if not engines:
        engines = list(uniq.keys())

    uniq_cells = "".join(
        f'<span class="inline-flex items-center gap-2 rounded-lg border border-line '
        f'bg-surface2 px-3 py-1 text-sm"><b class="text-ink">{_e(e)}</b>'
        f'<span class="tabular-nums text-ink2">{_e(c)}</span></span>'
        for e, c in uniq.items()
    )
    divergence = recon.get("divergence") or []
    if divergence:
        div_items = "".join(
            f'<li class="text-ink2"><b class="text-ink">{_e(f.get("engine"))}</b> over-indexes '
            f'<b class="text-ink">{_e(f.get("ecosystem"))}</b> '
            f"(+{float(f.get('delta', 0.0)) * 100:.0f}% vs cross-engine mean)</li>"
            for f in divergence
        )
        div_block = f'<ul class="list-disc space-y-1 pl-5">{div_items}</ul>'
    else:
        div_block = (
            '<p class="text-muted">No engine over-indexes a single source ecosystem beyond the '
            "divergence threshold on this run.</p>"
        )
    return (
        _panel_open("cross-engine", "Cross-engine reconciliation")
        + '<div class="mb-4 flex flex-wrap gap-4">'
        + f'<div class="{_CARD} px-5 py-4"><div class="text-3xl font-bold tabular-nums '
        + f'text-accent">{_num(mean_j, 3)}</div>'
        + '<div class="mt-1 text-xs text-muted">mean pairwise overlap (Jaccard)</div></div>'
        + "</div>"
        + _heatmap(overlap, engines)
        + '<p class="mb-2 mt-5 text-ink2">Unique cited domains per engine:</p>'
        + f'<div class="flex flex-wrap gap-2">{uniq_cells}</div>'
        + '<p class="mb-2 mt-5 text-ink2">Source-ecosystem divergence:</p>'
        + div_block
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Top cited domains per engine (D3 small-multiple horizontal bars)
# --------------------------------------------------------------------------- #
def _top_domains(r: dict) -> str:
    top = r.get("top_domains") or {}
    target = str(r.get("target_domain") or "").lower().lstrip(".")
    if not top or not any(top.values()):
        return ""
    blocks = "".join(
        f'<div class="rounded-xl border border-line p-4">'
        f'<h3 class="mb-2 text-sm font-semibold text-ink">{_e(engine)}</h3>'
        f'<div class="top-chart geo-chart" data-engine="{_e(engine)}"><svg></svg></div></div>'
        for engine in top
    )
    tnote = (
        f'<p class="mt-4 text-xs text-muted">The target domain <b class="text-accent">'
        f"{_e(target)}</b> is highlighted where an engine cites it.</p>"
        if target
        else ""
    )
    return (
        _panel_open(
            "top-domains",
            "Top cited domains per engine",
            "count of citations in this run",
        )
        + f'<div class="grid grid-cols-1 gap-4 md:grid-cols-2">{blocks}</div>'
        + tnote
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Prompt set + prompts used
# --------------------------------------------------------------------------- #
def _prompt_set(r: dict) -> str:
    ps = r.get("prompt_set") or {}
    count = ps.get("count", "—")
    intents = ps.get("intents") or {}
    skew = ps.get("skew") or {}
    skew_ok = bool(skew.get("ok", False))
    skew_msg = skew.get("message", "—")
    chips = "".join(
        f'<span class="inline-flex items-center gap-2 rounded-lg border border-line '
        f'bg-surface2 px-3 py-1 text-sm"><b class="text-ink">{_e(k)}</b>'
        f'<span class="text-ink2">{int(v.get("count", 0))} '
        f'({v.get("fraction", 0.0) * 100:.0f}%)</span></span>'
        for k, v in intents.items()
    )
    verdict = _badge(skew_msg, "ok" if skew_ok else "crit")
    return (
        _panel_open("prompt-set", "Prompt set")
        + f'<p class="mb-3 text-ink2">{_e(count)} prompts · intent mix (target 80 / 10 / 10):</p>'
        + f'<div class="mb-4 flex flex-wrap gap-2">{chips}</div>'
        + f'<div class="text-sm">Branded-skew check: {verdict}</div>'
        + _panel_close()
    )


def _prompts_used(r: dict) -> str:
    prompts = r.get("prompts") or []
    if not prompts:
        return ""
    lis = "".join(
        f'<li class="flex flex-wrap items-baseline gap-3">'
        f'<span class="inline-flex shrink-0 rounded-md bg-accent/10 px-2 py-0.5 text-[11px] '
        f'font-semibold uppercase tracking-wide text-accent">{_e(p.get("intent", "—"))}</span>'
        f'<span class="text-ink2">{_e(p.get("text", ""))}</span></li>'
        for p in prompts
    )
    return (
        _panel_open("prompts-used", "Prompts used", "the exact questions asked, per intent")
        + f'<ol class="space-y-2.5">{lis}</ol>'
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Methodology card + verbatim caveats
# --------------------------------------------------------------------------- #
def _methodology(r: dict) -> str:
    card = ((r.get("reconciliation") or {}).get("methodology")) or {}
    if not card:
        return (
            _panel_open("methodology", "Methodology card")
            + '<p class="text-muted">No methodology card in this report '
            "(reconciliation skipped).</p>"
            + _panel_close()
        )
    access = card.get("access_method") or {}
    engines = card.get("engines") or {}
    access_rows = "".join(
        f'<tr class="border-b border-line"><td class="py-2 pr-4 text-ink">{_e(e)}</td>'
        f'<td class="py-2 pr-4 text-ink2">{_e(engines.get(e, "—"))}</td>'
        f'<td class="py-2 text-ink2">{_e(access.get(e, "—"))}</td></tr>'
        for e in sorted(set(access) | set(engines))
    )
    caveats = "".join(
        f'<li class="text-ink2">{_e(c)}</li>' for c in (card.get("caveats") or [])
    )
    fields = [
        ("generated", card.get("generated_utc")),
        ("prompts × repeats", f"{card.get('n_prompts')} × {card.get('repeats_per_prompt')}"),
        ("locale", card.get("locale")),
        ("domain normalization", card.get("domain_normalization")),
    ]
    field_cards = "".join(
        f'<div class="rounded-lg border border-line bg-surface2 px-3 py-2">'
        f'<div class="text-[11px] uppercase tracking-wide text-muted">{_e(k)}</div>'
        f'<div class="break-words text-sm text-ink">{_e(v)}</div></div>'
        for k, v in fields
    )
    return (
        _panel_open("methodology", "Methodology card")
        + '<div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">'
        + field_cards
        + "</div>"
        + '<div class="overflow-x-auto"><table class="w-full text-left text-sm">'
        + '<thead><tr class="border-b border-line text-xs uppercase tracking-wide text-muted">'
        + '<th class="py-2 pr-4">engine</th><th class="py-2 pr-4">model</th>'
        + '<th class="py-2">access method</th></tr></thead>'
        + f"<tbody>{access_rows}</tbody></table></div>"
        + '<div class="mt-5 border-l-2 border-warn pl-4">'
        + '<div class="mb-1 text-sm font-semibold text-warn">Caveats (verbatim)</div>'
        + f'<ul class="list-disc space-y-1 pl-5">{caveats}</ul></div>'
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Evidence transcript (native <details>/<summary>, no JS)
# --------------------------------------------------------------------------- #
def _transcript(r: dict) -> str:
    tr = r.get("transcript") or {}
    if not tr:
        return ""
    blocks: list[str] = []
    for engine, samples in tr.items():
        details: list[str] = []
        for s in samples or []:
            cites = s.get("citations") or []
            cite_items = "".join(
                f'<li class="flex flex-wrap items-baseline gap-2">'
                f'<span class="w-6 shrink-0 tabular-nums text-muted">{_e(c.get("position"))}</span>'
                f'<b class="text-ink">{_e(c.get("domain"))}</b>'
                f'<span class="break-all text-accent">{_e(c.get("url"))}</span></li>'
                for c in cites
            )
            cite_block = (
                f'<ol class="mt-2 space-y-1 text-xs">{cite_items}</ol>'
                if cite_items
                else '<p class="mt-2 text-xs text-muted">no citations for this answer</p>'
            )
            details.append(
                '<details class="rounded-lg border border-line bg-surface2 px-4 py-2">'
                f'<summary class="cursor-pointer py-1 font-medium text-ink">'
                f"{_e(s.get('prompt_text', ''))}</summary>"
                '<div class="my-2 whitespace-pre-wrap border-l-2 border-line bg-surface '
                f'px-3 py-2 text-sm text-ink2">{_e(s.get("answer", ""))}</div>'
                f"{cite_block}</details>"
            )
        blocks.append(
            f'<div class="space-y-2"><h3 class="text-sm font-semibold text-ink">{_e(engine)}</h3>'
            f'{"".join(details)}</div>'
        )
    return (
        _panel_open(
            "evidence",
            "Evidence · transcript",
            "one representative answer per prompt, with citations",
        )
        + '<p class="mb-4 text-ink2">Expand any prompt to read the model\'s actual answer and the '
        "exact sources it cited (url · domain · position).</p>"
        + f'<div class="space-y-5">{"".join(blocks)}</div>'
        + _panel_close()
    )


def _notes(r: dict) -> str:
    notes = r.get("notes") or []
    if not notes:
        return ""
    items = "".join(f'<li class="text-ink2">{_e(n)}</li>' for n in notes)
    return (
        _panel_open("notes", "Notes")
        + f'<ul class="list-disc space-y-1 pl-5">{items}</ul>'
        + _panel_close()
    )


# --------------------------------------------------------------------------- #
# Head: Tailwind + D3 v7 CDNs, dark config
# --------------------------------------------------------------------------- #
_TAILWIND_CONFIG = """
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: '#0b0f17', surface: '#0f1626', surface2: '#182236', line: '#1f2b40',
        accent: '#22d3ee', accent2: '#f472b6', warn: '#fbbf24', crit: '#f87171', ok: '#34d399',
        ink: '#e6edf7', ink2: '#94a3b8', muted: '#64748b'
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif']
      }
    }
  }
};
"""

_NAV = [
    ("overview", "Overview"),
    ("gap", "Gap"),
    ("findings", "Findings"),
    ("metrics", "Metrics"),
    ("cross-engine", "Cross-engine"),
    ("evidence", "Evidence"),
    ("methodology", "Methodology"),
]


def _topbar() -> str:
    links = "".join(
        f'<a href="#{a}" class="rounded-md px-2.5 py-1 text-sm text-ink2 '
        f'transition-colors hover:bg-surface2 hover:text-accent">{_e(label)}</a>'
        for a, label in _NAV
    )
    return (
        '<header class="sticky top-0 z-50 border-b border-line bg-bg/85 backdrop-blur">'
        '<div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-1 gap-y-1 px-4 py-3">'
        '<span class="mr-3 flex items-center gap-2 font-bold text-ink">'
        '<span class="h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_10px] shadow-accent"></span>'
        "GEO Platform</span>"
        f'<nav class="flex flex-wrap items-center gap-1">{links}</nav>'
        "</div></header>"
    )


# --------------------------------------------------------------------------- #
# The D3 v7 builder (one script, reads the injected JSON blob into SVG charts)
# --------------------------------------------------------------------------- #
_D3_JS = r"""
(function () {
  var el = document.getElementById('geo-report');
  if (!el || typeof d3 === 'undefined') return;
  var R;
  try { R = JSON.parse(el.textContent); } catch (e) { return; }

  var C = { bg: '#0b0f17', surface: '#0f1626', surface2: '#182236', line: '#1f2b40',
            accent: '#22d3ee', accent2: '#f472b6', warn: '#fbbf24', crit: '#f87171',
            ok: '#34d399', ink: '#e6edf7', ink2: '#94a3b8', muted: '#64748b' };
  var GRID = 'rgba(148,163,184,0.12)';
  var FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";
  var per = R.per_engine_metrics || {};
  var engines = Object.keys(per);

  // One shared, absolutely-positioned tooltip for every chart.
  var tip = d3.select('body').append('div').attr('class', 'geo-tooltip');
  tip.node().style.cssText =
    'position:absolute;z-index:60;pointer-events:none;opacity:0;transition:opacity .12s;' +
    'max-width:260px;padding:8px 10px;border-radius:10px;line-height:1.35;font:12px ' + FONT +
    ';color:' + C.ink + ';background:rgba(15,22,38,0.97);border:1px solid ' + C.line +
    ';box-shadow:0 8px 24px rgba(0,0,0,0.45);';
  function showTip(html, ev) { tip.html(html).style('opacity', 1); moveTip(ev); }
  function moveTip(ev) {
    tip.style('left', (ev.pageX + 14) + 'px').style('top', (ev.pageY + 14) + 'px');
  }
  function hideTip() { tip.style('opacity', 0); }
  function hoverable(sel, htmlFn) {
    sel.style('cursor', 'default')
      .on('mousemove', function (ev, d) { showTip(htmlFn(d), ev); })
      .on('mouseleave', hideTip);
  }

  function pt(est) { return est && est.point != null ? est.point * 100 : 0; }
  function loOf(est) { return est && est.lo != null ? est.lo * 100 : 0; }
  function hiOf(est) { return est && est.hi != null ? est.hi * 100 : 0; }
  function nOf(est) { return est && est.n != null ? est.n : 0; }
  function fpct(v) { return v.toFixed(0) + '%'; }
  function widthOf(node) { return Math.max(260, node.clientWidth || 600); }

  function freshSvg(node, width, height) {
    // Reuse the server-rendered <svg> placeholder inside the mount (create one if absent),
    // clear it, and (re)size it. Width is measured from the parent mount for responsiveness.
    var svg = d3.select(node).select('svg');
    if (svg.empty()) svg = d3.select(node).append('svg');
    svg.selectAll('*').remove();
    return svg
      .attr('viewBox', '0 0 ' + width + ' ' + height)
      .attr('width', '100%').attr('height', height)
      .attr('preserveAspectRatio', 'xMinYMin meet')
      .style('overflow', 'visible').style('display', 'block');
  }

  function pctGrid(svg, x, top, bottom, ticks) {
    var g = svg.append('g');
    g.selectAll('line').data(ticks).join('line')
      .attr('x1', function (d) { return x(d); }).attr('x2', function (d) { return x(d); })
      .attr('y1', top).attr('y2', bottom).attr('stroke', GRID).attr('stroke-width', 1);
    g.selectAll('text').data(ticks).join('text')
      .attr('x', function (d) { return x(d); }).attr('y', bottom + 15)
      .attr('text-anchor', 'middle').attr('fill', C.muted).attr('font-size', 10)
      .text(function (d) { return d + '%'; });
  }

  // -- Redraw registry: every chart is a closure re-run on resize (responsive). --
  var redraws = [];
  function register(fn) { redraws.push(fn); try { fn(); } catch (e) {} }
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      redraws.forEach(function (f) { try { f(); } catch (e) {} });
    }, 150);
  });

  // 1) Mention-vs-citation gap -> DUMBBELL / connected-dot chart.
  function drawGap() {
    var node = document.getElementById('chart-gap');
    if (!node || !engines.length) return;
    var W = widthOf(node);
    var m = { top: 10, right: 46, bottom: 30, left: 96 };
    var rowH = 36;
    var H = m.top + m.bottom + engines.length * rowH;
    var svg = freshSvg(node, W, H);
    var x = d3.scaleLinear().domain([0, 100]).range([m.left, W - m.right]);
    var y = d3.scaleBand().domain(engines).range([m.top, H - m.bottom]).padding(0.5);
    pctGrid(svg, x, m.top, H - m.bottom, x.ticks(5));
    engines.forEach(function (e) {
      var cy = y(e) + y.bandwidth() / 2;
      var mp = pt(per[e].mention), cp = pt(per[e].citation);
      var flagged = mp >= 40 && cp <= 5;
      var cCol = flagged ? C.crit : C.accent2;
      svg.append('text').attr('x', m.left - 12).attr('y', cy).attr('dy', '0.32em')
        .attr('text-anchor', 'end').attr('fill', C.ink2).attr('font-size', 12)
        .attr('font-weight', 600).text(e);
      svg.append('line').attr('x1', x(mp)).attr('x2', x(cp)).attr('y1', cy).attr('y2', cy)
        .attr('stroke', flagged ? C.crit : C.line).attr('stroke-width', flagged ? 3 : 2);
      svg.append('circle').attr('cx', x(mp)).attr('cy', cy).attr('r', 6)
        .attr('fill', C.accent).attr('stroke', C.bg).attr('stroke-width', 1.5);
      svg.append('circle').attr('cx', x(cp)).attr('cy', cy).attr('r', 6)
        .attr('fill', cCol).attr('stroke', C.bg).attr('stroke-width', 1.5);
      hoverable(
        svg.append('rect').attr('x', m.left).attr('y', y(e))
          .attr('width', W - m.right - m.left).attr('height', y.bandwidth())
          .attr('fill', 'transparent'),
        function () {
          return '<b>' + e + '</b><br>mention: <b style="color:' + C.accent + '">' +
            fpct(mp) + '</b><br>citation: <b style="color:' + cCol + '">' + fpct(cp) +
            '</b>' + (flagged ? '<br><span style="color:' + C.crit +
            '">mentioned, not cited</span>' : '');
        }
      );
    });
  }
  register(drawGap);

  // 2) Per-engine rate with 95% CI -> DOT-PLOT with lo->hi error whiskers + end caps.
  function ciChart(id, key, color) {
    var node = document.getElementById(id);
    if (!node || !engines.length) return;
    var W = widthOf(node);
    var m = { top: 8, right: 22, bottom: 26, left: 84 };
    var rowH = 30;
    var H = m.top + m.bottom + engines.length * rowH;
    var svg = freshSvg(node, W, H);
    var x = d3.scaleLinear().domain([0, 100]).range([m.left, W - m.right]);
    var y = d3.scaleBand().domain(engines).range([m.top, H - m.bottom]).padding(0.5);
    pctGrid(svg, x, m.top, H - m.bottom, x.ticks(4));
    engines.forEach(function (e) {
      var est = per[e][key] || {};
      var cy = y(e) + y.bandwidth() / 2;
      var lo = loOf(est), hi = hiOf(est), p = pt(est);
      svg.append('text').attr('x', m.left - 8).attr('y', cy).attr('dy', '0.32em')
        .attr('text-anchor', 'end').attr('fill', C.ink2).attr('font-size', 11).text(e);
      svg.append('line').attr('x1', x(lo)).attr('x2', x(hi)).attr('y1', cy).attr('y2', cy)
        .attr('stroke', color).attr('stroke-width', 2).attr('opacity', 0.75);
      [lo, hi].forEach(function (v) {
        svg.append('line').attr('x1', x(v)).attr('x2', x(v))
          .attr('y1', cy - 5).attr('y2', cy + 5)
          .attr('stroke', color).attr('stroke-width', 2).attr('opacity', 0.75);
      });
      svg.append('circle').attr('cx', x(p)).attr('cy', cy).attr('r', 5)
        .attr('fill', color).attr('stroke', C.bg).attr('stroke-width', 1.5);
      hoverable(
        svg.append('rect').attr('x', m.left).attr('y', y(e))
          .attr('width', W - m.right - m.left).attr('height', y.bandwidth())
          .attr('fill', 'transparent'),
        function () {
          return '<b>' + e + '</b><br>point: <b style="color:' + color + '">' + fpct(p) +
            '</b><br>95% CI: [' + fpct(lo) + ', ' + fpct(hi) + ']<br>n = ' + nOf(est);
        }
      );
    });
  }
  register(function () { ciChart('chart-ci-mention', 'mention', C.accent); });
  register(function () { ciChart('chart-ci-citation', 'citation', C.accent2); });
  register(function () { ciChart('chart-ci-sov', 'share_of_voice', C.warn); });

  // 3) Top cited domains per engine -> small-multiple horizontal bars.
  var target = String(R.target_domain || '').toLowerCase().replace(/^\.+/, '');
  function isTarget(d) {
    d = String(d).toLowerCase().replace(/^\.+/, '');
    return !!target && (d === target || d.endsWith('.' + target));
  }
  var top = R.top_domains || {};
  function drawTop() {
    d3.selectAll('.top-chart').each(function () {
      var node = this;
      var e = node.getAttribute('data-engine');
      var entries = (top[e] || []).slice()
        .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 8);
      if (!entries.length) { d3.select(node).selectAll('*').remove(); return; }
      var W = widthOf(node);
      var m = { top: 6, right: 30, bottom: 6, left: 120 };
      var rowH = 24;
      var H = m.top + m.bottom + entries.length * rowH;
      var svg = freshSvg(node, W, H);
      var maxC = d3.max(entries, function (d) { return d[1]; }) || 1;
      var x = d3.scaleLinear().domain([0, maxC]).range([m.left, W - m.right]);
      var y = d3.scaleBand().domain(entries.map(function (d) { return d[0]; }))
        .range([m.top, H - m.bottom]).padding(0.28);
      entries.forEach(function (d) {
        var isT = isTarget(d[0]);
        hoverable(
          svg.append('rect').attr('x', m.left).attr('y', y(d[0])).attr('height', y.bandwidth())
            .attr('width', Math.max(0, x(d[1]) - m.left)).attr('rx', 4)
            .attr('fill', isT ? C.accent : 'rgba(244,114,182,0.55)'),
          function () {
            return '<b>' + d[0] + '</b><br>' + d[1] + ' citation' + (d[1] === 1 ? '' : 's');
          }
        );
        svg.append('text').attr('x', m.left - 8).attr('y', y(d[0]) + y.bandwidth() / 2)
          .attr('dy', '0.32em').attr('text-anchor', 'end').attr('font-size', 11)
          .attr('fill', isT ? C.accent : C.ink2).text(d[0]);
        svg.append('text').attr('x', x(d[1]) + 6).attr('y', y(d[0]) + y.bandwidth() / 2)
          .attr('dy', '0.32em').attr('fill', C.muted).attr('font-size', 11)
          .attr('font-weight', 600).text(d[1]);
      });
    });
  }
  register(drawTop);

  // 4) Cross-engine overlap -> D3 HEATMAP (sequential surface->accent + numbers + legend).
  function drawHeatmap() {
    var node = document.getElementById('chart-heatmap');
    if (!node) return;
    var recon = R.reconciliation || {};
    var overlap = recon.overlap || {};
    var pairwise = overlap.pairwise_jaccard || {};
    var uniq = overlap.per_engine_unique_domains || {};
    var labels = engines.length ? engines : Object.keys(uniq);
    if (labels.length < 2) { d3.select(node).selectAll('*').remove(); return; }
    var lookup = {};
    Object.keys(pairwise).forEach(function (k) {
      var parts = k.split('|');
      if (parts.length === 2) {
        var v = +pairwise[k];
        lookup[parts[0] + '|' + parts[1]] = v;
        lookup[parts[1] + '|' + parts[0]] = v;
      }
    });
    var W = widthOf(node);
    var m = { top: 66, right: 16, bottom: 40, left: 92 };
    var n = labels.length;
    var cell = Math.max(30, Math.min(74, (W - m.left - m.right) / n));
    var gridW = cell * n;
    var H = m.top + cell * n + m.bottom;
    var svg = freshSvg(node, W, H);
    var color = d3.scaleLinear().domain([0, 1]).range([C.surface2, C.accent]);
    labels.forEach(function (e, j) {
      var cx = m.left + j * cell + cell / 2;
      svg.append('text').attr('x', cx).attr('y', m.top - 8)
        .attr('transform', 'rotate(-40,' + cx + ',' + (m.top - 8) + ')')
        .attr('text-anchor', 'start').attr('fill', C.ink2).attr('font-size', 11).text(e);
    });
    labels.forEach(function (rowE, i) {
      svg.append('text').attr('x', m.left - 8).attr('y', m.top + i * cell + cell / 2)
        .attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', C.ink2)
        .attr('font-size', 11).text(rowE);
      labels.forEach(function (colE, j) {
        var v = (rowE === colE) ? 1 : lookup[rowE + '|' + colE];
        var has = v != null && !isNaN(v);
        var x0 = m.left + j * cell, y0 = m.top + i * cell;
        hoverable(
          svg.append('rect').attr('x', x0 + 1).attr('y', y0 + 1)
            .attr('width', cell - 2).attr('height', cell - 2).attr('rx', 4)
            .attr('fill', has ? color(Math.max(0, Math.min(1, v))) : C.surface)
            .attr('stroke', C.line),
          function () {
            return '<b>' + rowE + ' &cap; ' + colE + '</b><br>Jaccard: ' +
              (has ? v.toFixed(3) : 'n/a');
          }
        );
        if (has) {
          svg.append('text').attr('x', x0 + cell / 2).attr('y', y0 + cell / 2)
            .attr('dy', '0.32em').attr('text-anchor', 'middle')
            .attr('font-size', Math.min(12, cell / 3.2)).attr('font-weight', 600)
            .attr('fill', v >= 0.55 ? C.bg : C.ink).text(v.toFixed(2));
        }
      });
    });
    var lgY = m.top + cell * n + 16, lgW = Math.min(180, gridW);
    var defs = svg.append('defs');
    var grad = defs.append('linearGradient').attr('id', 'geo-heat-grad');
    [0, 0.5, 1].forEach(function (s) {
      grad.append('stop').attr('offset', (s * 100) + '%').attr('stop-color', color(s));
    });
    svg.append('rect').attr('x', m.left).attr('y', lgY).attr('width', lgW).attr('height', 10)
      .attr('rx', 3).attr('fill', 'url(#geo-heat-grad)').attr('stroke', C.line);
    svg.append('text').attr('x', m.left).attr('y', lgY + 24)
      .attr('fill', C.muted).attr('font-size', 10).text('0.0');
    svg.append('text').attr('x', m.left + lgW).attr('y', lgY + 24).attr('text-anchor', 'end')
      .attr('fill', C.muted).attr('font-size', 10).text('1.0 (identical sources)');
  }
  register(drawHeatmap);
})();
"""


# --------------------------------------------------------------------------- #
# Page assembly
# --------------------------------------------------------------------------- #
def _report_json_blob(report: dict) -> str:
    """Serialize the report for the client, escaping `</` so it can't close the script."""
    raw = json.dumps(report, ensure_ascii=False, default=str)
    return raw.replace("</", "<\\/")


def render_dashboard(report: dict) -> str:
    """Render a complete DARK HTML dashboard from a GeoReport dict.

    Tailwind + D3 v7 are loaded from CDNs (internet-required — the user's choice).
    All server-rendered text is HTML-escaped; the report is also injected as a JSON blob
    that the client-side script reads to build every D3 SVG chart.
    """
    brand = _e(report.get("brand", "GEO report"))
    body = "".join(
        [
            _hero(report),
            _gap(report),
            _findings(report),
            _recommendations(report),
            _metrics(report),
            _distinguishability(report),
            _reconciliation(report),
            _top_domains(report),
            _prompt_set(report),
            _prompts_used(report),
            _methodology(report),
            _transcript(report),
            _notes(report),
        ]
    )
    data_blob = _report_json_blob(report)
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEO report — {brand}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>{_TAILWIND_CONFIG}</script>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
</head>
<body class="min-h-screen bg-bg font-sans text-ink antialiased">
{_topbar()}
<main class="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6">
{body}
<footer class="border-t border-line pt-6 text-xs text-muted">
Measurement-honest GEO platform · every rate carries a 95% confidence interval ·
charts by D3.js v7, styling by Tailwind (CDN).
</footer>
</main>
<script type="application/json" id="geo-report">{data_blob}</script>
<script>{_D3_JS}</script>
</body>
</html>
"""
