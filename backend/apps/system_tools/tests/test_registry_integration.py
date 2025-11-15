"""
Integration tests for system tools registry.
"""
from __future__ import annotations

import pytest
from fastmcp.server.server import FastMCP

from apps.system_tools.tools import SYSTEM_TOOLS
from apps.system_tools.services import TOOL_HANDLERS
from mcp_fabric.registry import register_system_tools_for_org_env


@pytest.fixture
def org_env(db):
    """Create organization and environment for testing."""
    from apps.tenants.models import Organization, Environment
    
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="test", type="dev")
    return org, env


@pytest.mark.django_db
def test_system_tools_registered(org_env):
    """Test that system tools are registered in MCP server."""
    org, env = org_env
    
    # Create MCP server instance
    mcp = FastMCP(name="Test MCP Server")
    
    # Register system tools
    register_system_tools_for_org_env(mcp, org=org, env=env)
    
    # Get registered tools
    import asyncio
    tools_dict = asyncio.run(mcp.get_tools())
    
    # Check that all system tools are registered
    registered_tool_names = set(tools_dict.keys()) if isinstance(tools_dict, dict) else set()
    
    expected_tool_names = {tool_def["name"] for tool_def in SYSTEM_TOOLS}
    
    # Verify all system tools are registered
    for tool_name in expected_tool_names:
        assert tool_name in registered_tool_names, f"System tool '{tool_name}' not registered"
    
    # Verify handlers exist for all tools
    for tool_name in expected_tool_names:
        assert tool_name in TOOL_HANDLERS, f"No handler found for system tool '{tool_name}'"


@pytest.mark.django_db
def test_system_tool_handler_mapping():
    """Test that all system tools have corresponding handlers."""
    tool_names = {tool_def["name"] for tool_def in SYSTEM_TOOLS}
    handler_names = set(TOOL_HANDLERS.keys())
    
    # All tools should have handlers
    missing_handlers = tool_names - handler_names
    assert not missing_handlers, f"Missing handlers for tools: {missing_handlers}"
    
    # All handlers should have corresponding tools
    extra_handlers = handler_names - tool_names
    assert not extra_handlers, f"Extra handlers without tools: {extra_handlers}"

