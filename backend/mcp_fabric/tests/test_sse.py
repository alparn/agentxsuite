"""
Tests for MCP SSE and messages endpoints.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from mcp_fabric.main import app


@pytest.mark.skip(reason="SSE endpoint has infinite loop - requires special async test handling")
def test_sse_endpoint(mocker):
    """Test SSE endpoint connection and initial event."""
    c = TestClient(app)
    
    # Mock org/env resolution
    mock_org = mocker.Mock()
    mock_org.id = "org-id"
    mock_org.name = "TestOrg"
    mock_env = mocker.Mock()
    mock_env.id = "env-id"
    mock_env.name = "TestEnv"
    
    mocker.patch("mcp_fabric.routers.mcp._resolve_org_env", return_value=(mock_org, mock_env))
    
    # Mock auth via deps patches
    mocker.patch("mcp_fabric.deps.get_bearer_token", return_value="test-token")
    mocker.patch("mcp_fabric.deps.get_validated_token", return_value={"org_id": "org-id", "env_id": "env-id", "scope": "mcp:connect"})
    
    # Also need to patch resolve_agent_from_token_claims in agent_resolver
    mock_agent = mocker.Mock()
    mock_agent.id = "agent-id"
    mocker.patch("mcp_fabric.agent_resolver.resolve_agent_from_token_claims", return_value=mock_agent)
    
    # Mock sync_to_async in deps.py
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs) if callable(func) else func
        
    mocker.patch("mcp_fabric.deps.sync_to_async", side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs))

    response = c.get("/.well-known/mcp/sse", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_messages_endpoint(mocker):
    """Test messages endpoint for JSON-RPC."""
    c = TestClient(app)
    
    # Mock org/env
    mock_org = mocker.Mock()
    mock_org.id = "org-id"
    mock_org.name = "TestOrg"
    mock_env = mocker.Mock()
    mock_env.id = "env-id"
    mock_env.name = "TestEnv"
    
    mocker.patch("mcp_fabric.routers.mcp._resolve_org_env", return_value=(mock_org, mock_env))
    
    # Mock auth via deps patches
    mocker.patch("mcp_fabric.deps.get_bearer_token", return_value="test-token")
    mocker.patch("mcp_fabric.deps.get_validated_token", return_value={"org_id": "org-id", "env_id": "env-id", "scope": "mcp:connect"})
    
    mock_agent = mocker.Mock()
    mock_agent.id = "agent-id"
    mocker.patch("mcp_fabric.agent_resolver.resolve_agent_from_token_claims", return_value=mock_agent)
    
    # Mock MCPServer
    mock_mcp = mocker.Mock()
    mock_mcp.get_tools = AsyncMock(return_value={})
    mocker.patch("mcp_fabric.routers.mcp.MCPServer", return_value=mock_mcp)
    mocker.patch("mcp_fabric.routers.mcp.register_tools_for_org_env")
    
    # Mock sync_to_async
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs) if callable(func) else func
    
    # Patch both router and deps sync_to_async
    mocker.patch("mcp_fabric.routers.mcp.sync_to_async", side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs))
    mocker.patch("mcp_fabric.deps.sync_to_async", side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs))

    # Test initialize
    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {},
        "id": 1
    }
    
    response = c.post("/.well-known/mcp/messages", json=payload, headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["protocolVersion"] == "2024-11-05"
    assert data["result"]["serverInfo"]["name"] == "AgentxSuite MCP - TestOrg/TestEnv"
    
    # Test tools/list
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 2
    }
    response = c.post("/.well-known/mcp/messages", json=payload, headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data["result"]
