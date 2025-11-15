"""
Tests for system tools.
"""
from __future__ import annotations

import pytest

from apps.agents.models import Agent, AgentMode
from apps.connections.models import Connection
from apps.runs.models import Run
from apps.system_tools.services import (
    list_agents_handler,
    get_agent_handler,
    create_agent_handler,
    list_connections_handler,
    list_tools_handler,
    list_runs_handler,
)
from apps.tools.models import Tool


@pytest.fixture
def org_env(db):
    """Create organization and environment for testing."""
    from apps.tenants.models import Organization, Environment
    
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="test", type="dev")
    return org, env


@pytest.fixture
def agent(org_env):
    """Create an agent for testing."""
    org, env = org_env
    return Agent.objects.create(
        organization=org,
        environment=env,
        name="Test Agent",
        mode=AgentMode.RUNNER,
        enabled=True,
    )


@pytest.fixture
def connection(org_env):
    """Create a connection for testing."""
    org, env = org_env
    return Connection.objects.create(
        organization=org,
        environment=env,
        name="Test Connection",
        endpoint="http://example.com",
        auth_method="none",
        status="ok",
    )


@pytest.fixture
def tool(org_env, connection):
    """Create a tool for testing."""
    org, env = org_env
    return Tool.objects.create(
        organization=org,
        environment=env,
        connection=connection,
        name="test_tool",
        version="1.0.0",
        enabled=True,
        schema_json={"type": "object", "properties": {}},
    )


@pytest.mark.django_db
def test_list_agents_handler(org_env, agent):
    """Test list_agents_handler."""
    org, env = org_env
    
    result = list_agents_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        enabled_only=True,
    )
    
    assert result["status"] == "success"
    assert "agents" in result
    assert len(result["agents"]) == 1
    assert result["agents"][0]["name"] == "Test Agent"


@pytest.mark.django_db
def test_list_agents_handler_filter_mode(org_env, agent):
    """Test list_agents_handler with mode filter."""
    org, env = org_env
    
    # Create another agent with different mode
    Agent.objects.create(
        organization=org,
        environment=env,
        name="Caller Agent",
        mode=AgentMode.CALLER,
        enabled=True,
    )
    
    result = list_agents_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        mode="runner",
    )
    
    assert result["status"] == "success"
    assert len(result["agents"]) == 1
    assert result["agents"][0]["mode"] == "runner"


@pytest.mark.django_db
def test_get_agent_handler_by_id(org_env, agent):
    """Test get_agent_handler with agent_id."""
    org, env = org_env
    
    result = get_agent_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        agent_id=str(agent.id),
    )
    
    assert result["status"] == "success"
    assert "agent" in result
    assert result["agent"]["name"] == "Test Agent"


@pytest.mark.django_db
def test_get_agent_handler_by_name(org_env, agent):
    """Test get_agent_handler with agent_name."""
    org, env = org_env
    
    result = get_agent_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        agent_name="Test Agent",
    )
    
    assert result["status"] == "success"
    assert "agent" in result
    assert result["agent"]["id"] == str(agent.id)


@pytest.mark.django_db
def test_get_agent_handler_not_found(org_env):
    """Test get_agent_handler with non-existent agent."""
    org, env = org_env
    
    result = get_agent_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        agent_name="NonExistent",
    )
    
    assert result["status"] == "error"
    assert result["error"] == "agent_not_found"


@pytest.mark.django_db
def test_create_agent_handler(org_env):
    """Test create_agent_handler."""
    org, env = org_env
    
    result = create_agent_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        name="New Agent",
        mode="runner",
        enabled=True,
    )
    
    assert result["status"] == "success"
    assert "agent_id" in result
    assert "agent" in result
    assert result["agent"]["name"] == "New Agent"
    
    # Verify agent was created
    agent = Agent.objects.get(id=result["agent_id"])
    assert agent.name == "New Agent"
    assert agent.mode == AgentMode.RUNNER


@pytest.mark.django_db
def test_create_agent_handler_duplicate(org_env, agent):
    """Test create_agent_handler with duplicate name."""
    org, env = org_env
    
    result = create_agent_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        name="Test Agent",  # Same name as existing agent
        mode="runner",
    )
    
    assert result["status"] == "error"
    assert result["error"] == "agent_already_exists"


@pytest.mark.django_db
def test_list_connections_handler(org_env, connection):
    """Test list_connections_handler."""
    org, env = org_env
    
    result = list_connections_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
    )
    
    assert result["status"] == "success"
    assert "connections" in result
    assert len(result["connections"]) == 1
    assert result["connections"][0]["name"] == "Test Connection"


@pytest.mark.django_db
def test_list_connections_handler_filter_status(org_env, connection):
    """Test list_connections_handler with status filter."""
    org, env = org_env
    
    # Create another connection with different status
    Connection.objects.create(
        organization=org,
        environment=env,
        name="Failed Connection",
        endpoint="http://failed.com",
        auth_method="none",
        status="fail",
    )
    
    result = list_connections_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        status="ok",
    )
    
    assert result["status"] == "success"
    assert len(result["connections"]) == 1
    assert result["connections"][0]["status"] == "ok"


@pytest.mark.django_db
def test_list_tools_handler(org_env, tool):
    """Test list_tools_handler."""
    org, env = org_env
    
    result = list_tools_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        enabled_only=True,
    )
    
    assert result["status"] == "success"
    assert "tools" in result
    assert len(result["tools"]) == 1
    assert result["tools"][0]["name"] == "test_tool"


@pytest.mark.django_db
def test_list_runs_handler(org_env, agent, tool):
    """Test list_runs_handler."""
    org, env = org_env
    
    # Create a run
    run = Run.objects.create(
        organization=org,
        environment=env,
        agent=agent,
        tool=tool,
        status="succeeded",
        input_json={},
        output_json={"result": "success"},
    )
    
    result = list_runs_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        limit=10,
    )
    
    assert result["status"] == "success"
    assert "runs" in result
    assert len(result["runs"]) == 1
    assert result["runs"][0]["status"] == "succeeded"


@pytest.mark.django_db
def test_list_runs_handler_filter_status(org_env, agent, tool):
    """Test list_runs_handler with status filter."""
    org, env = org_env
    
    # Create runs with different statuses
    Run.objects.create(
        organization=org,
        environment=env,
        agent=agent,
        tool=tool,
        status="succeeded",
        input_json={},
    )
    Run.objects.create(
        organization=org,
        environment=env,
        agent=agent,
        tool=tool,
        status="failed",
        input_json={},
    )
    
    result = list_runs_handler(
        organization_id=str(org.id),
        environment_id=str(env.id),
        status="succeeded",
    )
    
    assert result["status"] == "success"
    assert len(result["runs"]) == 1
    assert result["runs"][0]["status"] == "succeeded"


@pytest.mark.django_db
def test_handlers_with_invalid_org_env():
    """Test handlers with invalid organization/environment."""
    invalid_id = "00000000-0000-0000-0000-000000000000"
    
    result = list_agents_handler(
        organization_id=invalid_id,
        environment_id=invalid_id,
    )
    
    assert result["status"] == "error"
    assert result["error"] == "not_found"

