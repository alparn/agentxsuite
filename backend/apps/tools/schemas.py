"""
Pydantic schemas for tools app.
"""
from __future__ import annotations

from pydantic import BaseModel


class ToolRunInputSchema(BaseModel):
    """Input schema for tool run."""

    input_json: dict | None = None
    agent_id: str | None = None

