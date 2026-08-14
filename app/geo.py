"""`geo` CLI — the single entrypoint for the GEO platform (Task A1).

    uv run python app/geo.py run --brand "Asana" --category "project management software" \
        --target-domain asana.com --competitor-domains monday.com,trello.com,clickup.com

Default is an OFFLINE dry-run (synthetic data, $0). Pass --live to call the real engines
under the $2/provider budget guard. Prints human-readable tables and writes a machine-readable
JSON report under data/reports/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import _paths  # noqa: F401  (side effect: put pocs/* on sys.path)
from dashboard import render_dashboard
from insights import generate_findings, generate_recommendations
from insights import top_domains as compute_top_domains
from pipeline import GeoConfig, GeoReport, run_pipeline
from store_reader import read_evidence


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (value or "").split(",") if v.strip())


def _fmt_est(e: dict) -> str:
    return (f"{e['point']:.3f} [{e['lo']:.3f}, {e['hi']:.3f}] "
            f"(n={e['n']}, {int(e['confidence'] * 100)}% CI)")


def render(report: GeoReport) -> str:
    r = report.to_dict()
    out: list[str] = []
    out.append(f"\n=== GEO report: {r['brand']} ({r['category']}) ===")
    out.append(f"mode: {r['mode']}  |  generated: {r['generated_utc']}")

    ps = r["prompt_set"]
    out.append(f"\n-- prompt set ({ps['count']}) --")
    out.append(f"   skew: {ps['skew']['message']}")
    out.append("   intents: " + ", ".join(
        f"{k} {int(v['count'])} ({v['fraction']:.0%})" for k, v in ps["intents"].items()))

    out.append("\n-- per-engine metrics (95% CIs) --")
    for engine, m in r["per_engine_metrics"].items():
        out.append(f"   {engine} (n={m['n_runs']}):")
        out.append(f"      mention   {_fmt_est(m['mention'])}")
        out.append(f"      citation  {_fmt_est(m['citation'])}")
        out.append(f"      SoV       {_fmt_est(m['share_of_voice'])}")

    recon = r.get("reconciliation") or {}
    if recon:
        ov = recon["overlap"]
        out.append("\n-- cross-engine reconciliation --")
        out.append(f"   mean pairwise citation overlap: {ov['mean_pairwise_jaccard']:.3f}")
        out.append(f"   unique domains/engine: {ov['per_engine_unique_domains']}")
        for f in recon.get("divergence", []):
            out.append(f"   {f['engine']} over-indexes '{f['ecosystem']}' "
                       f"(+{f['delta']:.0%} vs mean)")
        out.append("")
        out.append(_methodology_md(recon["methodology"]))

    if r.get("spend"):
        out.append("\n-- spend --")
        for e, s in r["spend"].items():
            out.append(f"   {e:<11} ${s['spent']:.4f} / ${s['cap']:.2f}")

    if r.get("notes"):
        out.append("\n-- notes --")
        out += [f"   * {n}" for n in r["notes"]]
    return "\n".join(out)


def _methodology_md(card: dict) -> str:
    lines = ["-- methodology card --",
             f"   generated: {card['generated_utc']}",
             f"   prompts × repeats: {card['n_prompts']} × {card['repeats_per_prompt']}",
             f"   locale: {card['locale']}",
             f"   normalization: {card['domain_normalization']}"]
    lines.append("   caveats:")
    lines += [f"     - {c}" for c in card.get("caveats", [])]
    return "\n".join(lines)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "brand"


def write_report(report: GeoReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    path = out_dir / f"{_slug(report.brand)}_{day}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return path


def _build_config(args) -> GeoConfig:
    return GeoConfig(
        brand=args.brand, category=args.category,
        aliases=_csv(args.aliases), competitors=_csv(args.competitors),
        target_domain=args.target_domain,
        competitor_domains=_csv(args.competitor_domains),
        engines=_csv(args.engines) or GeoConfig.engines,
        n_prompts=args.prompts, repeats=args.repeats, live=args.live,
        locale=args.locale, seed=args.seed,
    )


def cmd_run(args) -> int:
    config = _build_config(args)
    ledger = store = None
    if config.live:
        from budget import CostLedger
        from dotenv import load_dotenv
        from factstore import FactStore
        load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))
        ledger = CostLedger(path=Path("data/cost_ledger.json"),
                            cap_usd=float(os.getenv("BUDGET_USD_PER_PROVIDER", "2.00")))
        store = FactStore(path="data/geo.sqlite")

    report = run_pipeline(config, ledger=ledger, store=store)
    print(render(report))
    path = write_report(report, Path(args.out_dir))
    print(f"\nJSON report written: {path}")
    if store is not None:
        store.close()
    return 0


def _default_html_path(input_path: Path, out_dir: Path) -> Path:
    return out_dir / (input_path.stem + ".html")


def _enrich_from_store(report: dict, store_path: str) -> dict:
    """Attach the raw evidence + interpretation layer to a report using the fact store.

    Lets a JSON report written before the evidence layer existed be re-rendered with its
    prompts / transcript / top-domains / findings / recommendations — with **zero spend**,
    since everything is read back from `data/geo.sqlite` (no engine is re-called).
    """
    evidence = read_evidence(store_path)
    report["prompts"] = evidence["prompts"]
    report["transcript"] = evidence["transcript"]
    report["top_domains"] = compute_top_domains(evidence["citations_by_engine"])
    report["target_domain"] = evidence["target_domain"]
    report["findings"] = generate_findings(report)
    report["recommendations"] = generate_recommendations(report)
    return report


def cmd_report(args) -> int:
    """Render a saved JSON GeoReport into a self-contained HTML dashboard (Task A2).

    With ``--store``, the report is first enriched with the raw evidence (prompts,
    per-engine answers + citations, top cited domains) and the interpretation layer
    (findings, recommendations) reconstructed from the fact store — no engine re-called.
    """
    input_path = Path(args.input)
    report = json.loads(input_path.read_text())
    if args.store:
        report = _enrich_from_store(report, args.store)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output) if args.output else _default_html_path(input_path, out_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_dashboard(report))
    print(f"HTML dashboard written: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="geo", description="Measurement-honest GEO platform.")
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the end-to-end pipeline for a brand")
    run.add_argument("--brand", required=True)
    run.add_argument("--category", required=True)
    run.add_argument("--aliases", help="comma-separated brand aliases")
    run.add_argument("--competitors", help="comma-separated competitor names")
    run.add_argument("--target-domain", help="the brand's registrable domain")
    run.add_argument("--competitor-domains", help="comma-separated competitor domains")
    run.add_argument("--engines", help=f"comma-separated (default: {','.join(GeoConfig.engines)})")
    run.add_argument("--prompts", type=int, default=30, help="prompt-set size (default 30)")
    run.add_argument("--repeats", type=int, default=5, help="repeats per prompt (default 5)")
    run.add_argument("--live", action="store_true",
                     help="call real engines (budget-guarded); default is offline dry-run")
    run.add_argument("--locale", default="us")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--out-dir", default="data/reports")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="render a saved JSON report into an HTML dashboard")
    rep.add_argument("--input", required=True, help="path to a GeoReport JSON file")
    rep.add_argument("--output", help="HTML output path (default: <input>.html in --out-dir)")
    rep.add_argument("--out-dir", default="data/reports",
                     help="directory for the default output path (default: data/reports)")
    rep.add_argument("--store",
                     help="fact-store path (e.g. data/geo.sqlite) to reconstruct the "
                          "prompts/transcript/top-domains + findings/recommendations "
                          "(no engine is re-called; zero spend)")
    rep.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
