"""
Shared test fixtures for runs app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.agents.models import Agent, InboundAuthMethod
from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


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
        endpoint="http://localhost:8090",  # Use localhost to trigger "own service" path
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

