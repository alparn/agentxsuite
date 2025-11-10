"""
Tests for MCP tools endpoint.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool

User = get_user_model()


@pytest.fixture
def test_user():
    """Create test user with token."""
    user = User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )
    token, _ = Token.objects.get_or_create(user=user)
    return user, token.key


@pytest.fixture
def test_org_env_conn():
    """Create test organization, environment, and connection."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
        status="ok",
    )
    return org, env, conn


@pytest.fixture
def test_tool(test_org_env_conn):
    """Create test tool."""
    org, env, conn = test_org_env_conn
    tool = Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        schema_json={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
            },
            "description": "Test tool",
        },
        sync_status="synced",
        enabled=True,
    )
    return tool


@pytest.mark.django_db
def test_get_tools_success(test_user, test_org_env_conn, test_tool):
    """Test successful tools retrieval."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/tools",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "test-tool"
    assert data["tools"][0]["description"] == "Test tool"
    assert "inputSchema" in data["tools"][0]


@pytest.mark.django_db
def test_get_tools_empty(test_user, test_org_env_conn):
    """Test tools endpoint with no tools."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/tools",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) == 0


@pytest.mark.django_db
def test_get_tools_only_enabled(test_user, test_org_env_conn):
    """Test that only enabled, synced tools are returned."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, conn = test_org_env_conn

    # Create enabled tool
    Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="enabled-tool",
        schema_json={"type": "object"},
        sync_status="synced",
        enabled=True,
    )

    # Create disabled tool
    Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="disabled-tool",
        schema_json={"type": "object"},
        sync_status="synced",
        enabled=False,
    )

    # Create unsynced tool
    Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="unsynced-tool",
        schema_json={"type": "object"},
        sync_status="failed",
        enabled=True,
    )

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/tools",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["name"] == "enabled-tool"


@pytest.mark.django_db
def test_get_tools_unauthorized(test_org_env_conn):
    """Test tools endpoint without authentication."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/tools",
    )

    assert response.status_code == 403

