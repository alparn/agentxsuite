"""
Shared test fixtures for tools app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.tenants.models import Environment, Organization
from apps.connections.models import Connection


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    return org, env


@pytest.fixture
def org_env_conn(org_env):
    """Create test organization, environment, and connection."""
    org, env = org_env
    conn = baker.make(
        Connection,
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
    )
    return org, env, conn

