// Thin typed client for the AI_GEO FastAPI backend.
// All calls run in the browser; the base URL is a NEXT_PUBLIC_ var so it can be
// injected at build or runtime. Every helper throws a readable Error on failure so
// pages can surface a graceful error state (the backend is often not running).

import type {
  BrandProfile,
  GeoReport,
  HealthResponse,
  RunCreated,
  RunDetail,
  RunRequest,
  RunSummary,
} from "./types";

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      `Could not reach the API at ${API_BASE}. Is the backend running? ` +
        `(uvicorn server.main:app --reload)`,
    );
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),

  createRun: (body: RunRequest) =>
    request<RunCreated>("/api/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listRuns: () => request<RunSummary[]>("/api/runs"),

  getRun: (id: number | string) => request<RunDetail>(`/api/runs/${id}`),

  getReport: (id: number | string) =>
    request<GeoReport>(`/api/runs/${id}/report`),

  listBrands: () => request<BrandProfile[]>("/api/brands"),

  saveBrand: (body: BrandProfile) =>
    request<{ id: number }>("/api/brands", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// URL helpers for links / iframes (not fetched through `request`).
export const reportJsonUrl = (id: number | string) =>
  `${API_BASE}/api/runs/${id}/report`;
export const reportHtmlUrl = (id: number | string) =>
  `${API_BASE}/api/runs/${id}/report.html`;
