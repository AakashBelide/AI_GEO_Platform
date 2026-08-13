"""Append-only fact store for GEO measurement runs (Task F2).

Every engine call is one immutable row in ``runs`` (never updated), so variance
and month-over-month drift can be computed from history. Schema follows
RESEARCH.md §3.4. Uses stdlib sqlite3 — no ORM needed at prototype scale.

The raw API payload is stored as JSON in ``runs.raw_response`` so re-analysis
never needs to re-call the API (cost control) and the parser can evolve without
data loss.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id  INTEGER PRIMARY KEY,
    text       TEXT NOT NULL,
    intent     TEXT,          -- informational | commercial | navigational
    category   TEXT,
    locale     TEXT DEFAULT 'us',
    active      INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS runs (
    run_id        INTEGER PRIMARY KEY,
    prompt_id     INTEGER NOT NULL REFERENCES prompts(prompt_id),
    engine        TEXT NOT NULL,
    model         TEXT NOT NULL,
    temperature   REAL,
    run_index     INTEGER NOT NULL,   -- 0..N-1 repeat within a batch
    ts            TEXT NOT NULL,       -- ISO8601 UTC
    raw_response  TEXT,                -- JSON blob (full API payload)
    answer_text   TEXT,
    est_cost_usd  REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS citations (
    citation_id     INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(run_id),
    cited_url       TEXT,
    domain          TEXT,
    position        INTEGER,
    is_target_brand INTEGER DEFAULT 0,
    sentiment       TEXT
);
CREATE TABLE IF NOT EXISTS mentions (
    mention_id      INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(run_id),
    entity          TEXT,
    is_target_brand INTEGER DEFAULT 0,
    sentiment       TEXT,
    char_offset     INTEGER
);
CREATE TABLE IF NOT EXISTS content_scores (
    page_url              TEXT PRIMARY KEY,
    crawl_ts              TEXT,
    stat_density          REAL,
    quote_count           INTEGER,
    citation_count        INTEGER,
    heading_structure_score REAL,
    readability           REAL,
    has_schema            INTEGER
);
CREATE INDEX IF NOT EXISTS idx_runs_prompt ON runs(prompt_id);
CREATE INDEX IF NOT EXISTS idx_citations_run ON citations(run_id);
CREATE INDEX IF NOT EXISTS idx_mentions_run ON mentions(run_id);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class FactStore:
    """Thin append-only wrapper over a SQLite database."""

    path: str = ":memory:"

    def __post_init__(self) -> None:
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- prompts ----
    def add_prompt(
        self, text: str, *, intent: str | None = None, category: str | None = None,
        locale: str = "us", active: bool = True,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO prompts(text,intent,category,locale,active) VALUES (?,?,?,?,?)",
            (text, intent, category, locale, int(active)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ---- runs (append-only) ----
    def add_run(
        self, prompt_id: int, *, engine: str, model: str, run_index: int,
        temperature: float | None = 0.0, raw_response: dict | None = None,
        answer_text: str = "", est_cost_usd: float = 0.0, ts: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs(prompt_id,engine,model,temperature,run_index,ts,"
            "raw_response,answer_text,est_cost_usd) VALUES (?,?,?,?,?,?,?,?,?)",
            (prompt_id, engine, model, temperature, run_index, ts or _utcnow(),
             json.dumps(raw_response or {}), answer_text, est_cost_usd),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    # ---- citations / mentions ----
    def add_citation(
        self, run_id: int, *, cited_url: str | None, domain: str | None,
        position: int | None = None, is_target_brand: bool = False,
        sentiment: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO citations(run_id,cited_url,domain,position,is_target_brand,sentiment)"
            " VALUES (?,?,?,?,?,?)",
            (run_id, cited_url, domain, position, int(is_target_brand), sentiment),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_mention(
        self, run_id: int, *, entity: str, is_target_brand: bool = False,
        sentiment: str | None = None, char_offset: int | None = None,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO mentions(run_id,entity,is_target_brand,sentiment,char_offset)"
            " VALUES (?,?,?,?,?)",
            (run_id, entity, int(is_target_brand), sentiment, char_offset),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def upsert_content_score(self, page_url: str, **fields) -> None:
        cols = ["page_url", "crawl_ts", "stat_density", "quote_count", "citation_count",
                "heading_structure_score", "readability", "has_schema"]
        row = {c: fields.get(c) for c in cols}
        row["page_url"] = page_url
        row["crawl_ts"] = fields.get("crawl_ts") or _utcnow()
        placeholders = ",".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO content_scores({','.join(cols)}) VALUES ({placeholders})",
            tuple(row[c] for c in cols),
        )
        self.conn.commit()

    # ---- queries ----
    def runs_for_prompt(self, prompt_id: int) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM runs WHERE prompt_id=?", (prompt_id,)))

    def citations_for_run(self, run_id: int) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM citations WHERE run_id=?", (run_id,)))

    def count(self, table: str) -> int:
        if table not in {"prompts", "runs", "citations", "mentions", "content_scores"}:
            raise ValueError(f"unknown table {table!r}")
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def total_est_cost(self) -> float:
        row = self.conn.execute("SELECT COALESCE(SUM(est_cost_usd),0) FROM runs").fetchone()
        return round(float(row[0]), 6)

    def brand_citation_rate(self, prompt_id: int, engine: str) -> tuple[int, int]:
        """(#runs where target brand was cited, total runs) for a prompt+engine.

        Feeds the rigor module's Wilson interval — a Bernoulli trial per run.
        """
        runs = list(self.conn.execute(
            "SELECT run_id FROM runs WHERE prompt_id=? AND engine=?", (prompt_id, engine)))
        total = len(runs)
        hits = 0
        for r in runs:
            n = self.conn.execute(
                "SELECT COUNT(*) FROM citations WHERE run_id=? AND is_target_brand=1",
                (r["run_id"],)).fetchone()[0]
            hits += 1 if n > 0 else 0
        return hits, total
