"""
Shared test fixtures and utilities for MCP Ext tests.
"""
from __future__ import annotations

from typing import AsyncGenerator
from uuid import UUID

import httpx
import pytest
from fastapi import Depends
from model_bakery import baker

from apps.agents.models import Agent
from apps.mcp_ext.models import Prompt, Resource
from apps.tenants.models import Environment, Organization
from mcp_fabric.deps import create_token_validator
from mcp_fabric.main import app


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
    from apps.agents.models import InboundAuthMethod
    
    # Create agent with skip_validation to avoid validation errors during creation
    agent = baker.prepare(
        Agent,
        organization=org,
        environment=env,
        name="test-agent",
        slug="test-agent",  # Explicit slug to avoid auto-generation issues
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,  # NONE doesn't require secret_ref
        capabilities=[],  # Empty list required
        tags=[],  # Empty list required
    )
    # Save with skip_validation=True to bypass clean() validation
    agent.save(skip_validation=True)
    return agent


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
def simple_prompt(org_env):
    """Create simple test prompt without schema."""
    org, env = org_env
    return baker.make(
        Prompt,
        organization=org,
        environment=env,
        name="simple-prompt",
        description="Simple prompt",
        input_schema={},
        template_system="You are a helpful assistant.",
        template_user="Hello!",
        enabled=True,
    )


@pytest.fixture
def prompt_with_schema(org_env):
    """Create test prompt with input schema."""
    org, env = org_env
    return baker.make(
        Prompt,
        organization=org,
        environment=env,
        name="schema-prompt",
        description="Prompt with schema",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        template_system="You are a helpful assistant.",
        template_user="User: {{ name }}, Age: {{ age|default('N/A') }}",
        enabled=True,
    )


@pytest.fixture
def disabled_prompt(org_env):
    """Create disabled test prompt."""
    org, env = org_env
    return baker.make(
        Prompt,
        organization=org,
        environment=env,
        name="disabled-prompt",
        description="Disabled prompt",
        input_schema={},
        enabled=False,
    )


def create_auth_override(required_scopes: list[str], org_id: str, env_id: str):
    """Create auth dependency override for testing."""

    async def override_auth(
        org_id_param: UUID = None,
        env_id_param: UUID = None,
        credentials=None,
    ):
        return {
            "scope": required_scopes,
            "org_id": org_id,
            "env_id": env_id,
        }

    return override_auth


@pytest.fixture
async def async_client():
    """Create async HTTP client with proper lifespan handling."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Helper to create auth headers."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def override_auth():
    """Fixture to override auth dependencies."""
    overrides = {}

    def _override(required_scopes: list[str], org_id: str, env_id: str):
        validator = create_token_validator(required_scopes)
        override_func = create_auth_override(required_scopes, org_id, env_id)
        overrides[validator] = override_func
        app.dependency_overrides[validator] = override_func

    yield _override

    # Cleanup
    app.dependency_overrides.clear()

