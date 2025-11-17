"""
Shared test fixtures for system_tools app.
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
    """Create organization and environment for testing."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="test", type="dev")
    return org, env


@pytest.fixture
def connection(org_env):
    """Create a connection for testing."""
    org, env = org_env
    
    return baker.make(
        Connection,
        organization=org,
        environment=env,
        name="Test Connection",
        endpoint="https://example.com",
        auth_method="none",
        status="ok",
    )


@pytest.fixture
def agent(org_env, connection):
    """Create an agent for testing."""
    org, env = org_env
    
    return baker.make(
        Agent,
        organization=org,
        environment=env,
        connection=connection,
        name="Test Agent",
        slug="test-agent",
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,
        capabilities=[],
        tags=[],
    )


@pytest.fixture
def tool(org_env, connection):
    """Create a tool for testing."""
    org, env = org_env
    
    return baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=connection,
        name="test_tool",
        schema_json={"type": "object"},
        sync_status="synced",
    )

