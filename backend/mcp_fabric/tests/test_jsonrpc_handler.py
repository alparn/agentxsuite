from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import mcp_fabric.jsonrpc as jsonrpc_module
from mcp_fabric.jsonrpc import MCPJsonRpcContext, MCPJsonRpcHandler


async def _call_sync(func, *args, **kwargs):
    return func(*args, **kwargs)


def _sync_to_async(func):
    async def wrapper(*args, **kwargs):
        return await _call_sync(func, *args, **kwargs)

    return wrapper


def test_tools_call_maps_mcp_name_arguments_to_execution_service(monkeypatch):
    org = SimpleNamespace(id="org-id", name="Org")
    env = SimpleNamespace(id="env-id", name="Env")
    claims = {"_resolved_agent_id": "agent-id", "jti": "jti-1"}
    handler = MCPJsonRpcHandler(
        MCPJsonRpcContext(organization=org, environment=env, token_claims=claims)
    )
    execute_tool_run = Mock(
        return_value={
            "content": [{"type": "text", "text": "ok"}],
            "isError": False,
        },
    )
    monkeypatch.setattr(jsonrpc_module, "execute_tool_run", execute_tool_run)
    monkeypatch.setattr(jsonrpc_module, "sync_to_async", lambda f: _sync_to_async(f))

    response = asyncio.run(
        handler.handle_tool_call(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "search_docs",
                    "arguments": {"query": "mcp"},
                },
            }
        )
    )

    assert response["result"]["isError"] is False
    execute_tool_run.assert_called_once()
    call_kwargs = execute_tool_run.call_args.kwargs
    assert call_kwargs["organization"] == org
    assert call_kwargs["environment"] == env
    assert call_kwargs["tool_identifier"] == "search_docs"
    assert call_kwargs["agent_identifier"] is None
    assert call_kwargs["input_data"] == {"query": "mcp"}


def test_tools_call_rejects_non_object_arguments():
    handler = MCPJsonRpcHandler(
        MCPJsonRpcContext(
            organization=SimpleNamespace(),
            environment=SimpleNamespace(),
            token_claims={},
        )
    )

    response = asyncio.run(
        handler.handle_tool_call(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "search_docs", "arguments": "bad"},
            }
        )
    )

    assert response["error"]["code"] == -32602
    assert "'arguments' must be an object" in response["error"]["data"]
