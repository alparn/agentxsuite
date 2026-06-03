"""
Unit tests for outbound MCP client wrapper.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from apps.connections import mcp_client
from apps.connections.models import Connection


class FakeSecretStore:
    """In-memory SecretStore test double."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self.secrets = secrets

    def get_secret(self, ref: str, check_permissions: bool = True) -> str:
        return self.secrets[ref]


class FakeStreamableHttpTransport:
    """Capture Streamable HTTP transport configuration."""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = headers


class FakeStdioTransport:
    """Capture stdio transport configuration."""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args
        self.env = env


class FakeClient:
    """Async FastMCP client test double."""

    created_transports: list[Any] = []
    tools_response: list[Any] = []
    call_response: Any = None
    call_args: tuple[str, dict[str, Any]] | None = None

    def __init__(self, transport: Any) -> None:
        self.transport = transport
        self.created_transports.append(transport)

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def list_tools(self) -> list[Any]:
        return self.tools_response

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        type(self).call_args = (name, arguments)
        return self.call_response


@pytest.fixture(autouse=True)
def fake_fastmcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use fake FastMCP classes for all tests in this module."""
    FakeClient.created_transports = []
    FakeClient.tools_response = []
    FakeClient.call_response = None
    FakeClient.call_args = None

    monkeypatch.setattr(
        mcp_client,
        "_load_fastmcp_client",
        lambda: (FakeClient, FakeStdioTransport, FakeStreamableHttpTransport),
    )


@pytest.mark.django_db
def test_list_tools_uses_streamable_http_with_bearer_auth(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streamable HTTP connections pass SecretStore bearer auth to FastMCP."""
    org, env = org_env
    monkeypatch.setattr(
        mcp_client,
        "get_secretstore",
        lambda: FakeSecretStore({"auth-ref": "token-value"}),
    )
    FakeClient.tools_response = [
        SimpleNamespace(
            name="search",
            description="Search things",
            inputSchema={"type": "object", "properties": {"q": {"type": "string"}}},
        ),
    ]
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
        auth_method="bearer",
        secret_ref="auth-ref",
    )

    tools = mcp_client.list_tools(conn)

    transport = FakeClient.created_transports[0]
    assert isinstance(transport, FakeStreamableHttpTransport)
    assert transport.url == "https://example.com/mcp"
    assert transport.headers == {"Authorization": "Bearer token-value"}
    assert tools == [
        {
            "name": "search",
            "description": "Search things",
            "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    ]


@pytest.mark.django_db
def test_list_tools_uses_stdio_with_secretstore_env(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stdio connections pass env_ref JSON as process environment."""
    org, env = org_env
    monkeypatch.setattr(
        mcp_client,
        "get_secretstore",
        lambda: FakeSecretStore({"env-ref": json.dumps({"DATABASE_URL": "postgres://db"})}),
    )
    FakeClient.tools_response = [{"name": "query", "inputSchema": {"type": "object"}}]
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="postgres",
        transport=Connection.Transport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        env_ref="env-ref",
    )

    tools = mcp_client.list_tools(conn)

    transport = FakeClient.created_transports[0]
    assert isinstance(transport, FakeStdioTransport)
    assert transport.command == "npx"
    assert transport.args == ["-y", "@modelcontextprotocol/server-postgres"]
    assert transport.env == {"DATABASE_URL": "postgres://db"}
    assert tools == [{"name": "query", "description": "", "inputSchema": {"type": "object"}}]


@pytest.mark.django_db
def test_call_tool_returns_result_data(org_env: tuple) -> None:
    """Tool call results expose FastMCP structured data as plain dictionaries."""
    org, env = org_env
    FakeClient.call_response = SimpleNamespace(data={"rows": [{"id": 1}]})
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
    )

    result = mcp_client.call_tool(conn, "query", {"sql": "select 1"})

    assert FakeClient.call_args == ("query", {"sql": "select 1"})
    assert result == {"rows": [{"id": 1}]}


@pytest.mark.django_db
def test_call_tool_requires_name(org_env: tuple) -> None:
    """Outbound calls fail before opening a transport when the tool name is empty."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="Tool name is required"):
        mcp_client.call_tool(conn, "", {})


@pytest.mark.django_db
def test_call_tool_raises_on_mcp_error_result(org_env: tuple) -> None:
    """FastMCP error results are converted to MCPToolError."""
    org, env = org_env
    FakeClient.call_response = SimpleNamespace(isError=True, data={"message": "boom"})
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
    )

    with pytest.raises(mcp_client.MCPToolError, match="returned an error"):
        mcp_client.call_tool(conn, "query", {})


@pytest.mark.django_db
def test_call_tool_wraps_non_dict_data(org_env: tuple) -> None:
    """Scalar structured data is preserved under a data key."""
    org, env = org_env
    FakeClient.call_response = SimpleNamespace(data=["row-1"])
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
    )

    assert mcp_client.call_tool(conn, "query", {}) == {"data": ["row-1"]}


@pytest.mark.django_db
def test_streamable_http_requires_egress_allowlist(org_env: tuple) -> None:
    """HTTP MCP clients fail closed when no egress allowlist is configured."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="No egress allowlist"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_streamable_http_requires_endpoint(org_env: tuple) -> None:
    """Streamable HTTP transports must include a URL endpoint."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="endpoint is required"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_streamable_http_blocks_unlisted_host(org_env: tuple) -> None:
    """HTTP MCP clients only connect to explicitly allowed hosts."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://blocked.example/mcp",
        egress_allowlist=["allowed.example"],
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="not allowed"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_streamable_http_allows_cidr_entries(org_env: tuple) -> None:
    """Egress allowlists support IP/CIDR entries for private MCP gateways."""
    org, env = org_env
    FakeClient.tools_response = [{"name": "query", "inputSchema": {"type": "object"}}]
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="http://10.1.2.3/mcp",
        egress_allowlist=["10.0.0.0/8"],
    )

    assert mcp_client.list_tools(conn)[0]["name"] == "query"


@pytest.mark.django_db
def test_stdio_requires_command(org_env: tuple) -> None:
    """Stdio transports fail closed without an executable command."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="stdio",
        transport=Connection.Transport.STDIO,
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="command is required"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_unsupported_transport_raises_configuration_error(org_env: tuple) -> None:
    """Legacy REST-style connections are not treated as real outbound MCP clients."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="legacy",
        transport=Connection.Transport.LEGACY_HTTP,
        endpoint="https://example.com",
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_basic_auth_encodes_secretstore_value(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic auth secrets are base64 encoded into Authorization headers."""
    org, env = org_env
    monkeypatch.setattr(
        mcp_client,
        "get_secretstore",
        lambda: FakeSecretStore({"auth-ref": "user:pass"}),
    )
    FakeClient.tools_response = [{"name": "query", "inputSchema": {"type": "object"}}]
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
        auth_method="basic",
        secret_ref="auth-ref",
    )

    mcp_client.list_tools(conn)

    transport = FakeClient.created_transports[0]
    assert transport.headers == {"Authorization": "Basic dXNlcjpwYXNz"}


