"""
Shared test fixtures for runs app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.agents.models import Agent, InboundAuthMethod
from apps.connections.models import Connection
from apps.policies.models import Policy, PolicyRule
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


def create_policy_with_rules(org, env, name, rules_json=None, enabled=True):
    """
    Helper to create a policy with PolicyRule support.
    
    Args:
        org: Organization instance
        env: Environment instance (can be None for org-wide)
        name: Policy name
        rules_json: Rules dictionary (will be converted to PolicyRule objects)
        enabled: Whether policy is enabled (default: True)
    
    Returns:
        Policy instance
    """
    policy = Policy.objects.create(
        organization=org,
        environment=env,
        name=name,
        is_active=enabled,
    )
    
    # Convert rules_json to PolicyRule objects
    if rules_json:
        # Handle allow list
        allow_list = rules_json.get("allow", [])
        if allow_list:  # Only iterate if not None or empty
            for pattern in allow_list:
                PolicyRule.objects.create(
                    policy=policy,
                    action="tool.invoke",
                    target=f"tool:{pattern}" if not pattern.startswith("tool:") else pattern,
                    effect="allow",
                    conditions={},
                )
        
        # Handle deny list
        deny_list = rules_json.get("deny", [])
        if deny_list:  # Only iterate if not None or empty
            for pattern in deny_list:
                PolicyRule.objects.create(
                    policy=policy,
                    action="tool.invoke",
                    target=f"tool:{pattern}" if not pattern.startswith("tool:") else pattern,
                    effect="deny",
                    conditions={},
                )
    
    return policy


@pytest.fixture
def mock_outbound_mcp_call(monkeypatch):
    """Mock outbound MCP tool calls made by start_run."""
    from apps.connections import mcp_client

    calls = []

    def fake_call_tool(conn, name, arguments=None):
        calls.append(
            {
                "connection_id": str(conn.id),
                "name": name,
                "arguments": arguments or {},
            }
        )
        return {"ok": True, "tool": name, "arguments": arguments or {}}

    monkeypatch.setattr(mcp_client, "call_tool", fake_call_tool)
    return calls


@pytest.fixture(autouse=True)
def _mock_outbound_mcp_call(mock_outbound_mcp_call):
    """Keep runs service unit tests off real outbound MCP transports."""
    return None


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    return org, env


@pytest.fixture
def agent_tool(org_env):
    """Create agent, connection, and tool for tests."""
    org, env = org_env
    
    conn = baker.make(
        Connection,
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="http://localhost:8090",
        auth_method="none",
    )
    
    agent = baker.make(
        Agent,
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
        slug="test-agent",
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,
        capabilities=[],
        tags=[],
    )
    
    tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        schema_json={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
            },
            # No required fields - tests can use empty input_data={}
        },
        sync_status="synced",
        enabled=True,
    )
    
    return agent, tool

