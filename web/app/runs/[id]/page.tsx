"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, reportHtmlUrl, reportJsonUrl } from "@/lib/api";
import type { GeoReport, Interval } from "@/lib/types";

function isSynthetic(mode: string): boolean {
  const m = (mode || "").toLowerCase();
  return m.includes("synthetic") || m.includes("dry");
}

function fmtPct(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(1)}%`;
}

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString();
}

// Renders a rate as `point [lo, hi] (n=…)` — never a bare number (CI must be visible).
function CI({ iv }: { iv?: Interval }) {
  if (!iv) return <span className="muted">—</span>;
  return (
    <span>
      <span className="point">{fmtPct(iv.point)}</span>{" "}
      <span className="ci">
        [{fmtPct(iv.lo)}, {fmtPct(iv.hi)}] (n={iv.n})
      </span>
    </span>
  );
}

export default function ReportPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;

  const [report, setReport] = useState<GeoReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getReport(id)
      .then(setReport)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  const stats = useMemo(() => {
    if (!report) return null;
    const engineKeys = Object.keys(report.per_engine_metrics || {});
    const promptCount = report.prompt_set?.count ?? 0;
    const firstEngine = report.per_engine_metrics?.[engineKeys[0]];
    const nRuns = firstEngine?.n_runs ?? 0;
    const repeats = promptCount ? Math.round(nRuns / promptCount) : 0;
    const totalCitations = Object.values(report.top_domains || {}).reduce(
      (sum, list) =>
        sum + (list || []).reduce((s, [, count]) => s + (count || 0), 0),
      0,
    );
    const overlap = report.reconciliation?.overlap?.mean_pairwise_jaccard;
    return {
      engines: engineKeys.length,
      promptCount,
      repeats,
      totalCitations,
      overlap,
    };
  }, [report]);

  if (error) {
    return (
      <main className="container">
        <div className="actions-row">
          <Link href="/history" className="btn-link">
            ← History
          </Link>
        </div>
        <div className="banner error">
          <div className="big">Could not load report</div>
          <div className="sub">{error}</div>
        </div>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="container">
        <div className="loading-block">
          <span className="spinner" />
          Loading report…
        </div>
      </main>
    );
  }

  const synthetic = isSynthetic(report.mode);
  const engineKeys = Object.keys(report.per_engine_metrics || {});

  return (
    <main className="container wide">
      <div className="actions-row">
        <Link href="/history" className="btn-link">
          ← History
        </Link>
        <Link href="/" className="btn-link">
          + New analysis
        </Link>
      </div>

      <div className="report-header">
        <div style={{ flex: 1 }}>
          <h1 style={{ marginBottom: 6 }}>{report.brand}</h1>
          <div className="pills">
            <span className="muted">{report.category}</span>
            <span className={`pill mode ${synthetic ? "synthetic" : ""}`}>
              {report.mode}
            </span>
          </div>
        </div>
      </div>

      {synthetic && (
        <div className="banner synthetic">
          <div className="big">SYNTHETIC — not a real measurement</div>
          <div className="sub">
            This report was produced by a dry-run using synthetic, offline data.
            The numbers below illustrate the methodology; they do not reflect any
            live generative-engine behavior.
          </div>
        </div>
      )}

      {/* Stat tiles */}
      {stats && (
        <div className="tiles">
          <div className="tile">
            <div className="value cyan">{stats.engines}</div>
            <div className="label">Engines</div>
          </div>
          <div className="tile">
            <div className="value">
              {stats.promptCount} × {stats.repeats}
            </div>
            <div className="label">Prompts × repeats</div>
          </div>
          <div className="tile">
            <div className="value magenta">
              {stats.totalCitations.toLocaleString()}
            </div>
            <div className="label">Total citations</div>
          </div>
          <div className="tile">
            <div className="value">
              {stats.overlap === undefined ? "—" : fmtPct(stats.overlap)}
            </div>
            <div className="label">Mean cross-engine overlap</div>
          </div>
          <div className="tile">
            <div className="value" style={{ fontSize: "1.1rem", paddingTop: 8 }}>
              {fmtDate(report.generated_utc)}
            </div>
            <div className="label">Generated</div>
          </div>
        </div>
      )}

      {/* Findings */}
      {report.findings && report.findings.length > 0 && (
        <div className="card">
          <h2>Findings</h2>
          <div className="hint">Factual observations, restated verbatim.</div>
          <ul className="finding-list">
            {report.findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div className="card">
          <h2>Recommendations</h2>
          <div className="hint">
            Directional hypotheses, not guarantees — rendered verbatim.
          </div>
          <ul className="finding-list recs">
            {report.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Per-engine table */}
      <div className="card">
        <h2>Per-engine metrics</h2>
        <div className="hint">
          Every rate is shown as <code>point [lo, hi] (n)</code> — the confidence
          interval is always visible.
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Engine</th>
                <th>Mention rate</th>
                <th>Citation rate</th>
                <th>Share of voice</th>
                <th>Cited / mean rank</th>
              </tr>
            </thead>
            <tbody>
              {engineKeys.map((e) => {
                const m = report.per_engine_metrics[e];
                return (
                  <tr key={e}>
                    <td className="point">{e}</td>
                    <td>
                      <CI iv={m.mention} />
                    </td>
                    <td>
                      <CI iv={m.citation} />
                    </td>
                    <td>
                      <CI iv={m.share_of_voice} />
                    </td>
                    <td className="num muted">
                      {m.position
                        ? `${m.position.n_cited} cited` +
                          (m.position.mean_rank != null
                            ? ` · rank ${m.position.mean_rank.toFixed(1)}`
                            : "")
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Downloads */}
      <div className="card">
        <h2>Raw data</h2>
        <div className="actions-row" style={{ marginBottom: 0 }}>
          <a
            className="btn-link"
            href={reportJsonUrl(id!)}
            target="_blank"
            rel="noreferrer"
          >
            Download report JSON
          </a>
          <a
            className="btn-link"
            href={reportHtmlUrl(id!)}
            target="_blank"
            rel="noreferrer"
          >
            Open full dashboard ↗
          </a>
        </div>
      </div>

      {/* Full visual dashboard — reuses the tested backend D3 charts */}
      <div className="card">
        <h2>Full dashboard</h2>
        <div className="hint">
          Rendered by the backend (tested D3 charts), embedded below.
        </div>
        <iframe
          className="dash-frame"
          src={reportHtmlUrl(id!)}
          title="GEO report dashboard"
        />
      </div>
    </main>
  );
}
