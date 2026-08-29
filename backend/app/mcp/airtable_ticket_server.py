"""MCP server: create support tickets in Airtable."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

mcp = MCPServer("airtable-ticket")


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is not set in the environment")
    return value


@mcp.tool()
def create_ticket(
    subject: str,
    description: str,
    priority: str,
    customer_email: str,
) -> str:
    """Create a support ticket row in Airtable.

    Args:
        subject: Short ticket title.
        description: Detailed description of the customer issue.
        priority: One of low, normal, high.
        customer_email: Customer contact email.
    """
    token = _require_env("AIRTABLE_TOKEN")
    base_id = _require_env("AIRTABLE_BASE_ID")
    table_name = os.getenv("AIRTABLE_TABLE_NAME", "Tickets")

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    payload = {
        "fields": {
            "Subject": subject,
            "Description": description,
            "Priority": priority,
            "Customer Email": customer_email,
            "Status": "Open",
            "Created At": datetime.now(UTC).isoformat(),
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        return (
            f"Failed to create Airtable ticket (HTTP {exc.response.status_code}): {detail}"
        )
    except Exception as exc:
        return f"Failed to create Airtable ticket: {exc}"

    record = response.json()
    record_id = record.get("id", "unknown")
    return (
        f"Ticket created successfully.\n"
        f"Airtable record ID: {record_id}\n"
        f"Subject: {subject}\n"
        f"Priority: {priority}\n"
        f"Customer: {customer_email}"
    )


if __name__ == "__main__":
    mcp.run()
