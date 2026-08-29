"""MCP tooling package for Segni Electronics support agent."""

from app.mcp.client import call_create_ticket, call_get_order_status
from app.mcp.schemas import CreateTicketArgs, OrderLookupArgs

__all__ = [
    "CreateTicketArgs",
    "OrderLookupArgs",
    "call_create_ticket",
    "call_get_order_status",
]
