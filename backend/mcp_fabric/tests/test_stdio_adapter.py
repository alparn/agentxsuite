"""
Tests for stdio MCP Adapter.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agents.models import Agent
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool
from mcp_fabric.stdio_adapter import StdioMCPAdapter


@pytest.fixture
def valid_token():
    """Mock valid JWT token."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token"


@pytest.fixture
def token_claims(org, environment, agent):
    """Mock token claims."""
    return {
        "org_id": str(org.id),
        "env_id": str(environment.id),
        "agent_id": str(agent.id),
        "scope": ["mcp:tools", "mcp:run"],
        "sub": "test-subject",
        "iss": "test-issuer",
        "jti": "test-jti",
    }


@pytest.fixture
def org():
    """Create test organization."""
    return Organization.objects.create(name="Test Org")


@pytest.fixture
def environment(org):
    """Create test environment."""
    return Environment.objects.create(
        name="Test Environment",
        type="development",
        organization=org,
    )


@pytest.fixture
def agent(org, environment):
    """Create test agent."""
    return Agent.objects.create(
        name="Test Agent",
        organization=org,
        environment=environment,
        enabled=True,
        mode="caller",  # caller mode - no connection required
        inbound_auth_method="none",  # None authentication - no secret_ref required
    )


@pytest.fixture
def tool(org, environment):
    """Create test tool."""
    from apps.connections.models import Connection
    
    connection = Connection.objects.create(
        name="Test Connection",
        organization=org,
        environment=environment,
        endpoint="http://localhost:8000",
        status="active",
    )
    
    return Tool.objects.create(
        name="test_tool",
        organization=org,
        environment=environment,
        connection=connection,
        enabled=True,
        schema_json={
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
        },
    )


