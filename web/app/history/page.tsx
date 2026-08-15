"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { RunSummary } from "@/lib/types";

function fmtDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString();
}

function isSynthetic(mode: string): boolean {
  const m = mode.toLowerCase();
  return m.includes("synthetic") || m.includes("dry");
}

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRuns()
      .then(setRuns)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="container wide">
      <div className="report-header">
        <div style={{ flex: 1 }}>
          <h1>History</h1>
          <p className="subtitle">Past analysis runs.</p>
        </div>
        <Link href="/" className="btn-link">
          + New analysis
        </Link>
      </div>

      {error && (
        <div className="banner error">
          <div className="big">Could not load history</div>
          <div className="sub">{error}</div>
        </div>
      )}

      {!error && runs === null && (
        <div className="loading-block">
          <span className="spinner" />
          Loading runs…
        </div>
      )}

      {!error && runs !== null && runs.length === 0 && (
        <div className="empty">
          No runs yet. <Link href="/">Start a new analysis →</Link>
        </div>
      )}

      {!error && runs !== null && runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Brand</th>
                <th>Category</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Cost</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{r.brand}</td>
                  <td className="muted">{r.category}</td>
                  <td>
                    <span
                      className={`pill mode ${
                        isSynthetic(r.mode) ? "synthetic" : ""
                      }`}
                    >
                      {r.mode}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`pill ${
                        r.status === "done"
                          ? "done"
                          : r.status === "error"
                            ? "error"
                            : "running"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="num">${(r.actual_cost || 0).toFixed(2)}</td>
                  <td className="muted">{fmtDate(r.created_at)}</td>
                  <td>
                    <Link href={`/runs/${r.id}`}>View →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
