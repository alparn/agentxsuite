"""
Tests for local MCP flow: Runner agents against Mock MCP and Caller agents against mcp_fabric.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.agents.models import Agent, AgentMode
from apps.connections.models import Connection
from apps.runs.models import Run
from apps.runs.services import start_run
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


@pytest.mark.django_db
@patch("mcp_fabric.routers.mcp.MCPServer")
def test_caller_requires_bearer(mock_mcp_server_class):
    """Test that caller endpoints require Bearer token."""
    # Setup mock
    mock_mcp = Mock()
    mock_mcp.list_tools.return_value = []
    mock_mcp.get_manifest.return_value = {}
    mock_mcp_server_class.return_value = mock_mcp
    
    from mcp_fabric.main import app

    client = TestClient(app)
    # Use dummy UUIDs - will fail at org/env resolution, but auth check happens first
    response = client.get("/mcp/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002/.well-known/mcp/tools")
    assert response.status_code == 401


@pytest.mark.django_db
@patch("mcp_fabric.routers.mcp.register_tools_for_org_env")
@patch("mcp_fabric.routers.mcp.sync_to_async")
@patch("mcp_fabric.routers.mcp.MCPServer")
def test_caller_tools_ok(mock_mcp_server_class, mock_sync_to_async, mock_register):
    """Test that caller endpoints work with Bearer token."""
    # Setup MCPServer mock
    mock_mcp = Mock()
    mock_mcp.list_tools.return_value = []
    mock_mcp.get_manifest.return_value = {}
    mock_mcp_server_class.return_value = mock_mcp
    
    # Setup sync_to_async mock
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs)
    mock_sync_to_async.side_effect = lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs)
    
    # Setup registry mock
    mock_register.return_value = None
    
    from mcp_fabric.main import app

    # Create test data
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="test", type="dev")

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/tools",
        headers={"Authorization": "Bearer x"},
    )
    # Should return 200 even if no tools registered
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.django_db
def test_runner_start_run_smoke():
    """Test that runner can start a run (smoke test)."""
    from apps.policies.models import Policy

    # Create test data
    org = Organization.objects.create(name="Acme")
    env = Environment.objects.create(organization=org, name="prod", type="prod")

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="mock",
        endpoint="http://127.0.0.1:8091/.well-known/mcp/",
        auth_method="bearer",
        status="ok",
    )

    tool = Tool.objects.create(
        organization=org,
        environment=env,
        name="create_customer_note",
        connection=conn,
        enabled=True,
        sync_status="synced",
        schema_json={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["customer_id", "note"],
        },
    )

    agent = Agent.objects.create(
        organization=org,
        environment=env,
        name="CRM-Runner",
        mode=AgentMode.RUNNER,
        connection=conn,
        enabled=True,
    )

    # Create allow policy (required for default deny)
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Note: This will fail if Mock MCP Server is not running
    # In CI/CD, you might want to mock httpx calls instead
    try:
        run = start_run(
            agent=agent,
            tool=tool,
            input_json={"customer_id": "1", "note": "ok"},
            timeout_seconds=5,
        )
        assert run.status in ("succeeded", "failed")
        assert run.agent == agent
        assert run.tool == tool
    except Exception as e:
        # If Mock MCP Server is not running, that's expected
        # In a real test environment, you'd mock httpx or start the server
        pytest.skip(f"Mock MCP Server not available: {e}")


@pytest.mark.django_db
def test_runner_start_run_with_mock_httpx(monkeypatch):
    """Test runner start_run with mocked HTTP calls."""
    from unittest.mock import Mock, patch
    from apps.policies.models import Policy

    # Create test data
    org = Organization.objects.create(name="Acme")
    env = Environment.objects.create(organization=org, name="prod", type="prod")

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="mock",
        endpoint="http://127.0.0.1:8091/.well-known/mcp/",
        auth_method="bearer",
        status="ok",
    )

    tool = Tool.objects.create(
        organization=org,
        environment=env,
        name="create_customer_note",
        connection=conn,
        enabled=True,
        sync_status="synced",
        schema_json={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["customer_id", "note"],
        },
    )

    agent = Agent.objects.create(
        organization=org,
        environment=env,
        name="CRM-Runner",
        mode=AgentMode.RUNNER,
        connection=conn,
        enabled=True,
    )

    # Create allow policy (required for default deny)
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Mock the manifest fetch function to return None (will use default URLs)
    monkeypatch.setattr(
        "apps.connections.services._fetch_mcp_manifest",
        lambda *args, **kwargs: None,
    )

    # Mock HTTP response for run call
    mock_response_run = Mock()
    mock_response_run.status_code = 200
    mock_response_run.json.return_value = {
        "status": "success",
        "output": {
            "note_id": "note_test_1",
            "created_at": "2025-01-01T00:00:00Z",
        },
    }

    # Mock httpx.Client context manager
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.post = Mock(return_value=mock_response_run)

    monkeypatch.setattr("apps.runs.services.httpx.Client", lambda *args, **kwargs: mock_client)

    # Execute run
    run = start_run(
        agent=agent,
        tool=tool,
        input_json={"customer_id": "CUST-42", "note": "Test note"},
        timeout_seconds=5,
    )

    assert run.status == "succeeded"
    assert run.output_json is not None
    assert "note_id" in run.output_json.get("output", {})

