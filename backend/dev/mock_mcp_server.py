"""
Mock MCP Server for local testing.

Provides a minimal MCP-compatible server for testing runner agents.
Runs on port 8091 by default.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List

app = FastAPI(title="Mock MCP Server", version="0.1.0")

TOOLS = [
    {
        "name": "create_customer_note",
        "description": "Creates a note for a given customer.",
        "version": "1.0.0",
        "inputSchema": {  # MCP protocol standard uses CamelCase (inputSchema)
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["customer_id", "note"],
        },
    }
]


@app.get("/.well-known/mcp/manifest.json")
def manifest():
    """Get MCP manifest."""
    return {
        "mcp_version": "1.0.0",
        "name": "mock-mcp",
        "endpoints": {
            "tools": "/.well-known/mcp/tools",
            "run": "/.well-known/mcp/run",
        },
        "auth": {"type": "bearer"},
    }


@app.get("/.well-known/mcp/tools")
def list_tools():
    """List available tools."""
    return {"tools": TOOLS}


class RunBody(BaseModel):
    """Request body for tool execution."""

    tool: str
    input: Dict[str, Any] = {}


@app.post("/.well-known/mcp/run")
def run_tool(body: RunBody, request: Request):
    """
    Execute a tool.

    Minimal auth: only checks for Bearer header presence.
    """
    # Minimal-Auth: nur Header-Präsenz prüfen
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer")

    if body.tool != "create_customer_note":
        raise HTTPException(status_code=404, detail="tool_not_found")

    inp = body.input or {}
    if not inp.get("customer_id") or not inp.get("note"):
        raise HTTPException(status_code=400, detail="invalid_input")

    return {
        "status": "success",
        "output": {
            "note_id": "note_local_1",
            "created_at": "2025-01-01T00:00:00Z",
        },
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}

