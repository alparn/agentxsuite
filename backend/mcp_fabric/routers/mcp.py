"""
MCP-compatible router endpoints using fastmcp.
"""
from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async
from fastapi import APIRouter, Depends, HTTPException, Path
from fastmcp.server.server import FastMCP as MCPServer

from mcp_fabric.deps import create_token_validator
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception
from mcp_fabric.registry import register_tools_for_org_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/{org_id}/{env_id}/.well-known/mcp", tags=["mcp"])


def _resolve_org_env(org_id: str, env_id: str) -> tuple:
    """
    Resolve organization and environment by ID.

    Args:
        org_id: Organization UUID string
        env_id: Environment UUID string

    Returns:
        Tuple of (Organization, Environment) instances

    Raises:
        HTTPException: 404 if organization or environment not found
    """
    from apps.tenants.models import Environment, Organization

    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ORGANIZATION_NOT_FOUND,
            f"Organization {org_id} not found",
            404,
        )

    try:
        env = Environment.objects.get(id=env_id, organization=org)
    except Environment.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ENVIRONMENT_NOT_FOUND,
            f"Environment {env_id} not found or doesn't belong to organization",
            404,
        )

    return org, env


@router.get("/manifest.json")
async def manifest(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:manifest"])
    ),
) -> dict:
    """
    Get MCP manifest for organization/environment.

    Requires scope: mcp:manifest

    Returns:
        MCP manifest dictionary
    """
    org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

    # Create a fresh MCPServer instance per request (lightweight)
    mcp = MCPServer(name=f"AgentxSuite MCP - {org.name}/{env.name}")
    await sync_to_async(register_tools_for_org_env)(mcp, org=org, env=env)

    # fastmcp provides manifest as dict
    return mcp.get_manifest()


@router.get("/tools")
async def tools(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:tools"])
    ),
) -> list:
    """
    Get list of available tools for organization/environment.

    Requires scope: mcp:tools

    Returns:
        List of MCP-compatible tool definitions
    """
    org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

    mcp = MCPServer(name=f"AgentxSuite MCP - {org.name}/{env.name}")
    await sync_to_async(register_tools_for_org_env)(mcp, org=org, env=env)

    # FastMCP.get_tools() is async and returns a dict of FunctionTool objects
    tools_dict = await mcp.get_tools()
    if tools_dict and isinstance(tools_dict, dict):
        # Convert FunctionTool objects to MCP-compatible format
        tools_list = []
        for tool in tools_dict.values():
            # FunctionTool has: name, description, parameters (JSON Schema)
            tool_dict = {
                "name": tool.name if hasattr(tool, "name") else str(tool),
                "description": getattr(tool, "description", ""),
                "inputSchema": getattr(tool, "parameters", {}),
            }
            tools_list.append(tool_dict)
        return tools_list
    return []


@router.post("/run")
async def run(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    payload: dict = None,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:run"])
    ),
) -> dict:
    """
    Execute a tool via MCP run endpoint.

    Requires scope: mcp:run

    Payload format (supports both):
        {
            "tool": "tool_name",  # or "name"
            "input": {...}         # or "arguments"
        }

    Returns:
        Tool execution result dictionary

    Raises:
        HTTPException: 400 if tool name missing, 404 if tool not found
    """
    if payload is None:
        payload = {}

    org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

    mcp = MCPServer(name=f"AgentxSuite MCP - {org.name}/{env.name}")
    await sync_to_async(register_tools_for_org_env)(mcp, org=org, env=env)

    # Support both formats: {"tool": "...", "input": {...}} and {"name": "...", "arguments": {...}}
    tool_name = payload.get("tool") or payload.get("name")
    input_args = payload.get("input") or payload.get("arguments") or {}

    if not tool_name:
        raise raise_mcp_http_exception(
            ErrorCodes.MISSING_TOOL_NAME,
            "Missing tool name in payload",
            400,
        )

    try:
        # FastMCP doesn't have run_tool() - we need to get the tool and call its function
        tools_dict = await mcp.get_tools()

        if tool_name not in tools_dict:
            raise raise_mcp_http_exception(
                ErrorCodes.TOOL_NOT_FOUND,
                f"Tool '{tool_name}' not found",
                404,
            )

        tool_obj = tools_dict[tool_name]

        # Get the function from the tool object
        if not hasattr(tool_obj, "fn"):
            raise raise_mcp_http_exception(
                ErrorCodes.EXECUTION_FAILED,
                f"Tool '{tool_name}' has no executable function",
                500,
            )

        # Call the tool function with input arguments
        # Tool functions are synchronous (they use Django ORM), so we wrap them
        tool_function = tool_obj.fn

        # Execute synchronous function in thread pool
        # Handle both parameterized and parameterless functions
        import inspect

        sig = inspect.signature(tool_function)
        if len(sig.parameters) == 0:
            # Function has no parameters, call without arguments
            result = await sync_to_async(tool_function)()
        else:
            # Function has parameters, pass input_args
            result = await sync_to_async(tool_function)(**input_args)

        # Return unified response
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Error running tool '{tool_name}': {e}",
            extra={
                "org_id": str(org_id),
                "env_id": str(env_id),
                "tool_name": tool_name,
                "input_args": str(input_args),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        # Return error response instead of raising HTTPException
        # This matches the adapter's error format
        from mcp_fabric.errors import mcp_error_response

        return mcp_error_response(
            ErrorCodes.EXECUTION_FAILED,
            f"Tool execution failed: {str(e)}",
            500,
        )
