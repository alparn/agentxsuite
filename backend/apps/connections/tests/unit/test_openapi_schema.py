"""Regression tests for OpenAPI schema exposure."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_openapi_schema_includes_connection_transport_fields(client) -> None:
    """The generated schema documents the expanded Connection API surface."""
    response = client.get("/api/schema/", HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    schema = response.json()
    connection_schema = schema["components"]["schemas"]["Connection"]
    properties = connection_schema["properties"]
    assert "transport" in properties
    assert "command" in properties
    assert "args" in properties
    assert "env_ref" not in properties
    assert "secret_ref" not in properties
