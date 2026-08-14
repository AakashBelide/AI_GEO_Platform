"""Reconstruct the raw evidence for a report from the append-only fact store (Task A3).

The fact store (`pocs/factstore`) already holds every prompt, every engine answer, and
every citation from a real run. A JSON `GeoReport` written before the evidence layer
existed carries only the aggregate metrics — the underlying prompts / answers / citations
live in the store. `read_evidence` re-reads them so a saved report can be re-rendered with
its evidence and interpretation **without re-calling any engine** (zero spend).

Pure stdlib `sqlite3`, read-only. Returns plain dicts/lists so the result drops straight
into a report dict and JSON-serializes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

# One representative sample = the FIRST run (lowest run_id) per (engine, prompt).
_ANSWER_TRUNCATE = 700
_MAX_CITATIONS_PER_SAMPLE = 12


def _connect(store_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    return conn


def _prompts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT prompt_id, text, intent, category FROM prompts ORDER BY prompt_id"
    ).fetchall()
    return [
        {"text": r["text"], "intent": r["intent"], "category": r["category"]} for r in rows
    ]


def _engines(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT engine FROM runs ORDER BY engine")]


def _citations_for_run(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT cited_url, domain, position FROM citations WHERE run_id=? "
        "ORDER BY (position IS NULL), position, citation_id",
        (run_id,),
    ).fetchall()
    out: list[dict] = []
    for r in rows[:_MAX_CITATIONS_PER_SAMPLE]:
        out.append({"url": r["cited_url"], "domain": r["domain"], "position": r["position"]})
    return out


def _transcript(conn: sqlite3.Connection, engines: Iterable[str]) -> dict[str, list[dict]]:
    """One representative sample per prompt per engine (first run), ordered by prompt."""
    transcript: dict[str, list[dict]] = {}
    for engine in engines:
        rows = conn.execute(
            "SELECT r.prompt_id AS prompt_id, MIN(r.run_id) AS run_id, p.text AS text "
            "FROM runs r JOIN prompts p ON p.prompt_id = r.prompt_id "
            "WHERE r.engine=? GROUP BY r.prompt_id ORDER BY r.prompt_id",
            (engine,),
        ).fetchall()
        samples: list[dict] = []
        for row in rows:
            answer = conn.execute(
                "SELECT answer_text FROM runs WHERE run_id=?", (row["run_id"],)
            ).fetchone()["answer_text"] or ""
            samples.append(
                {
                    "prompt_text": row["text"],
                    "answer": answer[:_ANSWER_TRUNCATE],
                    "citations": _citations_for_run(conn, row["run_id"]),
                }
            )
        transcript[engine] = samples
    return transcript


def _citations_by_engine(conn: sqlite3.Connection, engines: Iterable[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for engine in engines:
        rows = conn.execute(
            "SELECT ci.domain AS domain FROM citations ci "
            "JOIN runs r ON r.run_id = ci.run_id WHERE r.engine=? AND ci.domain IS NOT NULL",
            (engine,),
        ).fetchall()
        out[engine] = [r["domain"] for r in rows]
    return out


def _target_domain(conn: sqlite3.Connection) -> str | None:
    """Recover the brand's registrable domain from citations flagged is_target_brand."""
    rows = conn.execute(
        "SELECT domain FROM citations WHERE is_target_brand=1 AND domain IS NOT NULL"
    ).fetchall()
    domains = {r["domain"].lower().lstrip(".") for r in rows if r["domain"]}
    if not domains:
        return None
    # Prefer the shortest registrable host (fewest labels, then fewest chars),
    # e.g. 'asana.com' over 'help.asana.com'.
    return min(domains, key=lambda d: (d.count("."), len(d)))


def read_evidence(store_path: str) -> dict:
    """Reconstruct prompts, transcript and per-engine cited domains from the fact store.

    Returns::

        {
          "prompts": [{"text", "intent", "category"}, ...],           # ordered
          "transcript": {engine: [{"prompt_text", "answer", "citations":[...]}, ...]},
          "citations_by_engine": {engine: [domain, ...]},             # every citation
          "target_domain": "asana.com" | None,
        }
    """
    conn = _connect(store_path)
    try:
        engines = _engines(conn)
        return {
            "prompts": _prompts(conn),
            "transcript": _transcript(conn, engines),
            "citations_by_engine": _citations_by_engine(conn, engines),
            "target_domain": _target_domain(conn),
        }
    finally:
        conn.close()
