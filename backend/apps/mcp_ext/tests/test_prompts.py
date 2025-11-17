"""
Tests for MCP Prompts endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from model_bakery import baker

from apps.agents.models import Agent
from apps.mcp_ext.models import Prompt
from apps.tenants.models import Environment, Organization
from mcp_fabric.errors import ErrorCodes
from mcp_fabric.main import app


@pytest.fixture
def client():
    """Create TestClient instance per test with proper cleanup."""
    with TestClient(app) as c:
        yield c




def test_prompts_list_requires_scope(org_env, mocker, client):
    """Test that listing prompts requires 'mcp:prompts' scope."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts"

    # No token
    response = client.get(url)
    assert response.status_code == 401

    # Token without required scope
    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={"scope": ["mcp:run"], "org_id": str(org.id), "env_id": str(env.id)},
    )
    from mcp_fabric.errors import raise_mcp_http_exception
    http_exception = raise_mcp_http_exception(
        ErrorCodes.INSUFFICIENT_SCOPE, "Missing required scope: mcp:prompts", 403
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


@pytest.mark.django_db
def test_prompts_list_ok(org_env, simple_prompt, prompt_with_schema, mocker, client):
    """Test prompts list endpoint returns prompts with input_schema."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompts"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver - return a mock agent
    mock_agent = mocker.Mock()
    mock_agent.id = "test-agent-id"
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=mock_agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=None,  # Not needed for list endpoint
    )
    # Mock Prompt.objects.filter to avoid DB queries
    mock_qs = mocker.Mock()
    mock_qs.values.return_value = [
        {
            "name": "simple-prompt",
            "description": "Simple prompt",
            "input_schema": {},
        },
        {
            "name": "schema-prompt",
            "description": "Prompt with schema",
            "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
    ]
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.filter",
        return_value=mock_qs,
    )

    response = client.get(url, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Check that inputSchema is present (MCP standard: CamelCase)
    prompt_names = [p["name"] for p in data]
    assert "simple-prompt" in prompt_names
    assert "schema-prompt" in prompt_names

    schema_prompt = next(p for p in data if p["name"] == "schema-prompt")
    assert "inputSchema" in schema_prompt  # MCP standard: CamelCase
    assert schema_prompt["inputSchema"]["type"] == "object"


def test_prompt_invoke_not_found(org_env, agent, mocker, client):
    """Test prompt invoke with non-existent prompt."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/nonexistent/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    # Mock Prompt.objects.get to raise DoesNotExist
    from apps.mcp_ext.models import Prompt
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        side_effect=Prompt.DoesNotExist,
    )

    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )
    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"input": {}},
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.PROMPT_NOT_FOUND


def test_prompt_invoke_policy_denied(org_env, prompt_with_schema, agent, mocker, client):
    """Test prompt invoke with policy denial."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/{prompt_with_schema.name}/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        return_value=prompt_with_schema,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.is_allowed_prompt",
        return_value=(False, "Access denied by policy"),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )

    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"input": {"name": "Test", "age": 30}},
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.FORBIDDEN


def test_prompt_invoke_schema_violation(org_env, prompt_with_schema, agent, mocker, client):
    """Test that invoking a prompt with invalid input schema returns 400."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/{prompt_with_schema.name}/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.is_allowed_prompt",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        return_value=prompt_with_schema,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.render_prompt",
        side_effect=ValueError("Input validation failed: 'name' is a required property"),
    )

    # Missing required field 'name'
    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"input": {"age": 30}},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == ErrorCodes.INVALID_SCHEMA
    assert "Input validation failed" in data["detail"]["error_description"]


def test_prompt_invoke_ok(org_env, prompt_with_schema, agent, mocker, client):
    """Test prompt invoke with valid input returns messages."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/{prompt_with_schema.name}/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.is_allowed_prompt",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        return_value=prompt_with_schema,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.render_prompt",
        return_value={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "User: Alice, Age: 30"},
            ]
        },
    )

    # Test with MCP standard format (arguments)
    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"arguments": {"name": "Alice", "age": 30}},  # MCP standard format
    )

    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) == 2

    # Check first message is system message
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][0]["content"] == "You are a helpful assistant."

    # Check second message is user message with rendered template
    assert data["messages"][1]["role"] == "user"
    assert "Alice" in data["messages"][1]["content"]
    assert "30" in data["messages"][1]["content"]


def test_prompt_invoke_simple_ok(org_env, simple_prompt, agent, mocker, client):
    """Test prompt invoke with simple prompt (no schema validation)."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/{simple_prompt.name}/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.is_allowed_prompt",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        return_value=simple_prompt,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.render_prompt",
        return_value={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
            ]
        },
    )

    # Test with compatibility format (input) - should still work
    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"input": {}},  # Compatibility format
    )

    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][1]["role"] == "user"


def test_prompt_invoke_with_arguments_format(org_env, prompt_with_schema, agent, mocker, client):
    """Test prompt invoke with MCP standard arguments format."""
    org, env = org_env
    url = f"/mcp/{org.id}/{env.id}/.well-known/mcp/prompts/{prompt_with_schema.name}/invoke"

    mocker.patch(
        "mcp_fabric.deps.get_bearer_token",
        return_value="test-token",
    )
    mocker.patch(
        "mcp_fabric.deps.get_validated_token",
        return_value={
            "scope": ["mcp:prompt:invoke"],
            "org_id": str(org.id),
            "env_id": str(env.id),
            "sub": "test-subject",
            "iss": "test-issuer",
        },
    )
    mocker.patch(
        "mcp_fabric.routes_prompts._resolve_org_env",
        return_value=(org, env),
    )
    # Mock agent resolver
    mocker.patch(
        "mcp_fabric.agent_resolver.resolve_agent_from_token_claims",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.get_or_create_mcp_agent",
        return_value=agent,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.is_allowed_prompt",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.check_rate_limit",
        return_value=(True, None),
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.Prompt.objects.get",
        return_value=prompt_with_schema,
    )
    mocker.patch(
        "mcp_fabric.routes_prompts.render_prompt",
        return_value={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "User: Bob, Age: 25"},
            ]
        },
    )

    # Test with MCP standard format (arguments)
    response = client.post(
        url,
        headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        json={"arguments": {"name": "Bob", "age": 25}},  # MCP standard format
    )

    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "system"
    assert data["messages"][1]["role"] == "user"
    assert "Bob" in data["messages"][1]["content"]
    assert "25" in data["messages"][1]["content"]
