"""Local reporting dashboard (Task A2): a GeoReport → one self-contained HTML file.

Turns the machine-readable report emitted by `app/geo.py run` (the `GeoReport`
dataclass in `app/pipeline.py`) into an honesty-first HTML dashboard that opens
directly in a browser with **no server, no network, no external assets**. All charts
are hand-written inline SVG; all styling is inline CSS. Pure functions
(`report dict → HTML string`), so the whole thing is offline-testable.

Honesty-first choices, mirrored from the rest of the platform:
  * every rate is drawn as a point estimate **with its confidence interval** — never a
    bare score (the project's whole thesis; see RESEARCH.md / `pocs/rigor`).
  * a synthetic dry-run is loudly flagged as NOT a real measurement.
  * the "mentioned a lot, cited ~never" gap is made visually obvious (the headline
    finding on the real Asana data: OpenAI & Anthropic mention ~80% but cite the
    brand's own domain 0%).
  * cross-engine pairs are checked for statistical distinguishability with the rigor
    POC's `two_proportion_test` — the dashboard refuses to imply a difference that is
    within noise.
  * the methodology card (incl. the Gemini-redirect caveat) is rendered verbatim.

Reuses `pocs/rigor` via the same sibling-dir sys.path shim `pocs/metrics/metrics.py`
uses — the stats live in one place only.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

# POC path shim: reuse the sibling rigor POC's statistics without duplicating them
# (identical pattern to pocs/metrics/metrics.py).
_RIGOR = Path(__file__).resolve().parent.parent / "rigor"
if str(_RIGOR) not in sys.path:
    sys.path.insert(0, str(_RIGOR))

from rigor import two_proportion_test  # noqa: E402

# --------------------------------------------------------------------------- #
# Palette (validated data-viz default; light, muted, professional)
# --------------------------------------------------------------------------- #
INK = "#0b0b0b"       # primary text
INK2 = "#52514e"      # secondary text
MUTED = "#898781"     # axis / captions
GRID = "#e1e0d9"      # hairline gridlines
AXIS = "#c3c2b7"      # baseline
SURFACE = "#fcfcfb"   # card surface
PLANE = "#f9f9f7"     # page plane
SERIES = "#2a78d6"    # point-estimate mark (categorical slot 1)
BAND = "#cde2fb"      # CI band fill (blue, step 100)
GOOD = "#0ca30c"      # status: good
WARN = "#fab219"      # status: warning
CRIT = "#d03b3b"      # status: critical
BORDER = "rgba(11,11,11,0.10)"

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


# --------------------------------------------------------------------------- #
# The core visual: a horizontal CI bar on a 0..1 proportion scale (inline SVG)
# --------------------------------------------------------------------------- #
def ci_bar_svg(
    point: float,
    lo: float,
    hi: float,
    *,
    n: int | None = None,
    label: str | None = None,
    width: int = 240,
    height: int = 24,
    color: str = SERIES,
    band: str = BAND,
) -> str:
    """A hand-written inline-SVG bar for a 0..1 proportion with a CI whisker/band.

    Draws (left→right on a fixed 0–100% track): faint quarter gridlines, a shaded
    band spanning [lo, hi], a whisker with end caps, a point-estimate dot, and the
    point value as text. Reused for mention rate, citation rate and share-of-voice.
    Values are clamped to [0, 1] so a malformed estimate can never overflow the track.
    """
    def clamp(v: float) -> float:
        return 0.0 if v < 0 else 1.0 if v > 1 else v

    p, lo_c, hi_c = clamp(point), clamp(lo), clamp(hi)
    if hi_c < lo_c:
        lo_c, hi_c = hi_c, lo_c

    x0, x1 = 6.0, float(width - 60)   # leave room for the value label on the right
    mid = height / 2.0

    def x(v: float) -> float:
        return x0 + v * (x1 - x0)

    aria = _e(label or "estimate")
    parts: list[str] = [
        f'<svg class="cibar" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{aria} {p * 100:.0f} percent, '
        f'95% interval {lo_c * 100:.0f} to {hi_c * 100:.0f} percent">'
    ]
    tip = f"{label + ': ' if label else ''}{_pct(p)} (95% CI {_pct(lo_c)}–{_pct(hi_c)}"
    tip += f", n={n})" if n is not None else ")"
    parts.append(f"<title>{_e(tip)}</title>")

    # quarter gridlines + baseline
    for frac in (0.25, 0.5, 0.75):
        gx = x(frac)
        parts.append(
            f'<line x1="{gx:.1f}" y1="3" x2="{gx:.1f}" y2="{height - 3}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
    parts.append(
        f'<line x1="{x0:.1f}" y1="{mid:.1f}" x2="{x1:.1f}" y2="{mid:.1f}" '
        f'stroke="{AXIS}" stroke-width="1"/>'
    )

    # CI band
    bx, bw = x(lo_c), max(1.0, x(hi_c) - x(lo_c))
    parts.append(
        f'<rect x="{bx:.1f}" y="{mid - 5:.1f}" width="{bw:.1f}" height="10" rx="2" '
        f'fill="{band}"/>'
    )
    # whisker caps
    for cx in (x(lo_c), x(hi_c)):
        parts.append(
            f'<line x1="{cx:.1f}" y1="{mid - 5:.1f}" x2="{cx:.1f}" y2="{mid + 5:.1f}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )
    # point-estimate dot
    parts.append(
        f'<circle cx="{x(p):.1f}" cy="{mid:.1f}" r="3.5" fill="{color}" '
        f'stroke="{SURFACE}" stroke-width="1"/>'
    )
    # value label
    parts.append(
        f'<text x="{x1 + 6:.1f}" y="{mid + 4:.1f}" font-size="11" '
        f'fill="{INK}" font-weight="600">{_pct(p)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def _header(r: dict) -> str:
    brand = _e(r.get("brand", "—"))
    category = _e(r.get("category", "—"))
    mode = str(r.get("mode", "—"))
    generated = _e(r.get("generated_utc", "—"))
    total_spend = sum(float(v.get("spent", 0.0)) for v in (r.get("spend") or {}).values())

    synthetic = "synthetic" in mode.lower() or "dry-run" in mode.lower()
    banner = ""
    if synthetic:
        banner = (
            f'<div class="banner banner-warn">SYNTHETIC DRY-RUN — this is '
            f'<strong>not a real measurement</strong> of {brand}. Deterministic '
            f"fabricated data for wiring/demo only.</div>"
        )
    mode_badge = (
        f'<span class="badge badge-warn">{_e(mode)}</span>'
        if synthetic
        else f'<span class="badge badge-ok">{_e(mode)}</span>'
    )
    return f"""
    <header>
      <div class="eyebrow">Measurement-honest GEO report</div>
      <h1>{brand}</h1>
      <div class="sub">{category}</div>
      <div class="meta">
        {mode_badge}
        <span>generated {generated}</span>
        <span>total spend ${total_spend:.2f}</span>
      </div>
      {banner}
    </header>
    """


def _prompt_set(r: dict) -> str:
    ps = r.get("prompt_set") or {}
    count = ps.get("count", "—")
    intents = ps.get("intents") or {}
    skew = ps.get("skew") or {}
    skew_ok = bool(skew.get("ok", False))
    skew_msg = _e(skew.get("message", "—"))

    chips = "".join(
        f'<span class="chip"><b>{_e(k)}</b> {int(v.get("count", 0))} '
        f'({v.get("fraction", 0.0) * 100:.0f}%)</span>'
        for k, v in intents.items()
    )
    skew_cls = "verdict-ok" if skew_ok else "verdict-bad"
    return f"""
    <section>
      <h2>Prompt set</h2>
      <p class="lead">{_e(count)} prompts &middot; intent mix (target 80 / 10 / 10):</p>
      <div class="chips">{chips}</div>
      <div class="{skew_cls}">Branded-skew check: {skew_msg}</div>
    </section>
    """


def _metrics_table(r: dict) -> str:
    per = r.get("per_engine_metrics") or {}
    rows: list[str] = []
    for engine, m in per.items():
        n_runs = m.get("n_runs", 0)
        cells = []
        for key in ("mention", "citation", "share_of_voice"):
            est = m.get(key) or {}
            cells.append(
                "<td>"
                + ci_bar_svg(
                    float(est.get("point", 0.0)),
                    float(est.get("lo", 0.0)),
                    float(est.get("hi", 0.0)),
                    n=int(est.get("n", 0) or 0),
                    label=key.replace("_", " "),
                )
                + "</td>"
            )
        rows.append(
            f'<tr><th scope="row">{_e(engine)}<span class="nrun">n={_e(n_runs)}</span>'
            f"</th>{''.join(cells)}</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="4" class="muted">no per-engine metrics</td></tr>')
    return f"""
    <section>
      <h2>Per-engine metrics <span class="hint">point ● with 95% confidence band</span></h2>
      <table class="metrics">
        <thead><tr><th>engine</th><th>mention rate</th><th>citation rate</th>
          <th>share of voice</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p class="caption">Scale is 0–100%. Wide bands = high uncertainty (small n /
      near-degenerate). No single-run point scores are shown without an interval.</p>
    </section>
    """


def _gap_callout(r: dict) -> str:
    """The headline finding: mentioned a lot, but own domain cited ~never."""
    per = r.get("per_engine_metrics") or {}
    cards: list[str] = []
    flagged = 0
    for engine, m in per.items():
        mention = m.get("mention") or {}
        citation = m.get("citation") or {}
        mp = float(mention.get("point", 0.0))
        cp = float(citation.get("point", 0.0))
        is_gap = mp >= _GAP_MENTION_MIN and cp <= _GAP_CITATION_MAX
        if is_gap:
            flagged += 1
        badge = (
            '<span class="badge badge-crit">mentioned, not cited</span>'
            if is_gap
            else '<span class="badge badge-ok">cites its own domain</span>'
        )
        cls = "gapcard flagged" if is_gap else "gapcard"
        mbar = ci_bar_svg(
            mp, float(mention.get("lo", 0.0)), float(mention.get("hi", 0.0)),
            n=int(mention.get("n", 0) or 0), label="mention", color=SERIES,
        )
        cbar = ci_bar_svg(
            cp, float(citation.get("lo", 0.0)), float(citation.get("hi", 0.0)),
            n=int(citation.get("n", 0) or 0), label="citation",
            color=CRIT if is_gap else SERIES, band="#f7d6d6" if is_gap else BAND,
        )
        cards.append(
            f'<div class="{cls}"><div class="gaphead">{_e(engine)} {badge}</div>'
            f'<div class="gaprow"><span class="glab">mention</span>{mbar}</div>'
            f'<div class="gaprow"><span class="glab">citation</span>{cbar}</div>'
            f"</div>"
        )
    lead = (
        f"<strong>{flagged}</strong> engine(s) mention "
        f"{_e(r.get('brand', 'the brand'))} often but cite its own domain at/near zero — "
        "the answer names the brand while sending the citation elsewhere."
        if flagged
        else "No engine shows the mention-without-citation gap on this run."
    )
    return f"""
    <section class="gap">
      <h2>Mention vs. citation gap <span class="hint">the headline finding</span></h2>
      <p class="lead">{lead}</p>
      <div class="gapgrid">{''.join(cards) or '<p class="muted">no engines</p>'}</div>
    </section>
    """


def _reconciliation(r: dict) -> str:
    recon = r.get("reconciliation") or {}
    if not recon:
        return """
    <section>
      <h2>Cross-engine reconciliation</h2>
      <p class="muted">Not available — reconciliation needs ≥2 engines and a target/
      competitor domain. Skipped for this report.</p>
    </section>
    """
    overlap = recon.get("overlap") or {}
    mean_j = overlap.get("mean_pairwise_jaccard")
    uniq = overlap.get("per_engine_unique_domains") or {}
    uniq_cells = "".join(
        f'<span class="chip"><b>{_e(e)}</b> {_e(c)}</span>' for e, c in uniq.items()
    )
    divergence = recon.get("divergence") or []
    if divergence:
        div_items = "".join(
            f"<li><b>{_e(f.get('engine'))}</b> over-indexes "
            f"<b>{_e(f.get('ecosystem'))}</b> (+{float(f.get('delta', 0.0)) * 100:.0f}% "
            f"vs cross-engine mean)</li>"
            for f in divergence
        )
        div_block = f"<ul class='divlist'>{div_items}</ul>"
    else:
        div_block = (
            '<p class="muted">No engine over-indexes a single source ecosystem beyond '
            "the divergence threshold on this run.</p>"
        )
    return f"""
    <section>
      <h2>Cross-engine reconciliation</h2>
      <div class="statrow">
        <div class="stat"><div class="statnum">{_num(mean_j, 3)}</div>
          <div class="statlab">mean pairwise citation overlap (Jaccard)</div></div>
      </div>
      <p class="lead">Unique cited domains per engine:</p>
      <div class="chips">{uniq_cells}</div>
      <p class="lead">Source-ecosystem divergence:</p>
      {div_block}
    </section>
    """


def _distinguishability(r: dict) -> str:
    """Are engine pairs actually distinguishable on citation rate, or within noise?"""
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
            if res.distinguishable:
                verdict = '<span class="verdict-ok">distinguishable</span>'
            else:
                verdict = '<span class="verdict-bad">NOT distinguishable (within noise)</span>'
            rows.append(
                f'<li><b>{_e(a)}</b> vs <b>{_e(b)}</b>: {verdict} '
                f'<span class="muted">(Δ={res.diff * 100:+.0f}pp, p={res.p_value:.3f})</span></li>'
            )
    body = (
        f"<ul class='distlist'>{''.join(rows)}</ul>"
        if rows
        else '<p class="muted">Need ≥2 engines with runs to test distinguishability.</p>'
    )
    return f"""
    <section>
      <h2>Statistical distinguishability <span class="hint">citation rate, two-proportion
        z-test (α=0.05)</span></h2>
      <p class="lead">Where a pair is <em>not</em> distinguishable, the dashboard does not
      claim one engine cites the brand more than the other — the gap is within noise.</p>
      {body}
    </section>
    """


def _methodology(r: dict) -> str:
    card = ((r.get("reconciliation") or {}).get("methodology")) or {}
    if not card:
        return """
    <section>
      <h2>Methodology card</h2>
      <p class="muted">No methodology card in this report (reconciliation skipped).</p>
    </section>
    """
    access = card.get("access_method") or {}
    engines = card.get("engines") or {}
    access_rows = "".join(
        f"<tr><td>{_e(e)}</td><td>{_e(engines.get(e, '—'))}</td>"
        f"<td>{_e(access.get(e, '—'))}</td></tr>"
        for e in sorted(set(access) | set(engines))
    )
    caveats = "".join(f"<li>{_e(c)}</li>" for c in (card.get("caveats") or []))
    fields = [
        ("generated", card.get("generated_utc")),
        ("prompts × repeats", f"{card.get('n_prompts')} × {card.get('repeats_per_prompt')}"),
        ("locale", card.get("locale")),
        ("domain normalization", card.get("domain_normalization")),
    ]
    field_rows = "".join(
        f'<div class="mfield"><div class="mkey">{_e(k)}</div>'
        f'<div class="mval">{_e(v)}</div></div>'
        for k, v in fields
    )
    return f"""
    <section>
      <h2>Methodology card</h2>
      <div class="mfields">{field_rows}</div>
      <table class="access">
        <thead><tr><th>engine</th><th>model</th><th>access method</th></tr></thead>
        <tbody>{access_rows}</tbody>
      </table>
      <div class="caveats"><div class="clab">Caveats (verbatim)</div>
        <ul>{caveats}</ul></div>
    </section>
    """


def _notes(r: dict) -> str:
    notes = r.get("notes") or []
    if not notes:
        return ""
    items = "".join(f"<li>{_e(n)}</li>" for n in notes)
    return f"""
    <section>
      <h2>Notes</h2>
      <ul class="notes">{items}</ul>
    </section>
    """


# --------------------------------------------------------------------------- #
# Page assembly
# --------------------------------------------------------------------------- #
_CSS = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: {PLANE}; color: {INK};
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5; font-size: 15px;
}}
.wrap {{ max-width: 900px; margin: 0 auto; padding: 32px 20px 64px; }}
header {{ border-bottom: 1px solid {BORDER}; padding-bottom: 20px; margin-bottom: 8px; }}
.eyebrow {{ text-transform: uppercase; letter-spacing: .08em; font-size: 11px;
  color: {MUTED}; font-weight: 600; }}
h1 {{ margin: 4px 0 2px; font-size: 30px; }}
h2 {{ font-size: 18px; margin: 0 0 12px; }}
.sub {{ color: {INK2}; font-size: 16px; }}
.meta {{ margin-top: 12px; display: flex; gap: 14px; flex-wrap: wrap;
  align-items: center; color: {INK2}; font-size: 13px; }}
.hint {{ font-weight: 400; font-size: 12px; color: {MUTED}; }}
.badge {{ display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 12px; font-weight: 600; }}
.badge-ok {{ background: #e4f3e4; color: #146c14; }}
.badge-warn {{ background: #fbefd2; color: #8a5b00; }}
.badge-crit {{ background: #fadbdb; color: #a3241f; }}
.banner {{ margin-top: 16px; padding: 12px 14px; border-radius: 8px; font-size: 14px; }}
.banner-warn {{ background: #fbefd2; color: #7a4f00; border: 1px solid #f0d38a; }}
section {{ margin: 30px 0; padding-top: 8px; }}
.lead {{ color: {INK2}; margin: 4px 0 10px; }}
.caption, .muted {{ color: {MUTED}; font-size: 12.5px; }}
.chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0; }}
.chip {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
  padding: 4px 10px; font-size: 13px; }}
.chip b {{ color: {INK}; }}
.verdict-ok {{ color: {GOOD}; font-weight: 600; }}
.verdict-bad {{ color: {CRIT}; font-weight: 600; }}
table {{ border-collapse: collapse; width: 100%; }}
table.metrics th, table.metrics td {{ text-align: left; padding: 8px 10px;
  border-bottom: 1px solid {GRID}; vertical-align: middle; }}
table.metrics thead th {{ font-size: 12px; color: {MUTED}; font-weight: 600;
  text-transform: uppercase; letter-spacing: .04em; }}
table.metrics th[scope=row] {{ font-weight: 600; white-space: nowrap; }}
.nrun {{ display: block; font-weight: 400; font-size: 11px; color: {MUTED}; }}
.gap {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
  padding: 18px 20px; }}
.gapgrid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px; }}
.gapcard {{ border: 1px solid {GRID}; border-radius: 10px; padding: 12px 14px;
  background: {PLANE}; }}
.gapcard.flagged {{ border-color: {CRIT}; background: #fdf4f4; }}
.gaphead {{ font-weight: 600; margin-bottom: 6px; display: flex; gap: 8px;
  align-items: center; justify-content: space-between; }}
.gaprow {{ display: flex; align-items: center; gap: 8px; }}
.glab {{ width: 62px; font-size: 12px; color: {INK2}; }}
.statrow {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }}
.stat {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
  padding: 12px 16px; min-width: 180px; }}
.statnum {{ font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }}
.statlab {{ color: {MUTED}; font-size: 12px; }}
.divlist, .distlist, .notes {{ margin: 4px 0; padding-left: 20px; }}
.divlist li, .distlist li, .notes li {{ margin: 4px 0; }}
.mfields {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px; margin-bottom: 14px; }}
.mfield {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
  padding: 8px 12px; }}
.mkey {{ font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
  color: {MUTED}; }}
.mval {{ font-size: 13px; color: {INK}; word-break: break-word; }}
table.access th, table.access td {{ text-align: left; padding: 6px 10px; font-size: 13px;
  border-bottom: 1px solid {GRID}; }}
table.access thead th {{ color: {MUTED}; font-size: 11px; text-transform: uppercase; }}
.caveats {{ margin-top: 14px; border-left: 3px solid {WARN}; padding: 4px 0 4px 14px; }}
.clab {{ font-weight: 600; font-size: 13px; margin-bottom: 4px; }}
.caveats ul {{ margin: 4px 0; padding-left: 18px; color: {INK2}; font-size: 13.5px; }}
svg.cibar {{ display: inline-block; vertical-align: middle; }}
footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid {BORDER};
  color: {MUTED}; font-size: 12px; }}
"""


def render_dashboard(report: dict) -> str:
    """Render a complete, standalone HTML document from a GeoReport dict.

    No external assets, no scripts, no network — everything (CSS + SVG charts) is
    inlined, so the returned string is a file that opens directly in any browser.
    """
    brand = _e(report.get("brand", "GEO report"))
    body = "".join(
        [
            _header(report),
            _prompt_set(report),
            _metrics_table(report),
            _gap_callout(report),
            _reconciliation(report),
            _distinguishability(report),
            _methodology(report),
            _notes(report),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEO report — {brand}</title>
<style>{_CSS}</style>
</head>
<body>
<main class="wrap">
{body}
<footer>Measurement-honest GEO platform · rates carry 95% confidence intervals ·
self-contained offline report (no network, no external assets).</footer>
</main>
</body>
</html>
"""
