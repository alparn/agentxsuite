"""
Tool handlers for Claude Agent SDK.

This module implements the actual logic for each tool exposed to Claude agents.
Each handler calls AgentxSuite's internal MCP/API endpoints.
"""

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""

    pass


class AgentxSuiteToolHandlers:
    """Handler class for executing tools via AgentxSuite's internal APIs."""

    def __init__(self, organization_id: str, environment_id: str, auth_token: str):
        """
        Initialize tool handlers.

        Args:
            organization_id: Organization ID for API requests
            environment_id: Environment ID for API requests
            auth_token: Authentication token for API requests
        """
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.auth_token = auth_token
        self.base_url = getattr(settings, "AGENTXSUITE_API_BASE_URL", "http://localhost:8000")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Token {self.auth_token}"},
            timeout=30.0,
        )

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    async def list_available_tools(self, environment_id: str | None = None) -> dict[str, Any]:
        """
        List all available tools in the environment.

        Args:
            environment_id: Optional environment ID override

        Returns:
            Dictionary containing tools list and metadata
        """
        env_id = environment_id or self.environment_id

        try:
            response = self.client.get(f"/api/v1/orgs/{self.organization_id}/tools/", params={"environment": env_id})
            response.raise_for_status()

            tools = response.json()
            return {"success": True, "tools": tools, "count": len(tools) if isinstance(tools, list) else 0}

        except httpx.HTTPError as e:
            logger.error(f"Failed to list tools: {e}")
            raise ToolExecutionError(f"Failed to list tools: {str(e)}")

    async def execute_tool(self, tool_name: str, tool_input: dict[str, Any], agent_id: str | None = None) -> dict[str, Any]:
        """
        Execute a tool via AgentxSuite's run endpoint.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            agent_id: Optional agent ID to execute as

        Returns:
            Tool execution result
        """
        try:
            payload = {
                "tool": tool_name,
                "input": tool_input,
                "environment": self.environment_id,
            }

            if agent_id:
                payload["agent"] = agent_id

            response = self.client.post(f"/api/v1/orgs/{self.organization_id}/runs/execute/", json=payload)

            response.raise_for_status()

            result = response.json()
            return {"success": True, "result": result}

        except httpx.HTTPError as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            error_detail = e.response.text if hasattr(e, "response") else str(e)
            raise ToolExecutionError(f"Failed to execute tool {tool_name}: {error_detail}")

    async def get_agent_info(self, agent_id: str) -> dict[str, Any]:
        """
        Get information about a specific agent.

        Args:
            agent_id: ID of the agent to retrieve

        Returns:
            Agent information
        """
        try:
            response = self.client.get(f"/api/v1/orgs/{self.organization_id}/agents/{agent_id}/")
            response.raise_for_status()

            agent = response.json()
            return {"success": True, "agent": agent}

        except httpx.HTTPError as e:
            logger.error(f"Failed to get agent info for {agent_id}: {e}")
            raise ToolExecutionError(f"Failed to get agent info: {str(e)}")

    async def list_runs(
        self, limit: int = 10, agent_id: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        """
        List recent tool execution runs.

        Args:
            limit: Maximum number of runs to return
            agent_id: Optional agent ID filter
            status: Optional status filter

        Returns:
            List of runs with metadata
        """
        try:
            params = {"limit": limit}
            if agent_id:
                params["agent"] = agent_id
            if status:
                params["status"] = status

            response = self.client.get(f"/api/v1/orgs/{self.organization_id}/runs/", params=params)

            response.raise_for_status()

            runs = response.json()
            return {"success": True, "runs": runs, "count": len(runs) if isinstance(runs, list) else 0}

        except httpx.HTTPError as e:
            logger.error(f"Failed to list runs: {e}")
            raise ToolExecutionError(f"Failed to list runs: {str(e)}")

    async def handle_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Route tool calls to appropriate handlers.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool execution result
        """
        handlers = {
            "list_available_tools": self.list_available_tools,
            "execute_tool": self.execute_tool,
            "get_agent_info": self.get_agent_info,
            "list_runs": self.list_runs,
        }

        handler = handlers.get(tool_name)
        if not handler:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")

        return await handler(**tool_input)

