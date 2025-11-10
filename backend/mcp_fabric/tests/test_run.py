"""
Tests for MCP run endpoint.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.agents.models import Agent
from apps.connections.models import Connection
from apps.policies.models import Policy
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
def test_agent(test_org_env_conn):
    """Create test agent."""
    org, env, conn = test_org_env_conn
    agent = Agent.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
        enabled=True,
    )
    return agent


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
        },
        sync_status="synced",
        enabled=True,
    )
    return tool


@pytest.fixture
def test_policy(test_org_env_conn, test_tool):
    """Create allow policy for test tool."""
    org, env, _ = test_org_env_conn
    policy = Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [test_tool.name]},
        enabled=True,
    )
    return policy


@pytest.mark.django_db
def test_run_tool_success(
    test_user,
    test_org_env_conn,
    test_agent,
    test_tool,
    test_policy,
):
    """Test successful tool execution."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.post(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "test-tool",
            "arguments": {"x": 1},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert data["isError"] is False


@pytest.mark.django_db
def test_run_tool_not_found(test_user, test_org_env_conn):
    """Test run endpoint with non-existent tool."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.post(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "non-existent-tool",
            "arguments": {},
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_run_tool_policy_denied(
    test_user,
    test_org_env_conn,
    test_agent,
    test_tool,
):
    """Test run endpoint with policy denial."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    # Create deny policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="deny-policy",
        rules_json={"deny": [test_tool.name]},
        enabled=True,
    )

    client = TestClient(app)
    response = client.post(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "test-tool",
            "arguments": {"x": 1},
        },
    )

    assert response.status_code == 403
    assert "denied" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_run_tool_unauthorized(test_org_env_conn, test_tool):
    """Test run endpoint without authentication."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    org, env, _ = test_org_env_conn

    client = TestClient(app)
    response = client.post(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/run",
        json={
            "name": "test-tool",
            "arguments": {},
        },
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_run_tool_creates_agent(
    test_user,
    test_org_env_conn,
    test_tool,
    test_policy,
):
    """Test that agent is created if it doesn't exist."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env, _ = test_org_env_conn

    # Verify no agent exists
    assert Agent.objects.filter(organization=org, environment=env).count() == 0

    client = TestClient(app)
    response = client.post(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "test-tool",
            "arguments": {"x": 1},
        },
    )

    assert response.status_code == 200
    # Verify agent was created
    assert Agent.objects.filter(organization=org, environment=env).count() == 1
    agent = Agent.objects.get(organization=org, environment=env)
    assert agent.name == "mcp-fabric-agent"