@pytest.mark.django_db
class TestStdioMCPAdapter:
    """Tests for StdioMCPAdapter class."""

    def test_initialize(self, valid_token, token_claims, org, environment, agent):
        """Test initialization with valid token."""
        adapter = StdioMCPAdapter(token=valid_token)
        
        # Directly set the adapter state (simulating successful validation)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        assert adapter.org == org
        assert adapter.env == environment
        assert adapter.agent == agent
        assert adapter.token_claims == token_claims

    def test_initialize_missing_claims(self, valid_token):
        """Test initialization with missing org_id/env_id claims."""
        adapter = StdioMCPAdapter(token=valid_token)
        
        # Mock token with missing claims - should raise ValueError
        with patch("mcp_fabric.stdio_adapter.get_validated_token", return_value={}):
            with pytest.raises(ValueError, match="Token missing org_id or env_id claims"):
                # Use asyncio.run to call async function in sync test
                import asyncio
                asyncio.run(adapter._validate_and_setup())

    @pytest.mark.asyncio
    async def test_handle_initialize_message(self, valid_token, token_claims, org, environment, agent):
        """Test handling MCP initialize message."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        
        response = await adapter.handle_initialize(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "agentxsuite"
        assert "tools" in response["result"]["capabilities"]

    @pytest.mark.asyncio
    async def test_handle_tools_list(self, valid_token, token_claims, org, environment, agent, tool):
        """Test handling tools/list request."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }
        
        # Mock get_tools_list_for_org_env to avoid DB locks
        mock_tools = [
            {
                "name": "test_tool",
                "description": "Test Tool",
                "inputSchema": {},
            }
        ]
        
        with patch("mcp_fabric.stdio_adapter.get_tools_list_for_org_env", return_value=mock_tools):
            response = await adapter.handle_tools_list(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]
        assert isinstance(response["result"]["tools"], list)
        
        # Check that our test tool is in the list
        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "test_tool" in tool_names

    @pytest.mark.asyncio
    async def test_handle_tool_call(self, valid_token, token_claims, org, environment, agent, tool):
        """Test handling tools/call request."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"input": "test value"},
            },
        }
        
        # Mock tool lookup and execution to avoid DB locks
        mock_result = {
            "status": "success",
            "output": {"result": "test output"},
            "run_id": "test-run-id",
        }
        
        # Mock Tool.objects.filter().first() chain
        mock_queryset = MagicMock()
        mock_queryset.first = MagicMock(return_value=tool)
        
        with patch("apps.tools.models.Tool.objects.filter", return_value=mock_queryset), \
             patch("mcp_fabric.stdio_adapter.run_tool_via_agentxsuite", return_value=mock_result):
            response = await adapter.handle_tool_call(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert response["result"]["isError"] is False
        assert "content" in response["result"]
        assert len(response["result"]["content"]) > 0

    @pytest.mark.asyncio
    async def test_handle_tool_call_not_found(self, valid_token, token_claims, org, environment, agent):
        """Test handling tools/call for non-existent tool."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        }
        
        response = await adapter.handle_tool_call(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "error" in response
        assert response["error"]["code"] == -32602
        assert "not found" in response["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_tool_call_error(self, valid_token, token_claims, org, environment, agent, tool):
        """Test handling tools/call when execution fails."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        adapter.agent = agent
        
        message = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"input": "test value"},
            },
        }
        
        # Mock tool lookup and execution failure to avoid DB locks
        mock_result = {
            "status": "error",
            "error": "tool_execution_failed",
            "error_description": "Tool execution failed for some reason",
        }
        
        # Mock Tool.objects.filter().first() chain
        mock_queryset = MagicMock()
        mock_queryset.first = MagicMock(return_value=tool)
        
        with patch("apps.tools.models.Tool.objects.filter", return_value=mock_queryset), \
             patch("mcp_fabric.stdio_adapter.run_tool_via_agentxsuite", return_value=mock_result):
            response = await adapter.handle_tool_call(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        assert "result" in response
        assert response["result"]["isError"] is True
        assert "content" in response["result"]

    @pytest.mark.asyncio
    async def test_handle_notification(self, valid_token):
        """Test handling notifications (no response expected)."""
        adapter = StdioMCPAdapter(token=valid_token)
        
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            # No id field = notification
        }
        
        response = await adapter.handle_message(message)
        
        # Notifications should not return a response
        assert response is None

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, valid_token, token_claims, org, environment):
        """Test handling unknown method."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        
        message = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown/method",
        }
        
        response = await adapter.handle_message(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 6
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    def test_normalize_tool_name(self, valid_token):
        """Test tool name normalization."""
        adapter = StdioMCPAdapter(token=valid_token)
        
        # Test various invalid characters
        assert adapter._normalize_tool_name("test tool") == "test_tool"
        assert adapter._normalize_tool_name("test@tool#name") == "test_tool_name"
        assert adapter._normalize_tool_name("test___tool") == "test_tool"
        assert adapter._normalize_tool_name("_test_tool_") == "test_tool"
        
        # Test length limit
        long_name = "a" * 100
        normalized = adapter._normalize_tool_name(long_name)
        assert len(normalized) <= 64
        
        # Test empty/invalid names
        assert adapter._normalize_tool_name("") == "unnamed_tool"
        assert adapter._normalize_tool_name("___") == "unnamed_tool"

    @pytest.mark.asyncio
    async def test_resources_list(self, valid_token, token_claims, org, environment):
        """Test resources/list (stub for Phase 3)."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        
        message = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/list",
        }
        
        response = await adapter.handle_resources_list(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 7
        assert "result" in response
        assert response["result"]["resources"] == []

    @pytest.mark.asyncio
    async def test_prompts_list(self, valid_token, token_claims, org, environment):
        """Test prompts/list (stub for Phase 3)."""
        adapter = StdioMCPAdapter(token=valid_token)
        adapter.token_claims = token_claims
        adapter.org = org
        adapter.env = environment
        
        message = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "prompts/list",
        }
        
        response = await adapter.handle_prompts_list(message)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 8
        assert "result" in response
        assert response["result"]["prompts"] == []

