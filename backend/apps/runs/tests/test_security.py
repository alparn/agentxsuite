"""
Security tests for runs service.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.agents.models import Agent
from apps.audit.models import AuditEvent
from apps.connections.models import Connection
from apps.policies.models import Policy
from apps.runs.models import Run
from apps.runs.rate_limit import RateLimiter
from apps.runs.services import start_run
from apps.runs.timeout import TimeoutError, execute_with_timeout
from apps.runs.validators import validate_input_json
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


@pytest.fixture
def org_env(db):
    """Create organization and environment for tests."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    return org, env


@pytest.fixture
def agent_tool(org_env):
    """Create agent and tool for tests."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
    )
    agent = Agent.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
    )
    tool = Tool.objects.create(
        organization=org,
        environment=env,
        name="test-tool",
        schema_json={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
            },
            "required": ["x"],
        },
    )
    return agent, tool


@pytest.mark.django_db
def test_policy_deny_blocks_run(agent_tool):
    """Test that policy deny blocks run execution."""
    agent, tool = agent_tool

    # Create deny policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=True,
    )

    # Attempt to start run
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == "failed"
    assert "Policy denied" in run.error_text

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_policy").first()
    assert audit is not None
    assert audit.event_data["tool_id"] == str(tool.id)


@pytest.mark.django_db
def test_policy_allow_permits_run(agent_tool):
    """Test that policy allow permits run execution."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Start run should succeed
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == "succeeded"


@pytest.mark.django_db
def test_jsonschema_invalid_input_raises(agent_tool):
    """Test that invalid input raises validation error."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Invalid input (missing required field)
    with pytest.raises(ValueError, match="Input validation failed"):
        start_run(agent=agent, tool=tool, input_json={})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == "failed"
    assert "validation" in run.error_text.lower()

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_validation").first()
    assert audit is not None


@pytest.mark.django_db
def test_jsonschema_valid_input_passes(agent_tool):
    """Test that valid input passes validation."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Valid input
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == "succeeded"


@pytest.mark.django_db
def test_rate_limit_blocks_after_threshold(agent_tool):
    """Test that rate limit blocks after threshold."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Clear cache
    cache.clear()

    # Create rate limiter with low threshold
    limiter = RateLimiter()

    # Create max concurrent runs
    for _ in range(5):
        Run.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="running",
            started_at=timezone.now(),
        )

    # Next run should be blocked
    allowed, reason = limiter.check_rate_limit(agent, max_concurrent_runs=5)
    assert not allowed
    assert "concurrent" in reason.lower()

    # Clean up
    Run.objects.filter(agent=agent).delete()


@pytest.mark.django_db
def test_timeout_stops_long_run(agent_tool):
    """Test that timeout stops long-running operations."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Define a function that takes too long
    def slow_function():
        import time

        time.sleep(2)
        return {"ok": True}

    # Execute with short timeout
    result = execute_with_timeout(slow_function, timeout_seconds=1, default_result=None)
    assert result is None


@pytest.mark.django_db
def test_audit_log_created_on_run(agent_tool):
    """Test that audit log is created on run."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Start run
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify audit logs
    started_audit = AuditEvent.objects.filter(event_type="run_started").first()
    assert started_audit is not None
    assert started_audit.event_data["run_id"] == str(run.id)

    succeeded_audit = AuditEvent.objects.filter(event_type="run_succeeded").first()
    assert succeeded_audit is not None


@pytest.mark.django_db
def test_default_deny_without_policy(agent_tool):
    """Test that default deny applies when no policy exists."""
    agent, tool = agent_tool

    # No policy created

    # Attempt to start run should fail
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == "failed"
    assert "No policy explicitly allows" in run.error_text


@pytest.mark.django_db
def test_disabled_policy_not_applied(agent_tool):
    """Test that disabled policies are not applied."""
    agent, tool = agent_tool

    # Create disabled deny policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="disabled-deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=False,  # Disabled
    )

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Run should succeed (disabled deny policy ignored)
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == "succeeded"

