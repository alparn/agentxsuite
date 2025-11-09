"""
Unit tests for policy allow/deny logic.
"""
from __future__ import annotations

import pytest

from apps.policies.models import Policy
from apps.policies.services import is_allowed
from apps.tenants.models import Environment, Organization


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
    from apps.agents.models import Agent
    from apps.connections.models import Connection
    from apps.tools.models import Tool

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
        schema_json={"type": "object"},
    )
    return agent, tool


@pytest.mark.django_db
def test_deny_beats_all(agent_tool):
    """Test that deny list takes precedence over allow list."""
    agent, tool = agent_tool

    # Create policy with both deny and allow
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="test-policy",
        rules_json={"deny": [tool.name], "allow": [tool.name]},
        enabled=True,
    )

    # Should be denied
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "denied" in reason.lower()


@pytest.mark.django_db
def test_allow_when_not_in_deny(agent_tool):
    """Test that tool is allowed when in allow list and not in deny list."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Should be allowed
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is True
    assert reason is None


@pytest.mark.django_db
def test_default_deny_without_policy(agent_tool):
    """Test that default deny applies when no policy exists."""
    agent, tool = agent_tool

    # No policy created

    # Should be denied by default
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "No policy explicitly allows" in reason


@pytest.mark.django_db
def test_empty_rules_default_deny(agent_tool):
    """Test that empty rules result in default deny."""
    agent, tool = agent_tool

    # Create policy with empty rules
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="empty-policy",
        rules_json={},
        enabled=True,
    )

    # Should be denied (no explicit allow)
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "No policy explicitly allows" in reason


@pytest.mark.django_db
def test_empty_deny_list_allows_if_in_allow(agent_tool):
    """Test that empty deny list allows if tool is in allow list."""
    agent, tool = agent_tool

    # Create policy with allow list only
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-only-policy",
        rules_json={"allow": [tool.name], "deny": []},
        enabled=True,
    )

    # Should be allowed
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is True
    assert reason is None


@pytest.mark.django_db
def test_multiple_deny_items(agent_tool):
    """Test that multiple items in deny list work correctly."""
    agent, tool = agent_tool

    # Create policy with multiple deny items
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="multi-deny-policy",
        rules_json={"deny": ["tool1", tool.name, "tool3"]},
        enabled=True,
    )

    # Should be denied
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "denied" in reason.lower()


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

    # Should be denied by default (no enabled allow policy)
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "No policy explicitly allows" in reason
