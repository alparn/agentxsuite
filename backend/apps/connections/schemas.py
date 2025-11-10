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
    tools_updated: int
    tool_ids: list[str]  # Changed to list[str] for UUIDs
    message: str | None = None

