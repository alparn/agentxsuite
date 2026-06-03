"""
MCP client wrapper for outbound connections.
"""
from __future__ import annotations

import base64
import fnmatch
import ipaddress
import json
import logging
from typing import Any
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.conf import settings

from apps.connections.models import Connection
from libs.secretstore import get_secretstore

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    """Base exception for outbound MCP client failures."""


class MCPClientConfigurationError(MCPClientError):
    """Raised when a connection is missing required client configuration."""


class MCPClientTransportError(MCPClientError):
    """Raised when the MCP transport cannot complete a request."""


class MCPToolError(MCPClientError):
    """Raised when an MCP tool call fails."""


def list_tools(conn: Connection) -> list[dict[str, Any]]:
    """
    List tools from an external MCP server.

    Raises MCPClientError subclasses when configuration, transport, or protocol calls fail.
    """
    return async_to_sync(alist_tools)(conn)


def call_tool(conn: Connection, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Call a tool on an external MCP server.

    Raises MCPClientError subclasses when configuration, transport, or tool execution fails.
    """
    return async_to_sync(acall_tool)(conn, name, arguments or {})


async def alist_tools(conn: Connection) -> list[dict[str, Any]]:
    """
    Async implementation of list_tools for callers already inside an event loop.

    Raises MCPClientError subclasses when configuration, transport, or protocol calls fail.
    """
    client_cls, _stdio_transport, _streamable_http_transport = _load_fastmcp_client()
    transport = _build_transport(conn)
    client = client_cls(transport)

    try:
        async with client:
            tools = await client.list_tools()
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPClientTransportError(
            f"Could not list tools for connection '{conn.name}' via {conn.transport}."
        ) from exc

    return [_normalize_tool(tool) for tool in tools]


async def acall_tool(
    conn: Connection,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Async implementation of call_tool for callers already inside an event loop.

    Raises MCPClientError subclasses when configuration, transport, or tool execution fails.
    """
    if not name:
        raise MCPClientConfigurationError("Tool name is required.")

    client_cls, _stdio_transport, _streamable_http_transport = _load_fastmcp_client()
    transport = _build_transport(conn)
    client = client_cls(transport)

    try:
        async with client:
            result = await client.call_tool(name, arguments or {})
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPToolError(
            f"Could not call tool '{name}' for connection '{conn.name}' via {conn.transport}."
        ) from exc

    return _normalize_call_result(result)


def _load_fastmcp_client() -> tuple[type, type, type]:
    """Load fastmcp lazily so Django can start even when optional deps are absent in dev."""
    try:
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
    except ImportError as exc:
        raise MCPClientConfigurationError(
            "fastmcp client dependency is not installed. Install backend requirements first."
        ) from exc

    return Client, StdioTransport, StreamableHttpTransport


def _build_transport(conn: Connection) -> Any:
    """Build the FastMCP transport for a configured connection."""
    _client_cls, stdio_transport, streamable_http_transport = _load_fastmcp_client()

    if conn.transport == Connection.Transport.STDIO:
        if not conn.command:
            raise MCPClientConfigurationError("command is required for stdio connections.")
        return stdio_transport(
            command=conn.command,
            args=[str(arg) for arg in (conn.args or [])],
            env=_load_stdio_env(conn),
        )

    if conn.transport == Connection.Transport.STREAMABLE_HTTP:
        if not conn.endpoint:
            raise MCPClientConfigurationError("endpoint is required for streamable_http connections.")
        _enforce_egress_allowlist(conn)
        return streamable_http_transport(
            url=conn.endpoint,
            headers=_build_auth_headers(conn) or None,
        )

    raise MCPClientConfigurationError(
        f"Unsupported MCP transport '{conn.transport}'. "
        "Use 'stdio' or 'streamable_http' for outbound MCP clients."
    )


def _enforce_egress_allowlist(conn: Connection) -> None:
    """Deny HTTP MCP egress unless the endpoint host matches an explicit allowlist."""
    endpoint = conn.endpoint or ""
    parsed = urlparse(endpoint)
    host = parsed.hostname
    if not host:
        raise MCPClientConfigurationError("endpoint must include a hostname for HTTP MCP connections.")

    allowlist = [
        str(entry).strip().lower()
        for entry in (
            conn.egress_allowlist
            or getattr(settings, "MCP_CLIENT_EGRESS_ALLOWLIST", [])
            or []
        )
        if str(entry).strip()
    ]
    if not allowlist:
        raise MCPClientConfigurationError(
            f"No egress allowlist configured for connection '{conn.name}'."
        )

    normalized_host = host.lower().rstrip(".")
    if any(_host_matches_allowlist_entry(normalized_host, entry) for entry in allowlist):
        return

    raise MCPClientConfigurationError(
        f"Endpoint host '{host}' is not allowed for connection '{conn.name}'."
    )


def _host_matches_allowlist_entry(host: str, entry: str) -> bool:
    """Match hostnames exactly, by wildcard pattern, or by IP/CIDR range."""
    if entry == "*":
        return True

    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        host_ip = None

    if host_ip is not None:
        try:
            return host_ip in ipaddress.ip_network(entry, strict=False)
        except ValueError:
            return host == entry

    return host == entry.rstrip(".") or fnmatch.fnmatch(host, entry.rstrip("."))


def _build_auth_headers(conn: Connection) -> dict[str, str]:
    """Build HTTP auth headers from SecretStore-backed connection credentials."""
    if conn.auth_method == "none":
        return {}

    if not conn.secret_ref:
        raise MCPClientConfigurationError(
            f"secret_ref is required for {conn.auth_method} authentication."
        )

    secret = _get_secret(conn.secret_ref, conn=conn, purpose="authentication")
    if conn.auth_method == "bearer":
        return {"Authorization": f"Bearer {secret}"}

    if conn.auth_method == "basic":
        encoded = base64.b64encode(secret.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    raise MCPClientConfigurationError(f"Unsupported auth_method '{conn.auth_method}'.")


def _load_stdio_env(conn: Connection) -> dict[str, str] | None:
    """Load stdio process environment variables from a SecretStore JSON object."""
    if not conn.env_ref:
        return None

    raw_env = _get_secret(conn.env_ref, conn=conn, purpose="stdio environment")
    try:
        parsed_env = json.loads(raw_env)
    except json.JSONDecodeError as exc:
        raise MCPClientConfigurationError(
            "env_ref must point to a JSON object containing stdio environment variables."
        ) from exc

    if not isinstance(parsed_env, dict):
        raise MCPClientConfigurationError(
            "env_ref must point to a JSON object containing stdio environment variables."
        )

    return {str(key): str(value) for key, value in parsed_env.items()}


def _get_secret(ref: str, *, conn: Connection, purpose: str) -> str:
    """Retrieve a SecretStore value for internal MCP service use."""
    try:
        return get_secretstore().get_secret(ref, check_permissions=False)
    except Exception as exc:
        raise MCPClientConfigurationError(
            f"Could not retrieve {purpose} secret for connection '{conn.name}'."
        ) from exc


def _normalize_tool(tool: Any) -> dict[str, Any]:
    """Normalize fastmcp/mcp Tool objects to the registry format used by AgentxSuite."""
    dumped = _dump_object(tool)
    if isinstance(dumped, dict):
        name = dumped.get("name")
        if not name:
            raise MCPClientTransportError("MCP tool response is missing a tool name.")

        schema = (
            dumped.get("inputSchema")
            or dumped.get("input_schema")
            or dumped.get("parameters")
            or {}
        )
        return {
            "name": name,
            "description": dumped.get("description", ""),
            "inputSchema": schema if isinstance(schema, dict) else {},
        }

    name = getattr(tool, "name", None)
    if not name:
        raise MCPClientTransportError("MCP tool response is missing a tool name.")

    schema = (
        getattr(tool, "inputSchema", None)
        or getattr(tool, "input_schema", None)
        or getattr(tool, "parameters", None)
        or {}
    )
    return {
        "name": name,
        "description": getattr(tool, "description", ""),
        "inputSchema": schema if isinstance(schema, dict) else {},
    }


def _normalize_call_result(result: Any) -> dict[str, Any]:
    """Normalize a FastMCP call result into a plain dictionary."""
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        dumped = _dump_object(result)
        raise MCPToolError(f"MCP tool returned an error: {dumped}")

    data = getattr(result, "data", None)
    if data is not None:
        if isinstance(data, dict):
            return data
        return {"data": data}

    dumped = _dump_object(result)
    if isinstance(dumped, dict):
        return dumped

    return {"data": dumped}


def _dump_object(value: Any) -> Any:
    """Dump pydantic/dataclass-like MCP objects without depending on their concrete classes."""
    if isinstance(value, dict):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump(by_alias=True, exclude_none=True)
        except TypeError:
            return model_dump()

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            return dict_method(by_alias=True, exclude_none=True)
        except TypeError:
            return dict_method()

    return value
