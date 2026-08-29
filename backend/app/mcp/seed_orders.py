"""Seed the local SQLite orders database used by the order-lookup MCP server.

Usage (from backend/):
    PYTHONPATH=. python -m app.mcp.seed_orders
    PYTHONPATH=. python -m app.mcp.seed_orders --reset
"""

from __future__ import annotations

import argparse

from app.mcp.orders_db import get_db_path, seed_orders


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Segni Electronics demo orders")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows before seeding",
    )
    args = parser.parse_args()

    count = seed_orders(reset=args.reset)
    print(f"Seeded {count} orders into {get_db_path()}")


if __name__ == "__main__":
    main()
