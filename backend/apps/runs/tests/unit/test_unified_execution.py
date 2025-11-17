"""
Unit tests for unified execution service functions.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from apps.agents.models import Agent
from apps.policies.models import Policy
from apps.runs.services import (
    ExecutionContext,
    execute_tool_run,
    format_run_response,
    resolve_agent,
    resolve_tool,
)
from apps.tenants.models import Environment, Organization


# ========== resolve_agent Tests ==========


@pytest.mark.django_db
def test_resolve_agent_from_token(org_env, agent_tool):
    """Test that agent is resolved from token (highest priority)."""
    org, env = org_env
    agent, _ = agent_tool
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    resolved = resolve_agent(
        organization=org,
        environment=env,
        requested_agent_id=None,
        context=context,
    )
    
    assert resolved.id == agent.id
    assert resolved.name == agent.name


@pytest.mark.django_db
def test_resolve_agent_from_token_with_matching_request(org_env, agent_tool):
    """Test that agent from token works even if request also specifies same agent."""
    org, env = org_env
    agent, _ = agent_tool
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    resolved = resolve_agent(
        organization=org,
        environment=env,
        requested_agent_id=str(agent.id),  # Same as token
        context=context,
    )
    
    assert resolved.id == agent.id


@pytest.mark.django_db
def test_resolve_agent_token_mismatch_raises(org_env, agent_tool):
    """Test that agent mismatch between token and request raises error."""
    org, env = org_env
    agent, _ = agent_tool
    from apps.agents.models import AgentMode
    
    # Create another agent (CALLER mode doesn't need connection)
    other_agent = Agent.objects.create(
        organization=org,
        environment=env,
        name="other-agent",
        mode=AgentMode.CALLER,
        enabled=True,
        inbound_auth_method="none",
    )
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    with pytest.raises(ValueError, match="Agent mismatch"):
        resolve_agent(
            organization=org,
            environment=env,
            requested_agent_id=str(other_agent.id),  # Different from token
            context=context,
        )


@pytest.mark.django_db
def test_resolve_agent_from_request(org_env, agent_tool):
    """Test that agent is resolved from request when no token agent."""
    org, env = org_env
    agent, _ = agent_tool
    
    context = ExecutionContext(token_agent_id=None)
    
    resolved = resolve_agent(
        organization=org,
        environment=env,
        requested_agent_id=str(agent.id),
        context=context,
    )
    
    assert resolved.id == agent.id


@pytest.mark.django_db
def test_resolve_agent_no_agent_raises(org_env):
    """Test that missing agent raises error (no fallback)."""
    org, env = org_env
    
    context = ExecutionContext(token_agent_id=None)
    
    with pytest.raises(ValueError, match="Agent selection required"):
        resolve_agent(
            organization=org,
            environment=env,
            requested_agent_id=None,
            context=context,
        )


@pytest.mark.django_db
def test_resolve_agent_disabled_raises(org_env, agent_tool):
    """Test that disabled agent raises error."""
    org, env = org_env
    agent, _ = agent_tool
    
    agent.enabled = False
    agent.save()
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    with pytest.raises(ValueError, match="not found.*disabled"):
        resolve_agent(
            organization=org,
            environment=env,
            requested_agent_id=None,
            context=context,
        )


@pytest.mark.django_db
def test_resolve_agent_wrong_org_raises(org_env, agent_tool):
    """Test that agent from different org raises error."""
    org, env = org_env
    agent, _ = agent_tool
    
    # Create different org
    other_org = Organization.objects.create(name="OtherOrg")
    other_env = Environment.objects.create(organization=other_org, name="dev", type="dev")
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    with pytest.raises(ValueError, match="doesn't belong"):
        resolve_agent(
            organization=other_org,
            environment=other_env,
            requested_agent_id=None,
            context=context,
        )


# ========== resolve_tool Tests ==========


@pytest.mark.django_db
def test_resolve_tool_by_uuid(org_env, agent_tool):
    """Test that tool is resolved by UUID."""
    org, env = org_env
    _, tool = agent_tool
    
    resolved = resolve_tool(
        organization=org,
        environment=env,
        tool_identifier=str(tool.id),
    )
    
    assert resolved.id == tool.id
    assert resolved.name == tool.name


@pytest.mark.django_db
def test_resolve_tool_by_name(org_env, agent_tool):
    """Test that tool is resolved by name."""
    org, env = org_env
    _, tool = agent_tool
    
    resolved = resolve_tool(
        organization=org,
        environment=env,
        tool_identifier=tool.name,
    )
    
    assert resolved.id == tool.id
    assert resolved.name == tool.name


@pytest.mark.django_db
def test_resolve_tool_not_found_raises(org_env):
    """Test that non-existent tool raises error."""
    org, env = org_env
    
    with pytest.raises(ValueError, match="not found"):
        resolve_tool(
            organization=org,
            environment=env,
            tool_identifier=str(uuid4()),
        )


@pytest.mark.django_db
def test_resolve_tool_disabled_raises(org_env, agent_tool):
    """Test that disabled tool raises error."""
    org, env = org_env
    _, tool = agent_tool
    
    tool.enabled = False
    tool.save()
    
    with pytest.raises(ValueError, match="not found.*enabled"):
        resolve_tool(
            organization=org,
            environment=env,
            tool_identifier=tool.name,
        )


@pytest.mark.django_db
def test_resolve_tool_wrong_org_raises(org_env, agent_tool):
    """Test that tool from different org raises error."""
    org, env = org_env
    _, tool = agent_tool
    
    # Create different org
    other_org = Organization.objects.create(name="OtherOrg")
    other_env = Environment.objects.create(organization=other_org, name="dev", type="dev")
    
    with pytest.raises(ValueError, match="not found"):
        resolve_tool(
            organization=other_org,
            environment=other_env,
            tool_identifier=tool.name,
        )


# ========== format_run_response Tests ==========


@pytest.mark.django_db
def test_format_run_response_success(agent_tool):
    """Test formatting successful run response."""
    agent, tool = agent_tool
    from apps.runs.models import Run
    from django.utils import timezone
    
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool,
        status="succeeded",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        output_json={"result": "success"},
    )
    
    response = format_run_response(run)
    
    assert response["run_id"] == str(run.id)
    assert response["status"] == "succeeded"
    assert response["isError"] is False
    assert len(response["content"]) > 0
    assert response["agent"]["id"] == str(agent.id)
    assert response["tool"]["id"] == str(tool.id)
    assert response["execution"]["started_at"] is not None
    assert response["execution"]["duration_ms"] is not None


@pytest.mark.django_db
def test_format_run_response_failed(agent_tool):
    """Test formatting failed run response."""
    agent, tool = agent_tool
    from apps.runs.models import Run
    from django.utils import timezone
    
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool,
        status="failed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        error_text="Test error",
    )
    
    response = format_run_response(run)
    
    assert response["status"] == "failed"
    assert response["isError"] is True
    assert len(response["content"]) > 0
    assert "Test error" in response["content"][0]["text"]


@pytest.mark.django_db
def test_format_run_response_string_output(agent_tool):
    """Test formatting run with string output."""
    agent, tool = agent_tool
    from apps.runs.models import Run
    from django.utils import timezone
    
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool,
        status="succeeded",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        output_json="Simple string output",
    )
    
    response = format_run_response(run)
    
    assert response["content"][0]["text"] == "Simple string output"


# ========== execute_tool_run Tests ==========


@pytest.mark.django_db
def test_execute_tool_run_success(org_env, agent_tool):
    """Test successful tool execution via unified service."""
    org, env = org_env
    agent, tool = agent_tool
    
    # Create allow policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    result = execute_tool_run(
        organization=org,
        environment=env,
        tool_identifier=str(tool.id),
        agent_identifier=None,
        input_data={},
        context=context,
    )
    
    assert result["status"] == "succeeded"
    assert result["isError"] is False
    assert result["run_id"] is not None
    assert result["agent"]["id"] == str(agent.id)
    assert result["tool"]["id"] == str(tool.id)


@pytest.mark.django_db
def test_execute_tool_run_by_name(org_env, agent_tool):
    """Test tool execution using tool name instead of UUID."""
    org, env = org_env
    agent, tool = agent_tool
    
    # Create allow policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    result = execute_tool_run(
        organization=org,
        environment=env,
        tool_identifier=tool.name,
        agent_identifier=None,
        input_data={},
        context=context,
    )
    
    assert result["status"] == "succeeded"
    assert result["tool"]["name"] == tool.name


@pytest.mark.django_db
def test_execute_tool_run_with_request_agent(org_env, agent_tool):
    """Test tool execution with agent from request (no token agent)."""
    org, env = org_env
    agent, tool = agent_tool
    
    # Create allow policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )
    
    context = ExecutionContext(token_agent_id=None)
    
    result = execute_tool_run(
        organization=org,
        environment=env,
        tool_identifier=str(tool.id),
        agent_identifier=str(agent.id),
        input_data={},
        context=context,
    )
    
    assert result["status"] == "succeeded"
    assert result["agent"]["id"] == str(agent.id)


@pytest.mark.django_db
def test_execute_tool_run_no_agent_raises(org_env, agent_tool):
    """Test that missing agent raises error."""
    org, env = org_env
    _, tool = agent_tool
    
    context = ExecutionContext(token_agent_id=None)
    
    with pytest.raises(ValueError, match="Agent selection required"):
        execute_tool_run(
            organization=org,
            environment=env,
            tool_identifier=str(tool.id),
            agent_identifier=None,
            input_data={},
            context=context,
        )


@pytest.mark.django_db
def test_execute_tool_run_policy_denied(org_env, agent_tool):
    """Test that policy denial is handled correctly."""
    org, env = org_env
    agent, tool = agent_tool
    
    # Create deny policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=True,
    )
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    with pytest.raises(ValueError, match="Policy denied"):
        execute_tool_run(
            organization=org,
            environment=env,
            tool_identifier=str(tool.id),
            agent_identifier=None,
            input_data={},
            context=context,
        )


@pytest.mark.django_db
def test_execute_tool_run_invalid_input(org_env, agent_tool):
    """Test that invalid input validation is handled."""
    org, env = org_env
    agent, tool = agent_tool
    
    # Update tool with required field
    tool.schema_json = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
        },
        "required": ["x"],
    }
    tool.save()
    
    # Create allow policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )
    
    context = ExecutionContext(token_agent_id=str(agent.id))
    
    with pytest.raises(ValueError, match="validation"):
        execute_tool_run(
            organization=org,
            environment=env,
            tool_identifier=str(tool.id),
            agent_identifier=None,
            input_data={},  # Missing required field "x"
            context=context,
        )

