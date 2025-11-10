"""
Tests for fastmcp tools endpoint.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_fabric.main import app


def test_tools_empty(mocker):
    """Test tools endpoint with no tools."""
    c = TestClient(app)

    # Mock org/env resolution
    mock_org = mocker.Mock()
    mock_org.id = "org-id"
    mock_org.name = "TestOrg"
    mock_env = mocker.Mock()
    mock_env.id = "env-id"
    mock_env.name = "TestEnv"

    mocker.patch(
        "mcp_fabric.routers.mcp._resolve_org_env",
        return_value=(mock_org, mock_env),
    )

    # Mock registry (no tools registered)
    mocker.patch(
        "mcp_fabric.routers.mcp.register_tools_for_org_env",
        return_value=None,
    )

    # Mock sync_to_async
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs)

    mocker.patch(
        "mcp_fabric.routers.mcp.sync_to_async",
        side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs),
    )

    r = c.get(
        "/mcp/org/env/.well-known/mcp/tools",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_tools_requires_auth(mocker):
    """Test that tools endpoint requires authentication."""
    c = TestClient(app)
    r = c.get("/mcp/org/env/.well-known/mcp/tools")
    assert r.status_code == 401


def test_tools_with_registered_tools(mocker):
    """Test tools endpoint with registered tools."""
    c = TestClient(app)

    # Mock org/env resolution
    mock_org = mocker.Mock()
    mock_org.id = "org-id"
    mock_org.name = "TestOrg"
    mock_env = mocker.Mock()
    mock_env.id = "env-id"
    mock_env.name = "TestEnv"

    mocker.patch(
        "mcp_fabric.routers.mcp._resolve_org_env",
        return_value=(mock_org, mock_env),
    )

    # Mock MCPServer with tools
    mock_mcp = mocker.Mock()
    mock_mcp.list_tools.return_value = [
        {
            "name": "test-tool",
            "description": "Test tool",
            "inputSchema": {"type": "object"},
        }
    ]

    # Mock MCPServer creation
    mocker.patch(
        "mcp_fabric.routers.mcp.MCPServer",
        return_value=mock_mcp,
    )

    # Mock registry
    mocker.patch(
        "mcp_fabric.routers.mcp.register_tools_for_org_env",
        return_value=None,
    )

    # Mock sync_to_async
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs)

    mocker.patch(
        "mcp_fabric.routers.mcp.sync_to_async",
        side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs),
    )

    r = c.get(
        "/mcp/org/env/.well-known/mcp/tools",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "test-tool"

