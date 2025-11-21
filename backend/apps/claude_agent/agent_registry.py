"""
Tool registry for Claude Agent SDK.

This module defines the tools that will be exposed to Claude's hosted agents.
Each tool maps to AgentxSuite's internal MCP endpoints.
"""

from typing import Any

from anthropic import Anthropic


class AgentxSuiteToolRegistry:
    """Registry of tools available to Claude agents."""

    def __init__(self):
        """Initialize the tool registry."""
        self.tools = self._define_tools()

    def _define_tools(self) -> list[dict[str, Any]]:
        """
        Define tools that will be exposed to Claude agents.

        Each tool definition follows Claude's tool schema format and maps
        to AgentxSuite's internal MCP/tool execution endpoints.

        Returns:
            List of tool definitions
        """
        return [
            {
                "name": "list_available_tools",
                "description": (
                    "List all tools available in the current AgentxSuite environment. "
                    "Returns tool names, descriptions, and schemas."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "environment_id": {
                            "type": "string",
                            "description": "Optional environment ID to filter tools",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "execute_tool",
                "description": (
                    "Execute a tool from AgentxSuite's MCP server ecosystem. "
                    "This allows running any registered tool with appropriate inputs."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Name of the tool to execute",
                        },
                        "tool_input": {
                            "type": "object",
                            "description": "Input parameters for the tool (JSON object)",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Optional agent ID to execute as (defaults to Claude agent)",
                        },
                    },
                    "required": ["tool_name", "tool_input"],
                },
            },
            {
                "name": "get_agent_info",
                "description": (
                    "Get information about a specific agent in AgentxSuite, "
                    "including its capabilities, permissions, and configuration."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "ID of the agent to retrieve",
                        }
                    },
                    "required": ["agent_id"],
                },
            },
            {
                "name": "list_runs",
                "description": (
                    "List recent tool execution runs, including their status, "
                    "inputs, outputs, and performance metrics."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of runs to return (default: 10)",
                            "default": 10,
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Optional agent ID to filter runs",
                        },
                        "status": {
                            "type": "string",
                            "description": "Optional status filter (succeeded, failed, etc.)",
                        },
                    },
                    "required": [],
                },
            },
        ]

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Get all registered tools.

        Returns:
            List of tool definitions
        """
        return self.tools

    def get_tool_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Get a specific tool definition by name.

        Args:
            name: Name of the tool

        Returns:
            Tool definition or None if not found
        """
        for tool in self.tools:
            if tool["name"] == name:
                return tool
        return None

