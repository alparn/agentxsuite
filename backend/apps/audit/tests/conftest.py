"""
Shared test fixtures for audit app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.tenants.models import Environment, Organization


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="test", type="dev")
    return org, env

