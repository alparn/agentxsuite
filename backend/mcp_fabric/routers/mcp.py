"""
MCP-compatible router endpoints using fastmcp.
"""
from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastmcp.server.server import FastMCP as MCPServer

from mcp_fabric.deps import create_token_validator
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception
from mcp_fabric.registry import register_tools_for_org_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/.well-known/mcp", tags=["mcp"])


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
    request: Request,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:manifest"])
    ),
) -> dict:
    """
    Get MCP manifest for organization/environment.

    Requires scope: mcp:manifest
    org_id/env_id are extracted from token claims (secure multi-tenant).

    Returns:
        MCP manifest dictionary
    """
    # Extract org_id/env_id from token claims
    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )
    
    org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

    # Create a fresh MCPServer instance per request (lightweight)
    mcp = MCPServer(name=f"AgentxSuite MCP - {org.name}/{env.name}")
    await sync_to_async(register_tools_for_org_env)(mcp, org=org, env=env)

    # fastmcp provides manifest as dict
    return mcp.get_manifest()


@router.get("/tools")
async def tools(
    request: Request,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:tools"])
    ),
) -> list:
    """
    Get list of available tools for organization/environment.

    Requires scope: mcp:tools
    org_id/env_id are extracted from token claims (secure multi-tenant).

    Returns:
        List of MCP-compatible tool definitions
    """
    # Extract org_id/env_id from token claims
    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )
    
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
    request: Request,
    payload: dict = None,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:run"])
    ),
) -> dict:
    """
    Execute a tool via MCP run endpoint - uses unified execution service.

    Requires scope: mcp:run
    org_id/env_id are extracted from token claims (secure multi-tenant).

    Payload format (supports both):
        {
            "tool": "tool_name",  # or "name"
            "input": {...}         # or "arguments"
        }

    Returns:
        MCP-compatible response dictionary

    Raises:
        HTTPException: 400 if tool name missing, 404 if tool not found
    """
    if payload is None:
        payload = {}

    # Extract org_id/env_id from token claims
    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )

    org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

    # Tool identifier - flexible from both formats
    tool_identifier = payload.get("name") or payload.get("tool")
    
    # Input data - flexible from both formats
    input_data = payload.get("arguments") or payload.get("input", {})
    
    if not tool_identifier:
        raise raise_mcp_http_exception(
            ErrorCodes.MISSING_TOOL_NAME,
            "Missing tool name in payload",
            400,
        )

    # Create context (with Token-Agent!)
    from apps.runs.services import ExecutionContext, execute_tool_run
    
    context = ExecutionContext.from_token_claims(token_claims)
    
    # IMPORTANT: No agent_identifier from Payload - Agent comes only from Token!
    
    try:
        # Execute via unified service
        result = await sync_to_async(execute_tool_run)(
            organization=org,
            environment=env,
            tool_identifier=tool_identifier,
            agent_identifier=None,  # NOT from Payload - only from Token!
            input_data=input_data,
            context=context,
        )
        
        # Response is already MCP-compatible
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        # Validation/Security Errors from execute_tool_run
        raise raise_mcp_http_exception(
            ErrorCodes.EXECUTION_FAILED,
            str(e),
            400,
        )
    except Exception as e:
        # Get context IDs for error response
        from libs.logging.context import get_context_ids
        
        context_ids = get_context_ids()
        trace_id = context_ids.get("trace_id")
        request_id = context_ids.get("request_id")
        run_id = context_ids.get("run_id")
        
        logger.error(
            f"Error running tool '{tool_identifier}': {e}",
            extra={
                "org_id": str(org_id),
                "env_id": str(env_id),
                "tool_identifier": tool_identifier,
                "input_data": str(input_data),
                "error_type": type(e).__name__,
                "trace_id": trace_id,
                "request_id": request_id,
                "run_id": run_id,
            },
            exc_info=True,
        )
        # Return error response instead of raising HTTPException
        # This matches the adapter's error format
        from mcp_fabric.errors import mcp_error_response

        error_extra = {}
        if trace_id:
            error_extra["trace_id"] = trace_id
        if request_id:
            error_extra["request_id"] = request_id
        if run_id:
            error_extra["run_id"] = run_id

        return mcp_error_response(
            ErrorCodes.EXECUTION_FAILED,
            f"Tool execution failed: {str(e)}",
            500,
            extra=error_extra,
        )


