"""
Registry for dynamically registering Django tools with fastmcp MCPServer.
"""
from __future__ import annotations

import logging
import types
from typing import TYPE_CHECKING, Any

from apps.tools.models import Tool

if TYPE_CHECKING:
    from fastmcp.server.server import FastMCP as MCPServer
    from apps.tenants.models import Environment, Organization

logger = logging.getLogger(__name__)


def register_tools_for_org_env(
    mcp: "MCPServer",
    *,
    org: "Organization",
    env: "Environment",
) -> None:
    """
    Register all enabled tools for an organization/environment with fastmcp.

    Args:
        mcp: fastmcp MCPServer instance to register tools with
        org: Organization instance
        env: Environment instance
    """
    tools = Tool.objects.filter(
        organization=org, environment=env, enabled=True
    ).select_related("connection")

    for tool in tools:
        input_schema = getattr(tool, "schema_json", None) or {"type": "object"}
        description = input_schema.get("description") if isinstance(input_schema, dict) else None
        version = getattr(tool, "version", None) or "1.0.0"

        # FastMCP doesn't support **kwargs, so we need to create a function
        # with explicit parameters matching the schema
        # We'll create a function that accepts all schema properties as optional parameters
        schema_props = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
        
        def create_handler(_t: Tool = tool, _schema: dict = input_schema):
            # Create function code dynamically based on schema properties
            param_names = list(_schema.get("properties", {}).keys()) if isinstance(_schema, dict) else []
            
            # Build function signature: all parameters are optional with Any type
            if param_names:
                # Create parameter string for function signature
                params_str = ", ".join([f"{name}: Any = None" for name in param_names])
                # Create function body that collects parameters into payload
                body_lines = [
                    "payload = {}",
                ]
                # Add lines to collect non-None parameters
                for name in param_names:
                    body_lines.append(f"if {name} is not None: payload['{name}'] = {name}")
                body_lines.extend([
                    "agent_id = payload.pop('agent_id', None)",
                    "# Extract token_agent_id and audit metadata from payload (set by router)",
                    "token_agent_id = payload.pop('_token_agent_id', None)",
                    "jti = payload.pop('_jti', None)",
                    "client_ip = payload.pop('_client_ip', None)",
                    "request_id = payload.pop('_request_id', None)",
                    "from mcp_fabric.adapters import run_tool_via_agentxsuite",
                    "return run_tool_via_agentxsuite(tool=_t, payload=payload, agent_id=agent_id, token_agent_id=token_agent_id, jti=jti, client_ip=client_ip, request_id=request_id)",
                ])
                # Join with proper indentation (4 spaces)
                body_str = "\n    ".join(body_lines)
                func_code = f"def _handler({params_str}) -> dict:\n    {body_str}"
            else:
                # No parameters - empty function
                func_code = "def _handler() -> dict:\n    payload = {}\n    agent_id = payload.pop('agent_id', None)\n    token_agent_id = payload.pop('_token_agent_id', None)\n    jti = payload.pop('_jti', None)\n    client_ip = payload.pop('_client_ip', None)\n    request_id = payload.pop('_request_id', None)\n    from mcp_fabric.adapters import run_tool_via_agentxsuite\n    return run_tool_via_agentxsuite(tool=_t, payload=payload, agent_id=agent_id, token_agent_id=token_agent_id, jti=jti, client_ip=client_ip, request_id=request_id)"
            
            # Execute function code in local namespace
            namespace = {"_t": _t, "Any": Any}
            exec(func_code, namespace)
            handler = namespace["_handler"]
            handler.__name__ = _t.name
            handler.__doc__ = description or f"Tool: {_t.name}"
            return handler

        try:
            # Create handler function
            handler = create_handler()
            
            # Register tool - FastMCP will infer parameters from function signature
            # and use the schema properties for validation
            registered_tool = mcp.tool(
                name=tool.name,
                description=description or f"Tool: {tool.name}",
            )(handler)
            logger.debug(
                f"Registered tool '{tool.name}' for {org.name}/{env.name}",
                extra={
                    "tool_id": str(tool.id),
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to register tool '{tool.name}': {e}",
                extra={
                    "tool_id": str(tool.id),
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                },
                exc_info=True,
            )