@pytest.mark.django_db
def test_auth_secret_ref_must_be_retrievable(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SecretStore failures are mapped to configuration errors without leaking details."""
    org, env = org_env
    secretstore = Mock()
    secretstore.get_secret.side_effect = KeyError("missing")
    monkeypatch.setattr(mcp_client, "get_secretstore", lambda: secretstore)
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
        auth_method="bearer",
        secret_ref="missing-ref",
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="Could not retrieve"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_unsupported_auth_method_raises_configuration_error(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only none, bearer, and basic auth are supported by the MCP client wrapper."""
    org, env = org_env
    monkeypatch.setattr(
        mcp_client,
        "get_secretstore",
        lambda: FakeSecretStore({"auth-ref": "token"}),
    )
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
        egress_allowlist=["example.com"],
        auth_method="oauth",
        secret_ref="auth-ref",
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError, match="Unsupported auth_method"):
        mcp_client.list_tools(conn)


@pytest.mark.django_db
def test_invalid_env_secret_raises_configuration_error(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env_ref must contain JSON object material, not arbitrary plaintext."""
    org, env = org_env
    monkeypatch.setattr(
        mcp_client,
        "get_secretstore",
        lambda: FakeSecretStore({"env-ref": "not-json"}),
    )
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="stdio",
        transport=Connection.Transport.STDIO,
        command="python",
        env_ref="env-ref",
    )

    with pytest.raises(mcp_client.MCPClientConfigurationError):
        mcp_client.list_tools(conn)
