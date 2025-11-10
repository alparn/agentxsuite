"""
Tests for fastmcp run endpoint.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_fabric.main import app


def test_run_missing_tool(mocker):
    """Test run endpoint with missing tool name."""
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

    r = c.post(
        "/mcp/org/env/.well-known/mcp/run",
        headers={"Authorization": "Bearer x"},
        json={"input": {"a": 1}},
    )
    assert r.status_code == 400
    assert "missing_tool_name" in r.json()["detail"]


def test_run_requires_auth(mocker):
    """Test that run endpoint requires authentication."""
    c = TestClient(app)
    r = c.post(
        "/mcp/org/env/.well-known/mcp/run",
        json={"tool": "test-tool", "input": {}},
    )
    assert r.status_code == 401


def test_run_tool_not_found(mocker):
    """Test run endpoint with non-existent tool."""
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

    # Mock MCPServer that raises KeyError for unknown tool
    mock_mcp = mocker.Mock()
    mock_mcp.run_tool.side_effect = KeyError("Tool not found")

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

    r = c.post(
        "/mcp/org/env/.well-known/mcp/run",
        headers={"Authorization": "Bearer x"},
        json={"tool": "non-existent-tool", "input": {}},
    )
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_run_success(mocker):
    """Test successful tool execution."""
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

    # Mock MCPServer with successful run
    mock_mcp = mocker.Mock()
    mock_mcp.run_tool.return_value = {
        "status": "success",
        "output": {"result": "ok"},
    }

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

    r = c.post(
        "/mcp/org/env/.well-known/mcp/run",
        headers={"Authorization": "Bearer x"},
        json={"tool": "test-tool", "input": {"x": 1}},
    )
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "success"

