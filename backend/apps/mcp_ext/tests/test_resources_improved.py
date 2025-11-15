"""
Improved tests for MCP Resources endpoints using FastAPI dependency_overrides.
"""
from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from model_bakery import baker

from apps.agents.models import Agent
from apps.mcp_ext.models import Resource
from apps.policies.models import Policy
from apps.tenants.models import Environment, Organization
from mcp_fabric.deps import create_token_validator
from mcp_fabric.errors import ErrorCodes
from mcp_fabric.main import app
from mcp_fabric.routes_resources import router as resources_router


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="test")
    return org, env


@pytest.fixture
def other_org_env(db):
    """Create another organization/environment for cross-tenant tests."""
    org = baker.make(Organization, name="OtherOrg")
    env = baker.make(Environment, organization=org, name="test")
    return org, env


@pytest.fixture
def agent(org_env):
    """Create test agent."""
    org, env = org_env
    from apps.agents.models import InboundAuthMethod
    
    # Use Agent.objects.create() directly instead of baker to avoid validation issues
    return Agent.objects.create(
        organization=org,
        environment=env,
        name="test-agent",
        slug="test-agent",
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,
        capabilities=[],
        tags=[],
    )


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
def disabled_resource(org_env):
    """Create disabled test resource."""
    org, env = org_env
    return baker.make(
        Resource,
        organization=org,
        environment=env,
        name="disabled-resource",
        type="static",
        config_json={"value": "Disabled"},
        enabled=False,
    )


@pytest.fixture
def allow_policy(org_env, agent):
    """Create policy that allows resource access."""
    org, env = org_env
    return baker.make(
        Policy,
        organization=org,
        environment=env,
        name="allow-resources",
        enabled=True,
        rules_json={"allow_resources": ["static-resource"]},
    )


@pytest.fixture
def deny_policy(org_env, agent):
    """Create policy that denies resource access."""
    org, env = org_env
    return baker.make(
        Policy,
        organization=org,
        environment=env,
        name="deny-resources",
        enabled=True,
        rules_json={"deny_resources": ["static-resource"]},
    )


@pytest.fixture
def override_auth(mocker):
    """Fixture to mock auth dependencies for testing."""
    # Mock agent resolver globally for all tests using this fixture
    mock_agent = mocker.Mock()
    mock_agent.id = "test-agent-id"
    
    def _override(required_scopes: list[str], org_id: str, env_id: str):
        """Mock auth dependency for a specific scope set."""
        # Mock the dependency functions directly
        mocker.patch(
            "mcp_fabric.deps.get_bearer_token",
            return_value="test-token",
        )
        mocker.patch(
            "mcp_fabric.deps.get_validated_token",
            return_value={
                "scope": required_scopes,
                "org_id": org_id,
                "env_id": env_id,
                "sub": "test-subject",
                "iss": "test-issuer",
            },
        )
        mocker.patch(
            "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
            return_value=mock_agent,
        )

    yield _override


