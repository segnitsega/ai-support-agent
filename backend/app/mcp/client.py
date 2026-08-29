"""MCP stdio client helpers for LangGraph tool nodes."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

MCP_DIR = Path(__file__).resolve().parent


def _server_env() -> dict[str, str]:
    """Pass through env so child MCP servers can read secrets / DB path."""
    env = os.environ.copy()
    # Ensure the child can import `app.*` the same way the parent does.
    backend_root = str(MCP_DIR.parents[1])
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        backend_root if not existing else f"{backend_root}{os.pathsep}{existing}"
    )
    return env


def _server_params(script_name: str) -> StdioServerParameters:
    script = MCP_DIR / script_name
    return StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        env=_server_env(),
        cwd=str(MCP_DIR.parents[1]),
    )


def _result_to_text(result) -> str:
    parts: list[str] = []
    for block in result.content or []:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif hasattr(block, "text"):
            parts.append(str(block.text))
        else:
            parts.append(str(block))
    text = "\n".join(part for part in parts if part).strip()
    if getattr(result, "is_error", False):
        return f"Tool error: {text or 'unknown error'}"
    return text or "No response from tool."


async def _call_tool(script_name: str, tool_name: str, arguments: dict) -> str:
    params = _server_params(script_name)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return _result_to_text(result)


def call_get_order_status(order_id: str) -> str:
    """Sync wrapper used by the LangGraph order_lookup node."""
    return asyncio.run(
        _call_tool(
            "order_lookup_server.py",
            "get_order_status",
            {"order_id": order_id},
        )
    )


def call_create_ticket(
    *,
    subject: str,
    description: str,
    priority: str,
    customer_email: str,
) -> str:
    """Sync wrapper used by the LangGraph book_ticket node."""
    return asyncio.run(
        _call_tool(
            "airtable_ticket_server.py",
            "create_ticket",
            {
                "subject": subject,
                "description": description,
                "priority": priority,
                "customer_email": customer_email,
            },
        )
    )
