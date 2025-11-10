"""
Tests for fastmcp manifest endpoint.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_fabric.main import app


def test_manifest_requires_auth(mocker):
    """Test that manifest endpoint requires authentication."""
    c = TestClient(app)
    r = c.get("/mcp/org/env/.well-known/mcp/manifest.json")
    assert r.status_code == 401


def test_manifest_ok(mocker):
    """Test successful manifest retrieval."""
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
        "/mcp/org/env/.well-known/mcp/manifest.json",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "protocol_version" in data or "protocolVersion" in data


def test_manifest_invalid_org(mocker):
    """Test manifest with invalid organization."""
    c = TestClient(app)

    # Mock HTTPException for org not found
    from fastapi import HTTPException

    mocker.patch(
        "mcp_fabric.routers.mcp._resolve_org_env",
        side_effect=HTTPException(status_code=404, detail="organization_not_found"),
    )

    # Mock sync_to_async
    async def sync_to_async_wrapper(func, *args, **kwargs):
        return func(*args, **kwargs)

    mocker.patch(
        "mcp_fabric.routers.mcp.sync_to_async",
        side_effect=lambda f: lambda *args, **kwargs: sync_to_async_wrapper(f, *args, **kwargs),
    )

    r = c.get(
        "/mcp/invalid-org/env/.well-known/mcp/manifest.json",
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 404

