"""
MCP Gateway - SSE/WebSocket to HTTP bridge for Claude Desktop.

This module provides a gateway that accepts SSE/WebSocket connections
from MCP clients (like Claude Desktop) and proxies them to the internal
HTTP-based FastMCP server.

This eliminates the need for users to run a local bridge.
"""

