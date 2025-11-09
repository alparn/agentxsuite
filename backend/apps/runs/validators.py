"""
Validators for run input validation.
"""
from __future__ import annotations

import json

import jsonschema
from jsonschema import ValidationError

from apps.tools.models import Tool


def validate_input_json(tool: Tool, input_json: dict) -> None:
    """
    Validate input_json against tool.schema_json using JSONSchema.

    Args:
        tool: Tool instance with schema_json
        input_json: Input data to validate

    Raises:
        ValidationError: If input does not match schema
        ValueError: If schema_json is invalid
    """
    schema = tool.schema_json

    if not schema:
        # Empty schema means no validation required
        return

    try:
        jsonschema.validate(instance=input_json, schema=schema)
    except ValidationError as e:
        raise ValueError(f"Input validation failed: {e.message}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid schema_json format: {e}") from e

