"""
Shared test fixtures for connections app.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.tenants.models import Environment, Organization


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    return org, env

