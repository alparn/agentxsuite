"""
Tests for MCP Resources endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from model_bakery import baker

from apps.agents.models import Agent
from apps.mcp_ext.models import Resource
from apps.tenants.models import Environment, Organization
from mcp_fabric.errors import ErrorCodes
from mcp_fabric.main import app


@pytest.fixture
def client():
    """Create TestClient instance per test with proper cleanup."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="test")
    return org, env


@pytest.fixture
def agent(org_env):
    """Create test agent."""
    org, env = org_env
    return baker.make(Agent, organization=org, environment=env, enabled=True)


@pytest.fixture
def static_resource(org_env):
    """Create static test resource."""
    org, env = org_env
    return baker.make(
        Resource,
        organization=org,
        environment=env,
        name="static-resource",
        type="static",
        config_json={"value": "Hello, World!"},
        mime_type="text/plain",
        enabled=True,
    )


@pytest.fixture
def http_resource(org_env):
    """Create HTTP test resource."""
    org, env = org_env
    return baker.make(
        Resource,
        organization=org,
        environment=env,
        name="http-resource",
        type="http",
        config_json={"url": "https://example.com/api/data"},
        mime_type="application/json",
        enabled=True,
    )


def test_resources_list_requires_scope(org_env, mocker, client):
    """Test that listing resources requires 'mcp:resources' scope."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    # No token
    response = client.get(url)
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers

    # Token without required scope - mock get_validated_token to raise HTTPException
    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    from mcp_fabric.errors import raise_mcp_http_exception
    http_exception = raise_mcp_http_exception(
        ErrorCodes.INSUFFICIENT_SCOPE, "Missing required scope: mcp:resources", 403
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        side_effect=http_exception,
    )
    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.INSUFFICIENT_SCOPE

    # Token with required scope - reset mock to return valid token
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resources"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mock_qs = mocker.Mock()
    mock_qs.values.return_value = []
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.filter",
        return_value=mock_qs,
    )
    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.django_db
def test_resources_list_ok(org_env, static_resource, mocker, client):
    """Test successful resource listing."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resources"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    # Mock Resource.objects.filter to avoid DB queries
    mock_qs = mocker.Mock()
    mock_qs.values.return_value = [
        {
            "name": "static-resource",
            "type": "static",
            "mime_type": "text/plain",
            "schema_json": None,
        }
    ]
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.filter",
        return_value=mock_qs,
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "static-resource"
    assert data[0]["type"] == "static"


def test_resources_read_not_found(org_env, agent, mocker, client):
    """Test resource read with non-existent resource."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/nonexistent"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resource:read"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    # Mock Resource.objects.get to raise DoesNotExist
    from apps.mcp_ext.models import Resource
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        side_effect=Resource.DoesNotExist,
    )
    # Mock check_rate_limit (called before Resource.objects.get in route)
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.RESOURCE_NOT_FOUND


def test_resources_read_policy_denied(org_env, static_resource, agent, mocker, client):
    """Test resource read with policy denial."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{static_resource.name}"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resource:read"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        return_value=static_resource,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(False, "Access denied by policy"),
    )
    # Mock check_rate_limit (called before is_allowed_resource in route)
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.FORBIDDEN


def test_resources_read_static_ok(org_env, static_resource, agent, mocker, client):
    """Test resource read with static type."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{static_resource.name}"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resource:read"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        return_value=static_resource,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.fetch_resource",
        return_value="Hello, World!",
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "static-resource"
    assert data["mime_type"] == "text/plain"
    assert data["content"] == "Hello, World!"


def test_resources_read_http_ok(org_env, http_resource, agent, mocker, client):
    """Test resource read with HTTP type."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{http_resource.name}"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resource:read"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        return_value=http_resource,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.fetch_resource",
        return_value='{"key": "value"}',
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "http-resource"
    assert data["mime_type"] == "application/json"
    assert "key" in data["content"]


def test_resources_read_http_truncation(org_env, http_resource, agent, mocker, client):
    """Test HTTP resource content truncation at 16KB limit."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{http_resource.name}"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:resource:read"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        return_value=http_resource,
    )
    truncated_content = "x" * 16384
    mocker.patch(
        "mcp_fabric.routes_resources.fetch_resource",
        return_value=truncated_content,
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    # Content should be truncated to 16384 bytes
    assert len(data["content"]) <= 16384
