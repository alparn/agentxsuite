"""MCP Gateway Service - Streamable HTTP entrypoint for MCP clients."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

import django
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from mcp_fabric.agent_resolver import resolve_agent_from_token_claims
from mcp_fabric.deps import get_validated_token, get_www_authenticate_header
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception
from mcp_fabric.jsonrpc import MCPJsonRpcContext, MCPJsonRpcHandler
from mcp_fabric.settings import MCP_CANONICAL_URI

logger = logging.getLogger(__name__)

GATEWAY_STATE_CACHE_PREFIX = "mcp_gateway:session:"
GATEWAY_STATE_TIMEOUT_SECONDS = getattr(settings, "MCP_GATEWAY_STATE_TIMEOUT_SECONDS", 3600)

app = FastAPI(
    title="AgentxSuite MCP Gateway",
    description="Streamable HTTP MCP gateway for AgentxSuite",
    version="1.0.0",
)


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise raise_mcp_http_exception(
            ErrorCodes.MISSING_TOKEN,
            "Missing Authorization header",
            status.HTTP_401_UNAUTHORIZED,
            headers=get_www_authenticate_header(),
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Authorization header must use Bearer token",
            status.HTTP_401_UNAUTHORIZED,
            headers=get_www_authenticate_header(),
        )

    return token


async def _validated_claims_from_request(request: Request) -> dict[str, Any]:
    """Validate bearer token and attach resolved agent/audit metadata."""
    token = _extract_bearer_token(request.headers.get("authorization"))
    resource = request.query_params.get("resource") or MCP_CANONICAL_URI
    claims = get_validated_token(token, required_scopes=["mcp:connect"], resource=resource)

    org_id = claims.get("org_id")
    env_id = claims.get("env_id")
    if not org_id or not env_id:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Token missing org_id or env_id claims",
            status.HTTP_403_FORBIDDEN,
        )

    resolved_agent = await sync_to_async(resolve_agent_from_token_claims)(
        claims,
        str(org_id),
        str(env_id),
    )
    if not resolved_agent:
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_NOT_FOUND,
            "Agent not found or access denied",
            status.HTTP_403_FORBIDDEN,
        )

    query_agent_id = request.query_params.get("agent_id")
    if query_agent_id and query_agent_id != str(resolved_agent.id):
        raise raise_mcp_http_exception(
            ErrorCodes.AGENT_SESSION_MISMATCH,
            "Agent cannot be changed during an MCP session",
            status.HTTP_403_FORBIDDEN,
        )

    client_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()

    claims["_resolved_agent_id"] = str(resolved_agent.id)
    claims["agent_id"] = str(resolved_agent.id)
    claims["_client_ip"] = client_ip
    claims["_request_id"] = request.headers.get("x-request-id") or str(uuid.uuid4())
    claims["_jti"] = claims.get("jti")
    claims["_gateway_session_key"] = _gateway_session_key(claims)
    return claims


async def _validated_claims_from_websocket(websocket: WebSocket) -> dict[str, Any]:
    token = _extract_bearer_token(websocket.headers.get("authorization"))
    claims = get_validated_token(token, required_scopes=["mcp:connect"], resource=MCP_CANONICAL_URI)

    org_id = claims.get("org_id")
    env_id = claims.get("env_id")
    if not org_id or not env_id:
        raise ValueError("Token missing org_id or env_id claims")

    resolved_agent = await sync_to_async(resolve_agent_from_token_claims)(
        claims,
        str(org_id),
        str(env_id),
    )
    if not resolved_agent:
        raise ValueError("Agent not found or access denied")

    claims["_resolved_agent_id"] = str(resolved_agent.id)
    claims["agent_id"] = str(resolved_agent.id)
    claims["_client_ip"] = websocket.client.host if websocket.client else None
    claims["_request_id"] = str(uuid.uuid4())
    claims["_jti"] = claims.get("jti")
    claims["_gateway_session_key"] = _gateway_session_key(claims)
    return claims


def _gateway_session_key(token_claims: dict[str, Any]) -> str:
    """Build a stable cache key for gateway session state."""
    session_id = (
        token_claims.get("jti")
        or token_claims.get("_resolved_agent_id")
        or token_claims.get("agent_id")
        or token_claims.get("sub")
        or str(uuid.uuid4())
    )
    return f"{GATEWAY_STATE_CACHE_PREFIX}{session_id}"


async def _load_gateway_state(session_key: str | None) -> dict[str, Any]:
    """Load gateway session state from the configured Django cache backend."""
    if not session_key:
        return {}
    state_data = await sync_to_async(cache.get)(session_key)
    return state_data if isinstance(state_data, dict) else {}


async def _save_gateway_state(handler: MCPJsonRpcHandler) -> None:
    """Persist lightweight handler state for multi-instance gateways."""
    session_key = handler.context.token_claims.get("_gateway_session_key")
    if not session_key:
        return

    await sync_to_async(cache.set)(
        session_key,
        {"initialized": handler.initialized},
        GATEWAY_STATE_TIMEOUT_SECONDS,
    )


async def _build_handler(token_claims: dict[str, Any]) -> MCPJsonRpcHandler:
    from apps.agents.models import Agent
    from apps.tenants.models import Environment, Organization

    org_id = token_claims.get("org_id")
    env_id = token_claims.get("env_id")
    agent_id = token_claims.get("_resolved_agent_id") or token_claims.get("agent_id")

    org = await sync_to_async(Organization.objects.get)(id=org_id)
    env = await sync_to_async(Environment.objects.get)(id=env_id, organization=org)
    agent = None
    if agent_id:
        agent = await sync_to_async(
            Agent.objects.filter(
                id=agent_id,
                organization=org,
                environment=env,
                enabled=True,
            ).first
        )()

    handler = MCPJsonRpcHandler(
        MCPJsonRpcContext(
            organization=org,
            environment=env,
            agent=agent,
            token_claims=token_claims,
            server_name=f"AgentxSuite MCP - {org.name}/{env.name}",
        )
    )
    state_data = await _load_gateway_state(token_claims.get("_gateway_session_key"))
    handler.initialized = bool(state_data.get("initialized", False))
    return handler


async def _handle_jsonrpc_payload(
    handler: MCPJsonRpcHandler,
    payload: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any] | list[dict[str, Any]] | None:
    if isinstance(payload, list):
        responses = []
        for message in payload:
            response = await handler.handle_message(message)
            await _save_gateway_state(handler)
            if response is not None:
                responses.append(response)
        return responses or None

    response = await handler.handle_message(payload)
    await _save_gateway_state(handler)
    return response


def _wants_event_stream(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept.lower()


@app.get("/.well-known/mcp")
async def mcp_endpoint_get(request: Request):
    """
    Streamable HTTP GET opens a server-to-client event stream.

    Non-SSE clients still receive a small discovery document for compatibility.
    """
    if _wants_event_stream(request):
        await _validated_claims_from_request(request)

        async def event_generator():
            while True:
                await asyncio.sleep(30)
                yield {"event": "ping", "data": "{}"}

        return EventSourceResponse(event_generator())

    return {
        "version": "1.0.0",
        "transports": {
            "streamable_http": {
                "url": "/.well-known/mcp",
            },
            "sse": {
                "url": "/.well-known/mcp/sse"
            },
            "websocket": {
                "url": "/.well-known/mcp/ws"
            }
        }
    }


@app.post("/.well-known/mcp")
async def mcp_streamable_http(request: Request):
    """
    Handle MCP JSON-RPC over Streamable HTTP.

    The gateway validates the bearer token server-side and executes
    tools/call directly via AgentxSuite's run service.
    """
    token_claims = await _validated_claims_from_request(request)
    payload = await request.json()
    handler = await _build_handler(token_claims)
    response_payload = await _handle_jsonrpc_payload(handler, payload)

    if response_payload is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)

    if _wants_event_stream(request):
        async def event_generator():
            yield {
                "event": "message",
                "data": json.dumps(response_payload),
            }

        return EventSourceResponse(event_generator())

    return JSONResponse(response_payload)


@app.get("/.well-known/mcp/sse")
async def mcp_sse(request: Request):
    """
    Legacy SSE endpoint for MCP clients that still use SSE + messages.
    """
    await _validated_claims_from_request(request)

    async def event_generator():
        base_url = str(request.base_url).rstrip("/")
        yield {
            "event": "endpoint",
            "data": f"{base_url}/.well-known/mcp/messages",
        }
        while True:
            await asyncio.sleep(30)
            yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())


@app.post("/.well-known/mcp/messages")
async def mcp_sse_messages(request: Request):
    """Handle JSON-RPC messages for legacy SSE clients."""
    return await mcp_streamable_http(request)


@app.websocket("/.well-known/mcp/ws")
async def mcp_websocket(websocket: WebSocket):
    """
    WebSocket compatibility endpoint using the same JSON-RPC handler.
    """
    try:
        token_claims = await _validated_claims_from_websocket(websocket)
        handler = await _build_handler(token_claims)
        await websocket.accept()

        while True:
            message = await websocket.receive_json()
            response = await _handle_jsonrpc_payload(handler, message)
            if response is not None:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail))
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mcp-gateway"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8091,  # Different port from FastMCP server
        log_level="info"
    )

