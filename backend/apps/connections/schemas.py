"""
Pydantic schemas for connections app.
"""
from __future__ import annotations

from pydantic import BaseModel


class ConnectionTestResponse(BaseModel):
    """Response schema for connection test."""

    status: str
    last_seen_at: str | None


class ConnectionSyncResponse(BaseModel):
    """Response schema for connection sync."""

    tools_created: int
    tool_ids: list[int]

