"""
System tools definitions for AgentxSuite self-management.
"""
from __future__ import annotations

SYSTEM_TOOLS = [
    {
        "name": "agentxsuite_list_agents",
        "description": "List all agents in the current organization/environment.",
        "schema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Only return enabled agents",
                },
                "mode": {
                    "type": "string",
                    "enum": ["runner", "caller"],
                    "description": "Filter by agent mode",
                },
            },
            "required": [],
        },
    },
    {
        "name": "agentxsuite_get_agent",
        "description": "Get details of a specific agent by ID or name.",
        "schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Agent UUID",
                },
                "agent_name": {
                    "type": "string",
                    "description": "Agent name (alternative to agent_id)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "agentxsuite_create_agent",
        "description": "Create a new agent in AgentxSuite.",
        "schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Agent name (must be unique per organization/environment)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["runner", "caller"],
                    "default": "runner",
                    "description": "Agent execution mode",
                },
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether the agent should be enabled",
                },
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "List of agent capabilities",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Tags for filtering and grouping",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "agentxsuite_list_connections",
        "description": "List all MCP server connections in the current organization/environment.",
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["unknown", "ok", "fail"],
                    "description": "Filter by connection status",
                },
            },
            "required": [],
        },
    },
    {
        "name": "agentxsuite_list_tools",
        "description": "List all available tools in the current organization/environment.",
        "schema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "default": True,
                    "description": "Only return enabled tools",
                },
                "connection_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Filter by connection ID",
                },
            },
            "required": [],
        },
    },
    {
        "name": "agentxsuite_list_runs",
        "description": "List recent runs (tool executions) in the current organization/environment.",
        "schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of runs to return",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "succeeded", "failed", "cancelled"],
                    "description": "Filter by run status",
                },
                "agent_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": "Filter by agent ID",
                },
            },
            "required": [],
        },
    },
]

