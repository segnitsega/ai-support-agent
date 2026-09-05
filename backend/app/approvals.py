"""SQLite queue of ticket approvals for the admin panel."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "approvals.db"

ApprovalStatus = Literal["pending", "approved", "rejected"]


def get_db_path() -> Path:
    configured = os.getenv("APPROVALS_DB_PATH")
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
            CREATE TABLE IF NOT EXISTS approvals (
                thread_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                user_question TEXT NOT NULL DEFAULT '',
                route TEXT NOT NULL DEFAULT '',
                ticket_json TEXT NOT NULL,
                bot_answer TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_approvals_status_created
            ON approvals (status, created_at DESC)
            """
        )
        conn.commit()
    return path


def upsert_pending(
    *,
    thread_id: str,
    ticket: dict[str, Any],
    user_question: str = "",
    route: str = "",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Create or refresh a pending approval for a paused ticket thread."""
    init_db(db_path)
    now = datetime.now(UTC).isoformat()
    ticket_json = json.dumps(ticket, ensure_ascii=False)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM approvals WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now

        conn.execute(
            """
            INSERT INTO approvals (
                thread_id, status, user_question, route, ticket_json,
                bot_answer, created_at, updated_at, resolved_at
            )
            VALUES (?, 'pending', ?, ?, ?, '', ?, ?, NULL)
            ON CONFLICT(thread_id) DO UPDATE SET
                status = 'pending',
                user_question = excluded.user_question,
                route = excluded.route,
                ticket_json = excluded.ticket_json,
                bot_answer = '',
                updated_at = excluded.updated_at,
                resolved_at = NULL
            """,
            (thread_id, user_question, route, ticket_json, created_at, now),
        )
        conn.commit()

    row = get_approval(thread_id, db_path=db_path)
    assert row is not None
    return row


def resolve_approval(
    *,
    thread_id: str,
    status: Literal["approved", "rejected"],
    bot_answer: str = "",
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    init_db(db_path)
    now = datetime.now(UTC).isoformat()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE approvals
            SET status = ?,
                bot_answer = ?,
                updated_at = ?,
                resolved_at = ?
            WHERE thread_id = ?
            """,
            (status, bot_answer, now, now, thread_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_approval(thread_id, db_path=db_path)


def get_approval(
    thread_id: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM approvals WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_approvals(
    *,
    status: ApprovalStatus | Literal["all"] = "pending",
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    init_db(db_path)
    limit = max(1, min(limit, 200))
    with connect(db_path) as conn:
        if status == "all":
            rows = conn.execute(
                """
                SELECT * FROM approvals
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM approvals
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    ticket: dict[str, Any]
    try:
        parsed = json.loads(row["ticket_json"])
        ticket = parsed if isinstance(parsed, dict) else {"raw": parsed}
    except (TypeError, json.JSONDecodeError):
        ticket = {"raw": row["ticket_json"]}

    return {
        "thread_id": row["thread_id"],
        "status": row["status"],
        "user_question": row["user_question"] or "",
        "route": row["route"] or "",
        "ticket": ticket,
        "bot_answer": row["bot_answer"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "resolved_at": row["resolved_at"],
    }
