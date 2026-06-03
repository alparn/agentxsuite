"""
Registry for dynamically registering Django tools with fastmcp MCPServer.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings

from apps.tools.models import CuratedTool, Tool

if TYPE_CHECKING:
    from fastmcp.server.server import FastMCP as MCPServer

    from apps.tenants.models import Environment, Organization

logger = logging.getLogger(__name__)


def _tool_curation_enabled() -> bool:
    """Return whether curated tools should be exposed to MCP clients."""
    return bool(getattr(settings, "TOOL_CURATION_ENABLED", False))


def _agent_tool_mode() -> str:
    """Return the configured agent-facing tool exposure mode."""
    return getattr(settings, "AGENT_TOOL_MODE", "raw_only")


def _tool_definition(name: str, description: str | None, input_schema: dict) -> dict:
    """Build a MCP-compatible tool definition."""
    return {
        "name": name,
        "description": description or f"Tool: {name}",
        "inputSchema": input_schema or {"type": "object"},
    }


def get_tools_list_for_org_env(
    *,
    org: Organization,
    env: Environment,
) -> list[dict]:
    """
    Get list of available tools for organization/environment in MCP-compatible format.
    
    This function directly queries the database and returns tools in MCP format,
    without requiring FastMCP. Used by sync API and other internal services.
    
    Args:
        org: Organization instance
        env: Environment instance
    
    Returns:
        List of tool definitions in MCP-compatible format:
        [
            {
                "name": "tool_name",
                "description": "...",
                "inputSchema": {...}
            },
            ...
        ]
    """
    tools_list = []
    
    if _tool_curation_enabled() and _agent_tool_mode() != "raw_only":
        curated_tools = CuratedTool.objects.filter(
            organization=org,
            environment=env,
            enabled=True,
        ).select_related("connection")

        for tool in curated_tools:
            tools_list.append(
                _tool_definition(tool.name, tool.description, tool.schema_json)
            )

    if not _tool_curation_enabled() or _agent_tool_mode() == "raw_only":
        raw_tools = Tool.objects.filter(
            organization=org, environment=env, enabled=True
        ).select_related("connection")
    elif _agent_tool_mode() == "curated_and_raw":
        raw_tools = Tool.objects.filter(
            organization=org,
            environment=env,
            enabled=True,
            is_agent_visible=True,
        ).select_related("connection")
    else:
        raw_tools = Tool.objects.none()

    for tool in raw_tools:
        input_schema = getattr(tool, "schema_json", None) or {"type": "object"}
        description = input_schema.get("description") if isinstance(input_schema, dict) else None
        tools_list.append(_tool_definition(tool.name, description, input_schema))
    
    # Add system tools
    from apps.system_tools.tools import SYSTEM_TOOLS
    
    for tool_def in SYSTEM_TOOLS:
        tool_dict = {
            "name": tool_def["name"],
            "description": tool_def["description"],
            "inputSchema": tool_def["schema"],
        }
        tools_list.append(tool_dict)
    
    return tools_list


def register_tools_for_org_env(
    mcp: MCPServer,
    *,
    org: Organization,
    env: Environment,
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
    tools = _get_agent_executable_tools(org=org, env=env)

    for tool in tools:
        input_schema = getattr(tool, "schema_json", None) or {"type": "object"}
        description = input_schema.get("description") if isinstance(input_schema, dict) else None

        # FastMCP doesn't support **kwargs, so we need to create a function
        # with explicit parameters matching the schema
        # We'll create a function that accepts all schema properties as optional parameters

        def create_handler(
            _t: Tool | CuratedTool = tool,
            _schema: dict = input_schema,
            _description: str | None = description,
        ):
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
                    "from apps.runs.services import ExecutionContext, execute_tool_run",
                    "return execute_tool_run(organization=_t.organization, environment=_t.environment, tool_identifier=str(_t.id), agent_identifier=agent_id, input_data=payload, context=ExecutionContext(token_agent_id=token_agent_id, jti=jti, client_ip=client_ip, request_id=request_id))",
                ])
                # Join with proper indentation (4 spaces)
                body_str = "\n    ".join(body_lines)
                func_code = f"def _handler({params_str}) -> dict:\n    {body_str}"
            else:
                # No parameters - empty function
                func_code = "def _handler() -> dict:\n    payload = {}\n    agent_id = payload.pop('agent_id', None)\n    token_agent_id = payload.pop('_token_agent_id', None)\n    jti = payload.pop('_jti', None)\n    client_ip = payload.pop('_client_ip', None)\n    request_id = payload.pop('_request_id', None)\n    from apps.runs.services import ExecutionContext, execute_tool_run\n    return execute_tool_run(organization=_t.organization, environment=_t.environment, tool_identifier=str(_t.id), agent_identifier=agent_id, input_data=payload, context=ExecutionContext(token_agent_id=token_agent_id, jti=jti, client_ip=client_ip, request_id=request_id))"
            
            # Execute function code in local namespace
            namespace = {"_t": _t, "Any": Any}
            exec(func_code, namespace)
            handler = namespace["_handler"]
            handler.__name__ = _t.name
            handler.__doc__ = _description or f"Tool: {_t.name}"
            return handler

        try:
            # Create handler function
            handler = create_handler()
            
            # Register tool - FastMCP will infer parameters from function signature
            # and use the schema properties for validation
            mcp.tool(
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
    mcp: MCPServer,
    *,
    org: Organization,
    env: Environment,
) -> None:
    """
    Register system tools for an organization/environment.
    
    System tools allow agents to manage AgentxSuite itself.
    
    Args:
        mcp: fastmcp MCPServer instance to register tools with
        org: Organization instance
        env: Environment instance
    """
    from apps.system_tools.services import TOOL_HANDLERS
    from apps.system_tools.tools import SYSTEM_TOOLS
    
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
            _param_names=param_names,
            _tool_name=tool_name,
        ):
            # Build parameter string including metadata params (will be filtered out)
            all_params = _param_names + ["_token_agent_id", "_jti", "_client_ip", "_request_id"]
            params_str = ", ".join([f"{name}: Any = None" for name in all_params])
            
            if _param_names:
                body_lines = [
                    "payload = {}",
                    "# Extract metadata params from function parameters",
                    "token_agent_id = _token_agent_id if '_token_agent_id' in locals() else None",
                    "jti = _jti if '_jti' in locals() else None",
                    "client_ip = _client_ip if '_client_ip' in locals() else None",
                    "request_id = _request_id if '_request_id' in locals() else None",
                ]
                # Only add schema-defined parameters to payload
                for name in _param_names:
                    body_lines.append(f"if {name} is not None: payload['{name}'] = {name}")
                body_lines.extend([
                    f"payload['organization_id'] = '{_org.id}'",
                    f"payload['environment_id'] = '{_env.id}'",
                    "from apps.system_tools.services import run_system_tool_with_audit, TOOL_HANDLERS",
                    "return run_system_tool_with_audit(",
                    f"    tool_name='{_tool_name}',",
                    f"    handler=TOOL_HANDLERS['{_tool_name}'],",
                    "    payload=payload,",
                    f"    organization_id='{_org.id}',",
                    f"    environment_id='{_env.id}',",
                    "    token_agent_id=token_agent_id,",
                    "    jti=jti,",
                    "    client_ip=client_ip,",
                    "    request_id=request_id,",
                    ")",
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
        tool_name='{_tool_name}',
        handler=TOOL_HANDLERS['{_tool_name}'],
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
            mcp.tool(
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


def _get_agent_executable_tools(*, org: Organization, env: Environment):
    """Return raw and/or curated tool objects that should be registered for agents."""
    if _tool_curation_enabled() and _agent_tool_mode() != "raw_only":
        curated_tools = list(
            CuratedTool.objects.filter(
                organization=org,
                environment=env,
                enabled=True,
            ).select_related("connection")
        )
    else:
        curated_tools = []

    if not _tool_curation_enabled() or _agent_tool_mode() == "raw_only":
        raw_tools = list(
            Tool.objects.filter(
                organization=org,
                environment=env,
                enabled=True,
            ).select_related("connection")
        )
    elif _agent_tool_mode() == "curated_and_raw":
        raw_tools = list(
            Tool.objects.filter(
                organization=org,
                environment=env,
                enabled=True,
                is_agent_visible=True,
            ).select_related("connection")
        )
    else:
        raw_tools = []

    return [*curated_tools, *raw_tools]
