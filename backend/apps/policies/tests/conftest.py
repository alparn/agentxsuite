"""
Shared test fixtures for policies app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
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
        endpoint="https://example.com",
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
        schema_json={"type": "object"},
        sync_status="synced",
    )
    
    return agent, tool


@pytest.fixture
def user_token(org_env):
    """Create user and token for authentication."""
    user = User.objects.create_user(email="test@example.com", password="testpass123")
    token = Token.objects.create(user=user)
    return token


@pytest.fixture
def api_client():
    """Create API client."""
    from rest_framework.test import APIClient
    
    return APIClient()

