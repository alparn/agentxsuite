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

    This includes:
    - Regular tools from the Tool model
    - System tools (agentxsuite_*) that allow agents to manage AgentxSuite itself

    Args:
        mcp: fastmcp MCPServer instance to register tools with
        org: Organization instance
        env: Environment instance
    """
    # Register regular tools
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
    
    # Register system tools
    register_system_tools_for_org_env(mcp, org=org, env=env)


def register_system_tools_for_org_env(
    mcp: "MCPServer",
    *,
    org: "Organization",
    env: "Environment",
) -> None:
    """
    Register system tools for an organization/environment.
    
    System tools allow agents to manage AgentxSuite itself.
    
    Args:
        mcp: fastmcp MCPServer instance to register tools with
        org: Organization instance
        env: Environment instance
    """
    from apps.system_tools.tools import SYSTEM_TOOLS
    from apps.system_tools.services import TOOL_HANDLERS
    
    for tool_def in SYSTEM_TOOLS:
        tool_name = tool_def["name"]
        handler_func = TOOL_HANDLERS.get(tool_name)
        
        if not handler_func:
            logger.warning(
                f"No handler found for system tool: {tool_name}",
                extra={
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                },
            )
            continue
        
        schema = tool_def["schema"]
        schema_props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        param_names = list(schema_props.keys())
        
        def create_system_handler(
            _def=tool_def,
            _handler=handler_func,
            _org=org,
            _env=env,
        ):
            # Build parameter string including metadata params (will be filtered out)
            all_params = param_names + ["_token_agent_id", "_jti", "_client_ip", "_request_id"]
            params_str = ", ".join([f"{name}: Any = None" for name in all_params])
            
            if param_names:
                body_lines = [
                    "payload = {}",
                    "# Extract metadata params from function parameters",
                    "token_agent_id = _token_agent_id if '_token_agent_id' in locals() else None",
                    "jti = _jti if '_jti' in locals() else None",
                    "client_ip = _client_ip if '_client_ip' in locals() else None",
                    "request_id = _request_id if '_request_id' in locals() else None",
                ]
                # Only add schema-defined parameters to payload
                for name in param_names:
                    body_lines.append(f"if {name} is not None: payload['{name}'] = {name}")
                body_lines.extend([
                    f"payload['organization_id'] = '{_org.id}'",
                    f"payload['environment_id'] = '{_env.id}'",
                    f"from apps.system_tools.services import run_system_tool_with_audit, TOOL_HANDLERS",
                    f"return run_system_tool_with_audit(",
                    f"    tool_name='{tool_name}',",
                    f"    handler=TOOL_HANDLERS['{tool_name}'],",
                    f"    payload=payload,",
                    f"    organization_id='{_org.id}',",
                    f"    environment_id='{_env.id}',",
                    f"    token_agent_id=token_agent_id,",
                    f"    jti=jti,",
                    f"    client_ip=client_ip,",
                    f"    request_id=request_id,",
                    f")",
                ])
                body_str = "\n    ".join(body_lines)
                func_code = f"def _system_handler({params_str}) -> dict:\n    {body_str}"
            else:
                # No parameters - still accept metadata params
                func_code = f"""def _system_handler(_token_agent_id: Any = None, _jti: Any = None, _client_ip: Any = None, _request_id: Any = None) -> dict:
    payload = {{}}
    payload['organization_id'] = '{_org.id}'
    payload['environment_id'] = '{_env.id}'
    from apps.system_tools.services import run_system_tool_with_audit, TOOL_HANDLERS
    return run_system_tool_with_audit(
        tool_name='{tool_name}',
        handler=TOOL_HANDLERS['{tool_name}'],
        payload=payload,
        organization_id='{_org.id}',
        environment_id='{_env.id}',
        token_agent_id=_token_agent_id,
        jti=_jti,
        client_ip=_client_ip,
        request_id=_request_id,
    )"""
            
            namespace = {"Any": Any, "TOOL_HANDLERS": _handler}
            exec(func_code, namespace)
            handler = namespace["_system_handler"]
            handler.__name__ = _def["name"]
            handler.__doc__ = _def["description"]
            return handler
        
        try:
            handler = create_system_handler()
            registered_tool = mcp.tool(
                name=tool_name,
                description=tool_def["description"],
            )(handler)
            logger.info(
                f"Registered system tool '{tool_name}' for {org.name}/{env.name}",
                extra={
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                    "tool_name": tool_name,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to register system tool '{tool_name}': {e}",
                extra={
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                    "tool_name": tool_name,
                },
                exc_info=True,
            )

