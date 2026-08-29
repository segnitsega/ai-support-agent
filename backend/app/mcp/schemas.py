"""Pydantic schemas for MCP tool arguments."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class OrderLookupArgs(BaseModel):
    order_id: str = Field(min_length=1, description="Order number, e.g. 1234 or #1234")

    @field_validator("order_id")
    @classmethod
    def normalize_order_id(cls, value: str) -> str:
        cleaned = value.strip().lstrip("#")
        if not cleaned.isdigit():
            raise ValueError("order_id must be a numeric order number like 1234 or #1234")
        return cleaned


class CreateTicketArgs(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=4000)
    priority: Literal["low", "normal", "high"] = "normal"
    customer_email: EmailStr
