"""SQLite persistence for the web app — the run/report/brand index (`app.db`).

Separate from the raw fact store (`data/geo.sqlite`, written by the pipeline): this DB
indexes analysis *runs*, stores each run's `GeoReport` JSON, and keeps reusable brand
profiles so a user can browse history and re-analyze any brand. Path from `GEO_APP_DB`
(default `data/app.db`, gitignored). Stdlib sqlite3, a fresh connection per call.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime

_SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    domain TEXT,
    aliases_json TEXT,
    competitors_json TEXT,
    competitor_domains_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(name, category)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    mode TEXT NOT NULL,
    config_json TEXT NOT NULL,
    status TEXT NOT NULL,                 -- queued | running | done | error
    progress_pct REAL DEFAULT 0,
    progress_note TEXT,
    est_cost REAL DEFAULT 0,
    actual_cost REAL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    run_id INTEGER PRIMARY KEY REFERENCES runs(id),
    report_json TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def db_path() -> str:
    return os.getenv("GEO_APP_DB", "data/app.db")


def _conn() -> sqlite3.Connection:
    path = db_path()
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# runs / reports
# --------------------------------------------------------------------------- #
def create_run(brand: str, category: str, mode: str, config: dict,
               *, est_cost: float = 0.0, status: str = "running") -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO runs(brand,category,mode,config_json,status,est_cost,created_at,"
            "started_at) VALUES (?,?,?,?,?,?,?,?)",
            (brand, category, mode, json.dumps(config), status, est_cost, _now(), _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def finish_run(run_id: int, *, status: str, actual_cost: float = 0.0,
               error: str | None = None, progress_pct: float = 100.0) -> None:
    conn = _conn()
    try:
        conn.execute(
            "UPDATE runs SET status=?, actual_cost=?, error=?, progress_pct=?, finished_at=? "
            "WHERE id=?",
            (status, actual_cost, error, progress_pct, _now(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_report(run_id: int, report: dict) -> None:
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO reports(run_id, report_json) VALUES (?,?)",
            (run_id, json.dumps(report)),
        )
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: int) -> dict | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_runs(limit: int = 100, offset: int = 0) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id,brand,category,mode,status,progress_pct,actual_cost,created_at,"
            "finished_at FROM runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report(run_id: int) -> dict | None:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT report_json FROM reports WHERE run_id=?", (run_id,)).fetchone()
        return json.loads(row["report_json"]) if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# brands (reusable profiles)
# --------------------------------------------------------------------------- #
def upsert_brand(name: str, category: str, *, domain: str | None = None,
                 aliases: list[str] | None = None, competitors: list[str] | None = None,
                 competitor_domains: list[str] | None = None) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO brands(name,category,domain,aliases_json,competitors_json,"
            "competitor_domains_json,created_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(name,category) DO UPDATE SET domain=excluded.domain, "
            "aliases_json=excluded.aliases_json, competitors_json=excluded.competitors_json, "
            "competitor_domains_json=excluded.competitor_domains_json",
            (name, category, domain, json.dumps(aliases or []),
             json.dumps(competitors or []), json.dumps(competitor_domains or []), _now()),
        )
        conn.commit()
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = conn.execute(
            "SELECT id FROM brands WHERE name=? AND category=?", (name, category)).fetchone()
        return int(row["id"])
    finally:
        conn.close()


def list_brands() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("aliases_json", "competitors_json", "competitor_domains_json"):
                d[k.removesuffix("_json")] = json.loads(d.pop(k) or "[]")
            out.append(d)
        return out
    finally:
        conn.close()
