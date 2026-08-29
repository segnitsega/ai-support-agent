"""MCP server: look up Segni Electronics orders from local SQLite."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.mcp.orders_db import get_order, seed_orders

mcp = MCPServer("order-lookup")

# Ensure demo data exists whenever the server process starts.
seed_orders(reset=False)


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Look up a Segni Electronics order by ID (e.g. 1234 or #1234)."""
    order = get_order(order_id)
    if order is None:
        return (
            f"No order found for ID '{order_id}'. "
            "Valid demo IDs: 1234, 5678, 9012, 3456, 7890."
        )

    eta = order["eta"] or "n/a"
    return (
        f"Order #{order['order_id']}\n"
        f"Status: {order['status']}\n"
        f"Item: {order['item']}\n"
        f"Shipping to: {order['shipping_address']}\n"
        f"ETA: {eta}"
    )


if __name__ == "__main__":
    mcp.run()