@router.get("/sse")
async def handle_sse(
    request: Request,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:connect"])
    ),
):
    """
    Handle MCP SSE connection.
    
    Requires scope: mcp:connect
    """
    from sse_starlette.sse import EventSourceResponse
    import asyncio
    
    # Extract org_id/env_id from token claims
    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )
    
    async def event_generator():
        # Send the endpoint for posting messages
        # Construct absolute URL for messages endpoint
        base_url = str(request.base_url).rstrip("/")
        # Handle both root and scoped routers
        if "mcp/" in request.url.path:
            # Scoped router: /mcp/{org}/{env}/.well-known/mcp/sse
            messages_url = f"{base_url}/mcp/{org_id}/{env_id}/.well-known/mcp/messages"
        else:
            # Root router: /.well-known/mcp/sse
            messages_url = f"{base_url}/.well-known/mcp/messages"
            
        yield {
            "event": "endpoint",
            "data": messages_url
        }
        
        # Keep connection open
        while True:
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.post("/messages")
async def handle_messages(
    request: Request,
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:connect"])
    ),
):
    """
    Handle MCP JSON-RPC messages.
    
    Requires scope: mcp:connect
    """
    import json
    
    # Extract org_id/env_id from token claims
    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )
        
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})
        
        org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))
        
        # Initialize MCP server
        mcp = MCPServer(name=f"AgentxSuite MCP - {org.name}/{env.name}")
        await sync_to_async(register_tools_for_org_env)(mcp, org=org, env=env)
        
        result = None
        error = None
        
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                    "resources": {"listChanged": False, "subscribe": False}
                },
                "serverInfo": {
                    "name": f"AgentxSuite MCP - {org.name}/{env.name}",
                    "version": "1.0.0"
                }
            }
            
        elif method == "notifications/initialized":
            # No response needed for notifications
            return Response(status_code=200)
            
        elif method == "tools/list":
            tools_dict = await mcp.get_tools()
            tools_list = []
            if tools_dict:
                for tool in tools_dict.values():
                    tools_list.append({
                        "name": tool.name if hasattr(tool, "name") else str(tool),
                        "description": getattr(tool, "description", ""),
                        "inputSchema": getattr(tool, "parameters", {}),
                    })
            result = {"tools": tools_list}
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # Execute tool using unified service
            from apps.runs.services import ExecutionContext, execute_tool_run
            context = ExecutionContext.from_token_claims(token_claims)
            
            try:
                exec_result = await sync_to_async(execute_tool_run)(
                    organization=org,
                    environment=env,
                    tool_identifier=tool_name,
                    agent_identifier=None,
                    input_data=tool_args,
                    context=context,
                )
                
                # Format result for MCP
                content = []
                if "content" in exec_result:
                    content = exec_result["content"]
                elif "result" in exec_result:
                    content = [{"type": "text", "text": str(exec_result["result"])}]
                    
                result = {
                    "content": content,
                    "isError": exec_result.get("isError", False)
                }
            except Exception as e:
                error = {
                    "code": -32603,
                    "message": str(e)
                }
                
        else:
            error = {
                "code": -32601,
                "message": f"Method {method} not found"
            }
            
        # Construct JSON-RPC response
        response_data = {
            "jsonrpc": "2.0",
            "id": msg_id
        }
        
        if error:
            response_data["error"] = error
        else:
            response_data["result"] = result
            
        return response_data
        
    except Exception as e:
        logger.error(f"Error handling MCP message: {e}", exc_info=True)
        return Response(status_code=500)