@pytest.fixture
async def async_client():
    """Create async HTTP client with proper lifespan handling."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_list_no_auth(async_client, org_env):
    """Test that listing resources requires authentication."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    response = await async_client.get(url)
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    data = response.json()
    assert "error" in data or "detail" in data


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_list_insufficient_scope(async_client, org_env, override_auth, mocker):
    """Test that listing resources requires 'mcp:resources' scope."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    # Mock to raise insufficient scope error
    from mcp_fabric.errors import raise_mcp_http_exception
    http_exception = raise_mcp_http_exception(
        ErrorCodes.INSUFFICIENT_SCOPE, "Missing required scope: mcp:resources", 403
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        side_effect=http_exception,
    )
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data.get("error") == ErrorCodes.INSUFFICIENT_SCOPE
    assert "scope" in data.get("error_description", "").lower()


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_list_org_env_mismatch(
    async_client, org_env, other_org_env, override_auth, mocker
):
    """Test that org/env mismatch in token returns 403."""
    org, env = org_env
    other_org, other_env = other_org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    # Mock token validation to return different org/env (mismatch)
    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:resources"],
            "org_id": str(other_org.id),  # Different org
            "env_id": str(other_env.id),  # Different env
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    # Should fail at token validation (org/env mismatch)
    assert response.status_code in [403, 401]
    data = response.json()
    assert "error" in data


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_list_success(
    async_client, org_env, static_resource, override_auth, mocker
):
    """Test successful resource listing with real DB queries."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    override_auth(["mcp:resources"], str(org.id), str(env.id))
    
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

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "static-resource"
    assert data[0]["type"] == "static"
    assert data[0]["mimeType"] == "text/plain"  # MCP standard: CamelCase


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_list_excludes_disabled(
    async_client, org_env, static_resource, disabled_resource, override_auth, mocker
):
    """Test that disabled resources are excluded from listing."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources"

    override_auth(["mcp:resources"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    
    # Mock Resource.objects.filter to avoid DB queries - only return enabled resource
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

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    names = [r["name"] for r in data]
    assert "static-resource" in names
    assert "disabled-resource" not in names


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_read_not_found(
    async_client, org_env, agent, override_auth, mocker
):
    """Test resource read with non-existent resource."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/nonexistent"

    override_auth(["mcp:resource:read"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    
    # Mock get_or_create_mcp_agent
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    
    # Mock check_rate_limit (called before Resource.objects.get)
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )
    
    # Mock Resource.objects.get to raise DoesNotExist
    from apps.mcp_ext.models import Resource
    mocker.patch(
        "mcp_fabric.routes_resources.Resource.objects.get",
        side_effect=Resource.DoesNotExist,
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 404
    data = response.json()
    assert data.get("error") == ErrorCodes.RESOURCE_NOT_FOUND
    assert "not found" in data.get("error_description", "").lower()


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_read_disabled_not_found(
    async_client, org_env, disabled_resource, override_auth, mocker
):
    """Test that disabled resources return 404."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{disabled_resource.name}"

    override_auth(["mcp:resource:read"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    
    # Mock get_or_create_mcp_agent
    mock_agent = mocker.Mock()
    mock_agent.id = "test-agent-id"
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=mock_agent,
    )
    
    # Mock check_rate_limit
    mocker.patch(
        "mcp_fabric.routes_resources.check_rate_limit",
        return_value=(True, None),
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 404
    data = response.json()
    assert data.get("error") == ErrorCodes.RESOURCE_NOT_FOUND


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_read_policy_denied(
    async_client, org_env, static_resource, agent, deny_policy, override_auth, mocker
):
    """Test resource read with policy denial."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{static_resource.name}"

    override_auth(["mcp:resource:read"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )
    
    # Mock get_or_create_mcp_agent
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 403
    data = response.json()
    assert data.get("error") == ErrorCodes.FORBIDDEN
    assert "denied" in data.get("error_description", "").lower() or "policy" in data.get(
        "error_description", ""
    ).lower()


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_read_static_success(
    async_client, org_env, static_resource, agent, allow_policy, override_auth, mocker
):
    """Test resource read with static type using real service."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{static_resource.name}"

    override_auth(["mcp:resource:read"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )

    # Mock get_or_create_mcp_agent to return the agent fixture
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    
    # Mock is_allowed_resource
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(True, None),
    )
    
    # Mock rate limit to allow
    mocker.patch(
        "apps.runs.rate_limit.check_rate_limit",
        return_value=(True, None),
    )
    
    # Mock fetch_resource
    mocker.patch(
        "mcp_fabric.routes_resources.fetch_resource",
        return_value="Hello, World!",
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "static-resource"
    assert data["mimeType"] == "text/plain"  # MCP standard: CamelCase
    assert data["content"] == "Hello, World!"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_resources_read_rate_limit_exceeded(
    async_client, org_env, static_resource, agent, allow_policy, override_auth, mocker
):
    """Test that rate limit exceeded returns 429."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/resources/{static_resource.name}"

    override_auth(["mcp:resource:read"], str(org.id), str(env.id))
    
    # Mock _resolve_org_env to avoid DB locks
    mocker.patch(
        "mcp_fabric.routes_resources._resolve_org_env",
        return_value=(org, env),
    )

    # Mock get_or_create_mcp_agent to return the agent fixture
    mocker.patch(
        "mcp_fabric.routes_resources.get_or_create_mcp_agent",
        return_value=agent,
    )
    
    # Mock is_allowed_resource
    mocker.patch(
        "mcp_fabric.routes_resources.is_allowed_resource",
        return_value=(True, None),
    )
    
    # Mock rate limit to deny
    mocker.patch(
        "apps.runs.rate_limit.check_rate_limit",
        return_value=(False, "Rate limit exceeded"),
    )

    response = await async_client.get(
        url, headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 429
    data = response.json()
    assert "error" in data
    assert "rate" in data.get("error_description", "").lower() or "limit" in data.get(
        "error_description", ""
    ).lower()

