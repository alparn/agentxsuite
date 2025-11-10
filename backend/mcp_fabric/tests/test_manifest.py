"""
Tests for MCP manifest endpoint.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.tenants.models import Environment, Organization

User = get_user_model()


@pytest.fixture
def test_user():
    """Create test user with token."""
    user = User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )
    token, _ = Token.objects.get_or_create(user=user)
    return user, token.key


@pytest.fixture
def test_org_env():
    """Create test organization and environment."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    return org, env


@pytest.mark.django_db
def test_get_manifest_success(test_user, test_org_env):
    """Test successful manifest retrieval."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    user, token = test_user
    org, env = test_org_env

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/manifest.json",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["protocol_version"] == "2024-11-05"
    assert data["name"] == f"{org.name}/{env.name}"
    assert "capabilities" in data


@pytest.mark.django_db
def test_get_manifest_unauthorized(test_org_env):
    """Test manifest endpoint without authentication."""
    from fastapi.testclient import TestClient

    from mcp_fabric.main import app

    org, env = test_org_env

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{env.id}/.well-known/mcp/manifest.json",
    )

    assert response.status_code == 403  # FastAPI returns 403 for missing auth


@pytest.mark.django_db
def test_get_manifest_invalid_org(test_user):
    """Test manifest endpoint with invalid organization."""
    from fastapi.testclient import TestClient
    from uuid import uuid4

    from mcp_fabric.main import app

    user, token = test_user
    invalid_org_id = uuid4()

    client = TestClient(app)
    response = client.get(
        f"/mcp/{invalid_org_id}/00000000-0000-0000-0000-000000000000/.well-known/mcp/manifest.json",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_get_manifest_invalid_env(test_user, test_org_env):
    """Test manifest endpoint with invalid environment."""
    from fastapi.testclient import TestClient
    from uuid import uuid4

    from mcp_fabric.main import app

    user, token = test_user
    org, _ = test_org_env
    invalid_env_id = uuid4()

    client = TestClient(app)
    response = client.get(
        f"/mcp/{org.id}/{invalid_env_id}/.well-known/mcp/manifest.json",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404

