"""
Pydantic schemas for MCP Fabric.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MCPManifest(BaseModel):
    """MCP manifest schema."""

    protocol_version: str = Field(default="2024-11-05", description="MCP protocol version")
    name: str = Field(description="Server name")
    version: str = Field(default="1.0.0", description="Server version")
    capabilities: dict[str, Any] = Field(default_factory=dict, description="Server capabilities")


class MCPTool(BaseModel):
    """MCP tool schema."""

    name: str = Field(description="Tool name")
    description: str | None = Field(default=None, description="Tool description")
    inputSchema: dict[str, Any] = Field(description="JSON Schema for tool inputs")


class MCPToolsResponse(BaseModel):
    """MCP tools list response."""

    tools: list[MCPTool] = Field(description="List of available tools")


class MCPRunRequest(BaseModel):
    """MCP run request schema."""

    name: str = Field(description="Tool name to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")


class MCPRunResponse(BaseModel):
    """MCP run response schema."""

    content: list[dict[str, Any]] = Field(description="Run output content")
    isError: bool = Field(default=False, description="Whether the run resulted in an error")

