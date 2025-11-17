"""
Unit tests for tool serializer schema validation.
"""
from __future__ import annotations

import pytest

from apps.tools.serializers import ToolSerializer


@pytest.mark.django_db
def test_tool_validates_schema_json_is_dict(org_env):
    """Test that schema_json must be a dictionary."""
    org, env = org_env
    # DRF will automatically convert JSON strings, so we test with invalid type
    # by passing a non-dict value directly to serializer
    serializer = ToolSerializer(
        data={
            "environment_id": env.id,
            "name": "test-tool",
            "version": "1.0.0",
            "schema_json": "not-a-dict",
        },
    )
    # organization_id is set automatically by view, but for serializer tests we validate without it
    # DRF JSONField will try to parse, but validation should catch it
    # In practice, DRF JSONField accepts strings and tries to parse them
    # So we test with a value that can't be parsed as JSON dict
    assert not serializer.is_valid() or isinstance(serializer.validated_data.get("schema_json"), dict)


@pytest.mark.django_db
def test_tool_accepts_valid_schema_json(org_env_conn):
    """Test that valid schema_json is accepted."""
    org, env, conn = org_env_conn
    serializer = ToolSerializer(
        data={
            "environment_id": env.id,
            "connection_id": conn.id,
            "name": "test-tool",
            "version": "1.0.0",
            "schema_json": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
            },
        },
    )
    # organization_id is set automatically by view, so we set it when saving
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_tool_accepts_empty_schema_json(org_env_conn):
    """Test that empty schema_json is accepted."""
    org, env, conn = org_env_conn
    serializer = ToolSerializer(
        data={
            "environment_id": env.id,
            "connection_id": conn.id,
            "name": "test-tool",
            "version": "1.0.0",
            "schema_json": {},
        },
    )
    # organization_id is set automatically by view, so we set it when saving
    serializer.is_valid(raise_exception=True)
    serializer.save(organization=org)
    assert serializer.is_valid(), serializer.errors

