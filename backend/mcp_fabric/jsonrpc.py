"""
Shared JSON-RPC handling for AgentxSuite MCP transports.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async

from apps.agents.models import Agent
from apps.runs.services import ExecutionContext, execute_tool_run
from apps.tenants.models import Environment, Organization
from mcp_fabric.registry import get_tools_list_for_org_env

logger = logging.getLogger(__name__)


def normalize_mcp_tool_name(name: str) -> str:
    """Normalize tool names to the MCP-compatible pattern."""
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:64] or "unnamed_tool"


@dataclass
class MCPJsonRpcContext:
    """Tenant and token context resolved before handling JSON-RPC messages."""

    organization: Organization
    environment: Environment
    token_claims: dict[str, Any]
    agent: Agent | None = None
    server_name: str = "agentxsuite"


class MCPJsonRpcHandler:
    """Handle MCP JSON-RPC methods independent of the transport."""

    def __init__(self, context: MCPJsonRpcContext):
        self.context = context
        self.initialized = False

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Route a single JSON-RPC request or notification."""
        msg_id = message.get("id")
        method = message.get("method")

        if msg_id is None:
            logger.debug("Received MCP notification: %s", method)
            return None

        try:
            if method == "initialize":
                return await self.handle_initialize(message)
            if method == "tools/list":
                return await self.handle_tools_list(message)
            if method == "tools/call":
                return await self.handle_tool_call(message)
            if method == "resources/list":
                return self._success_response(msg_id, {"resources": []})
            if method == "prompts/list":
                return self._success_response(msg_id, {"prompts": []})

            return self._error_response(
                msg_id,
                -32601,
                "Method not found",
                f"Unknown method: {method}",
            )
        except Exception as exc:
            logger.error("Error handling MCP method %s", method, exc_info=True)
            return self._error_response(
                msg_id,
                -32603,
                "Internal error",
                str(exc),
            )

    async def handle_initialize(self, message: dict[str, Any]) -> dict[str, Any]:
        """Return server capabilities for MCP initialization."""
        msg_id = message.get("id")
        params = message.get("params", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")
        self.initialized = True

        return self._success_response(
            msg_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {
                    "name": self.context.server_name,
                    "version": "1.0.0",
                },
            },
        )

    async def handle_tools_list(self, message: dict[str, Any]) -> dict[str, Any]:
        """Return enabled tools for the resolved organization/environment."""
        msg_id = message.get("id")
        tools = await sync_to_async(get_tools_list_for_org_env)(
            org=self.context.organization,
            env=self.context.environment,
        )

        normalized_tools = []
        for tool in tools:
            original_name = tool.get("name", "")
            normalized_tool = {**tool, "name": self._normalize_tool_name(original_name)}
            if not normalized_tool.get("description"):
                normalized_tool["description"] = f"Tool: {original_name}"
            normalized_tools.append(normalized_tool)

        return self._success_response(msg_id, {"tools": normalized_tools})

    async def handle_tool_call(self, message: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool using MCP params `{name, arguments}`."""
        msg_id = message.get("id")
        params = message.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if not tool_name:
            return self._error_response(
                msg_id,
                -32602,
                "Invalid params",
                "Missing 'name' parameter",
            )

        if not isinstance(arguments, dict):
            return self._error_response(
                msg_id,
                -32602,
                "Invalid params",
                "'arguments' must be an object",
            )

        try:
            result = await sync_to_async(execute_tool_run)(
                organization=self.context.organization,
                environment=self.context.environment,
                tool_identifier=tool_name,
                agent_identifier=None,
                input_data=arguments,
                context=ExecutionContext.from_token_claims(self.context.token_claims),
            )
        except ValueError as exc:
            message_text = str(exc)
            if "not found" in message_text.lower():
                return self._error_response(msg_id, -32602, "Tool not found", message_text)

            return self._success_response(
                msg_id,
                {
                    "content": [{"type": "text", "text": message_text}],
                    "isError": True,
                },
            )

        return self._success_response(
            msg_id,
            {
                "content": self._content_from_execution_result(result),
                "isError": bool(result.get("isError")),
            },
        )

    def _content_from_execution_result(self, result: dict[str, Any]) -> list[dict[str, str]]:
        content = result.get("content")
        if isinstance(content, list):
            return content

        if "output" in result:
            return self._content_from_value(result["output"])
        if "result" in result:
            return self._content_from_value(result["result"])
        if result:
            return self._content_from_value(result)
        return []

    def _content_from_value(self, value: Any) -> list[dict[str, str]]:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, indent=2)
        return [{"type": "text", "text": text}]

    def _normalize_tool_name(self, name: str) -> str:
        return normalize_mcp_tool_name(name)

    def _success_response(self, msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    def _error_response(
        self,
        msg_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> dict[str, Any]:
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": error,
        }
