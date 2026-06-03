"""
Unit tests for connection service MCP sync behavior.
"""
from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from apps.connections import mcp_client, services
from apps.connections.models import Connection
from apps.tools.models import CuratedTool, CurationMapping, Tool


@pytest.mark.django_db
def test_verify_mcp_server_uses_mcp_client_for_streamable_http(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External MCP verification delegates to the outbound MCP client."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    calls = []

    def fake_list_tools(received_conn: Connection) -> list[dict]:
        calls.append(received_conn)
        return [{"name": "search", "inputSchema": {"type": "object"}}]

    monkeypatch.setattr(services.mcp_client, "list_tools", fake_list_tools)

    assert services.verify_mcp_server(conn) is True
    assert calls == [conn]


@pytest.mark.django_db
def test_verify_mcp_server_returns_false_on_mcp_client_error(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth or transport failures are not treated as a successful verification."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )

    def fake_list_tools(_conn: Connection) -> list[dict]:
        raise mcp_client.MCPClientTransportError("401 Unauthorized")

    monkeypatch.setattr(services.mcp_client, "list_tools", fake_list_tools)

    assert services.verify_mcp_server(conn) is False


@pytest.mark.django_db
def test_test_connection_marks_ok_when_verification_succeeds(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection testing persists ok status and heartbeat after MCP verification."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    monkeypatch.setattr(services, "verify_mcp_server", lambda _conn: True)

    updated = services.test_connection(conn)

    assert updated.status == "ok"
    assert updated.last_seen_at is not None
    conn.refresh_from_db()
    assert conn.status == "ok"


@pytest.mark.django_db
def test_test_connection_marks_fail_when_verification_fails(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection testing persists fail status for negative MCP verification."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    monkeypatch.setattr(services, "verify_mcp_server", lambda _conn: False)

    updated = services.test_connection(conn)

    assert updated.status == "fail"
    assert updated.last_seen_at is not None


@pytest.mark.django_db
def test_sync_connection_creates_tools_from_mcp_client(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync stores tools returned by MCP tools/list without probing guessed URLs."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )

    def fake_list_tools(received_conn: Connection) -> list[dict]:
        assert received_conn == conn
        return [
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
            },
        ]

    monkeypatch.setattr(services.mcp_client, "list_tools", fake_list_tools)

    created_tools, updated_tools = services.sync_connection(conn)
    conn.refresh_from_db()

    assert len(created_tools) == 1
    assert updated_tools == []
    assert created_tools[0].name == "search"
    assert created_tools[0].schema_json == {
        "type": "object",
        "properties": {"q": {"type": "string"}},
    }
    assert Tool.objects.filter(connection=conn, name="search").exists()
    assert conn.status == "ok"
    assert conn.last_seen_at is not None


@pytest.mark.django_db
def test_sync_connection_updates_existing_tool_from_mcp_client(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync updates existing tool schemas instead of creating duplicates."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    existing = Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="search",
        version="1.0.0",
        schema_json={"type": "object", "properties": {}},
        sync_status="stale",
    )

    monkeypatch.setattr(
        services.mcp_client,
        "list_tools",
        lambda _conn: [
            {
                "name": "search",
                "schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            }
        ],
    )

    created_tools, updated_tools = services.sync_connection(conn)

    assert created_tools == []
    assert updated_tools == [existing]
    existing.refresh_from_db()
    assert existing.sync_status == "synced"
    assert existing.schema_json["properties"] == {"q": {"type": "string"}}


@pytest.mark.django_db
def test_sync_connection_skips_invalid_tool_definitions(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed tool entries are ignored while valid MCP tools are synced."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    monkeypatch.setattr(
        services.mcp_client,
        "list_tools",
        lambda _conn: [
            "not-a-dict",
            {"name": ""},
            {"name": "search", "inputSchema": []},
        ],
    )

    created_tools, updated_tools = services.sync_connection(conn)

    assert [tool.name for tool in created_tools] == ["search"]
    assert updated_tools == []
    assert created_tools[0].schema_json == {"type": "object", "properties": {}}


@pytest.mark.django_db
def test_sync_connection_rejects_empty_tools_list(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync requires at least one usable MCP tool definition."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )
    monkeypatch.setattr(services.mcp_client, "list_tools", lambda _conn: [])

    with pytest.raises(ValidationError, match="No valid tools found"):
        services.sync_connection(conn)


@pytest.mark.django_db
@override_settings(TOOL_CURATION_ENABLED=True, TOOL_CURATION_AUTO_SYNC=True)
def test_sync_connection_generates_passthrough_curated_tools(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-sync creates passthrough curated tools behind the feature flag."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="remote",
        transport=Connection.Transport.STREAMABLE_HTTP,
        endpoint="https://example.com/mcp",
    )

    def fake_list_tools(received_conn: Connection) -> list[dict]:
        assert received_conn == conn
        return [
            {
                "name": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
            },
        ]

    monkeypatch.setattr(services.mcp_client, "list_tools", fake_list_tools)

    created_tools, updated_tools = services.sync_connection(conn)

    assert len(created_tools) == 1
    assert updated_tools == []
    curated_tool = CuratedTool.objects.get(connection=conn, name="search")
    assert curated_tool.curator_type == "passthrough"
    assert CurationMapping.objects.get(curated_tool=curated_tool).raw_tool == created_tools[0]


@pytest.mark.django_db
def test_sync_connection_rejects_mcp_client_failure(
    org_env: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sync fails cleanly when tools/list cannot complete."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="legacy",
        transport=Connection.Transport.LEGACY_HTTP,
        endpoint="https://example.com",
    )

    def fake_list_tools(_conn: Connection) -> list[dict]:
        raise mcp_client.MCPClientConfigurationError("unsupported transport")

    monkeypatch.setattr(services.mcp_client, "list_tools", fake_list_tools)

    with pytest.raises(ValidationError, match="MCP tools/list failed"):
        services.sync_connection(conn)

    assert Tool.objects.filter(connection=conn).count() == 0
