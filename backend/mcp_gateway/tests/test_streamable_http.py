from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import mcp_gateway.main as gateway_module
from mcp_gateway.main import app


class FakeHandler:
    def __init__(self):
        self.initialized = False
        self.context = SimpleNamespace(token_claims={"_gateway_session_key": "test-session"})

    async def handle_message(self, message):
        if message.get("method") == "initialize":
            self.initialized = True
        if message.get("id") is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"method": message["method"]},
        }


def test_streamable_http_post_returns_jsonrpc_response(monkeypatch):
    async def validated_claims(_request):
        return {"org_id": "org-id", "env_id": "env-id", "_resolved_agent_id": "agent-id"}

    async def build_handler(_claims):
        return FakeHandler()

    monkeypatch.setattr(gateway_module, "_validated_claims_from_request", validated_claims)
    monkeypatch.setattr(gateway_module, "_build_handler", build_handler)

    client = TestClient(app)
    response = client.post(
        "/.well-known/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"method": "tools/list"},
    }


def test_streamable_http_post_returns_accepted_for_notifications(monkeypatch):
    async def validated_claims(_request):
        return {"org_id": "org-id", "env_id": "env-id", "_resolved_agent_id": "agent-id"}

    async def build_handler(_claims):
        return FakeHandler()

    monkeypatch.setattr(gateway_module, "_validated_claims_from_request", validated_claims)
    monkeypatch.setattr(gateway_module, "_build_handler", build_handler)

    client = TestClient(app)
    response = client.post(
        "/.well-known/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 202
    assert response.content == b""


def test_streamable_http_persists_initialized_state(monkeypatch):
    gateway_module.cache.delete("test-session")

    async def validated_claims(_request):
        return {
            "org_id": "org-id",
            "env_id": "env-id",
            "_resolved_agent_id": "agent-id",
            "_gateway_session_key": "test-session",
        }

    async def build_handler(_claims):
        return FakeHandler()

    monkeypatch.setattr(gateway_module, "_validated_claims_from_request", validated_claims)
    monkeypatch.setattr(gateway_module, "_build_handler", build_handler)

    client = TestClient(app)
    response = client.post(
        "/.well-known/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert gateway_module.cache.get("test-session") == {"initialized": True}
