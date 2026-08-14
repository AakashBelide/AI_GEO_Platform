# `app/` — the integrated GEO platform (Task A1)

The single entrypoint that wires the validated POCs into one end-to-end flow:

```
brand → prompts (R1) → engine runs (F3 live / synthetic) → fact store (F2)
      → metrics with CIs (R2/O1) → cross-engine reconciliation + methodology card (O3)
      → console tables + JSON report
```

The app **reuses the POC modules unchanged** (`app/_paths.py` puts each `pocs/<name>/` on
`sys.path`); nothing is copied. Integration logic lives in `pipeline.py`; the CLI in `geo.py`.

## Usage
```bash
# Offline dry-run (DEFAULT): synthetic data, $0, no network, deterministic
uv run python app/geo.py run \
    --brand "Asana" --category "project management software" \
    --target-domain asana.com \
    --competitor-domains monday.com,trello.com,clickup.com \
    --competitors "Monday.com,Trello,ClickUp"

# Live: real engines, budget-guarded ($2/provider). Persists to data/geo.sqlite.
uv run python app/geo.py run --brand "Asana" --category "..." \
    --target-domain asana.com --competitor-domains monday.com,trello.com \
    --repeats 8 --live
```

Key flags: `--engines` (default all four), `--prompts` (30), `--repeats` (5), `--seed`,
`--locale`, `--out-dir` (default `data/reports/`), `--live`.

```bash
# Render a saved JSON report into a modern dark HTML dashboard (Task A2, pocs/dashboard)
uv run python app/geo.py report --input data/reports/asana_2026-08-14.json
# -> writes data/reports/asana_2026-08-14.html; open in a browser (Tailwind + D3
#    load from CDN, so viewing needs internet)
```
The dashboard shows every rate with its 95% CI, flags the mention-vs-citation gap, gives
two-proportion-test distinguishability verdicts, and renders the methodology card verbatim.

## Safety / honesty
- **Dry-run is the default and spends nothing.** Live requires the explicit `--live` flag and
  runs under the same `CostLedger` guard the connectors use — a provider can never exceed $2.
- **Synthetic data is labeled as such** in every report (`mode`, `notes`) and must never be
  presented as a real measurement of a brand.
- Output carries **confidence intervals everywhere** and a **methodology card**; `--repeats < 5`
  emits a note that intervals will be wide / SoV may be degenerate.
- The JSON report and `data/geo.sqlite` are written under `data/` (gitignored).

## Tests
```bash
uv run pytest app/ -q     # 16 tests, offline (dry-run pipeline + CLI plumbing)
```
