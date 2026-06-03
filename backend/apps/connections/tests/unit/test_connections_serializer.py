"""
Unit tests for connection serializer validation.
"""
from __future__ import annotations

import pytest

from apps.connections.models import Connection
from apps.connections.serializers import ConnectionSerializer


@pytest.mark.django_db
def test_connection_requires_secret_ref_for_bearer(org_env):
    """Test that bearer auth requires secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "bearer",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "secret_ref" in serializer.errors


@pytest.mark.django_db
def test_connection_requires_secret_ref_for_basic(org_env):
    """Test that basic auth requires secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "basic",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "secret_ref" in serializer.errors


@pytest.mark.django_db
def test_connection_allows_none_auth_without_secret_ref(org_env):
    """Test that none auth doesn't require secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "none",
        },
    )
    # organization_id is set automatically by view, so we set it when saving
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org)
    # Should be valid (secret_ref not required for none)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_connection_validates_auth_method_choices(org_env):
    """Test that invalid auth_method is rejected."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "invalid",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "auth_method" in serializer.errors


@pytest.mark.django_db
def test_connection_requires_endpoint_for_http_transport(org_env):
    """Test that HTTP-based transports require endpoint."""
    _org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "transport": "streamable_http",
            "auth_method": "none",
        },
    )

    assert not serializer.is_valid()
    assert "endpoint" in serializer.errors


@pytest.mark.django_db
def test_connection_requires_command_for_stdio_transport(org_env):
    """Test that stdio transport requires command."""
    _org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "transport": "stdio",
            "auth_method": "none",
        },
    )

    assert not serializer.is_valid()
    assert "command" in serializer.errors


@pytest.mark.django_db
def test_connection_allows_stdio_without_endpoint(org_env):
    """Test that stdio transport can be configured without endpoint."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "postgres",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
            "auth_method": "none",
        },
    )

    serializer.is_valid(raise_exception=True)
    conn = serializer.save(organization=org)

    assert conn.transport == Connection.Transport.STDIO
    assert conn.endpoint is None
    assert conn.command == "npx"
    assert conn.args == ["-y", "@modelcontextprotocol/server-postgres"]


@pytest.mark.django_db
def test_connection_rejects_non_list_args(org_env):
    """Test that command args must be a list."""
    _org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "postgres",
            "transport": "stdio",
            "command": "npx",
            "args": {"bad": "shape"},
            "auth_method": "none",
        },
    )

    assert not serializer.is_valid()
    assert "args" in serializer.errors


@pytest.mark.django_db
def test_connection_secret_ref_not_in_response(org_env):
    """Test that secret refs are not exposed in serializer output."""
    org, env = org_env

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="bearer",
        secret_ref="secret-ref-123",
        env_ref="env-ref-123",
    )
    serializer = ConnectionSerializer(conn)
    data = serializer.data
    assert "secret_ref" not in data
    assert "env_ref" not in data
    assert data["transport"] == Connection.Transport.LEGACY_HTTP

