"""SQLite log of support-agent run outcomes for GET /stats."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "stats.db"

Outcome = str


def get_db_path() -> Path:
    configured = os.getenv("STATS_DB_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or get_db_path()
    with connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                route TEXT NOT NULL,
                outcome TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    return path


def record_run(
    *,
    thread_id: str,
    route: str,
    outcome: str,
    db_path: Path | None = None,
) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (thread_id, route, outcome, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, route, outcome, datetime.now(UTC).isoformat()),
        )
        conn.commit()


def get_stats(db_path: Path | None = None) -> dict[str, int]:
    init_db(db_path)
    with connect(db_path) as conn:
        resolved = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE outcome = 'resolved_without_human'"
        ).fetchone()[0]
        escalations = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE outcome = 'escalated'"
        ).fetchone()[0]
        tickets = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE outcome = 'ticket_created'"
        ).fetchone()[0]
    return {
        "resolved_without_human": int(resolved),
        "escalations": int(escalations),
        "tickets_created": int(tickets),
    }
