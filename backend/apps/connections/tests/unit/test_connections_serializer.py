"""
Unit tests for connection serializer validation.
"""
from __future__ import annotations

import pytest

from apps.connections.serializers import ConnectionSerializer


@pytest.mark.django_db
def test_connection_requires_secret_ref_for_bearer(org_env):
    """Test that bearer auth requires secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "bearer",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "secret_ref" in serializer.errors


@pytest.mark.django_db
def test_connection_requires_secret_ref_for_basic(org_env):
    """Test that basic auth requires secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "basic",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "secret_ref" in serializer.errors


@pytest.mark.django_db
def test_connection_allows_none_auth_without_secret_ref(org_env):
    """Test that none auth doesn't require secret_ref."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "none",
        },
    )
    # organization_id is set automatically by view, so we set it when saving
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org)
    # Should be valid (secret_ref not required for none)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_connection_validates_auth_method_choices(org_env):
    """Test that invalid auth_method is rejected."""
    org, env = org_env
    serializer = ConnectionSerializer(
        data={
            "environment_id": env.id,
            "name": "mcp",
            "endpoint": "https://example.com/mcp",
            "auth_method": "invalid",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    assert not serializer.is_valid()
    assert "auth_method" in serializer.errors


@pytest.mark.django_db
def test_connection_secret_ref_not_in_response(org_env):
    """Test that secret_ref is not exposed in serializer output."""
    org, env = org_env
    from apps.connections.models import Connection

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="bearer",
        secret_ref="secret-ref-123",
    )
    serializer = ConnectionSerializer(conn)
    data = serializer.data
    assert "secret_ref" not in data

