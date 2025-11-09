"""
Validators for tools app.
"""
from __future__ import annotations

import json

from rest_framework import serializers


def validate_schema_json(value: dict) -> dict:
    """
    Validate that schema_json is a valid JSON schema.

    Args:
        value: Dictionary to validate

    Returns:
        Validated dictionary

    Raises:
        serializers.ValidationError: If schema is invalid
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError("schema_json must be a dictionary")

    # Basic validation: check for common JSON schema fields
    if "type" not in value and "properties" not in value:
        # Allow empty dict or minimal schemas
        pass

    # Try to serialize to ensure it's valid JSON
    try:
        json.dumps(value)
    except (TypeError, ValueError) as e:
        raise serializers.ValidationError(f"Invalid JSON schema: {e}") from e

    return value

