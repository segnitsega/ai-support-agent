"""SQLite helpers for Segni Electronics fake orders."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "orders.db"

SEED_ORDERS = [
    ("1234", "out_for_delivery", "Samsung Galaxy Buds 3", "Addis Ababa — Bole", "2026-08-29"),
    ("5678", "processing", "Lenovo IdeaPad Slim 5", "Addis Ababa — Kazanchis", "2026-08-30"),
    ("9012", "shipped", "Anker PowerBank 20000mAh", "Bahir Dar", "2026-08-31"),
    ("3456", "delivered", "Sony WH-1000XM5", "Addis Ababa — CMC", "2026-08-25"),
    ("7890", "cancelled", "Logitech MX Master 3S", "Hawassa", None),
]


def get_db_path() -> Path:
    configured = os.getenv("ORDERS_DB_PATH")
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
    """Create the orders table if it does not exist."""
    path = db_path or get_db_path()
    with connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                item TEXT NOT NULL,
                shipping_address TEXT NOT NULL,
                eta TEXT
            )
            """
        )
        conn.commit()
    return path


def seed_orders(*, reset: bool = False, db_path: Path | None = None) -> int:
    """Insert the demo orders. If reset=True, wipe existing rows first."""
    path = init_db(db_path)
    with connect(path) as conn:
        if reset:
            conn.execute("DELETE FROM orders")
        conn.executemany(
            """
            INSERT OR REPLACE INTO orders
                (order_id, status, item, shipping_address, eta)
            VALUES (?, ?, ?, ?, ?)
            """,
            SEED_ORDERS,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return int(count)


def get_order(order_id: str, db_path: Path | None = None) -> dict | None:
    """Fetch one order by ID. Accepts '1234' or '#1234'."""
    normalized = order_id.strip().lstrip("#")
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT order_id, status, item, shipping_address, eta FROM orders WHERE order_id = ?",
            (normalized,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)
