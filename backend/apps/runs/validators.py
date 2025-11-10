"""
Validators for run input validation.
"""
from __future__ import annotations

import json

import jsonschema
from jsonschema import ValidationError

from apps.tools.models import Tool


def _normalize_input_types(input_json: dict, schema: dict) -> dict:
    """
    Normalize input types based on schema expectations.
    
    Converts string numbers to numbers, string booleans to booleans, etc.
    This handles cases where HTTP/JSON inputs come as strings but schema expects specific types.
    
    Args:
        input_json: Input data dictionary
        schema: JSON Schema dictionary
        
    Returns:
        Normalized input dictionary
    """
    if not isinstance(schema, dict) or not isinstance(input_json, dict):
        return input_json
    
    normalized = {}
    properties = schema.get("properties", {})
    
    for key, value in input_json.items():
        if key not in properties:
            # Unknown property - keep as is
            normalized[key] = value
            continue
        
        prop_schema = properties[key]
        prop_type = prop_schema.get("type") if isinstance(prop_schema, dict) else None
        
        # Normalize based on expected type
        if prop_type == "number" and isinstance(value, str):
            try:
                # Try to convert string to number (int or float)
                if "." in value:
                    normalized[key] = float(value)
                else:
                    normalized[key] = int(value)
            except (ValueError, TypeError):
                # If conversion fails, keep original value (validation will catch it)
                normalized[key] = value
        elif prop_type == "integer" and isinstance(value, str):
            try:
                normalized[key] = int(value)
            except (ValueError, TypeError):
                normalized[key] = value
        elif prop_type == "boolean" and isinstance(value, str):
            # Convert string booleans
            if value.lower() in ("true", "1", "yes", "on"):
                normalized[key] = True
            elif value.lower() in ("false", "0", "no", "off", ""):
                normalized[key] = False
            else:
                normalized[key] = value
        else:
            # Keep original value
            normalized[key] = value
    
    return normalized


def validate_input_json(tool: Tool, input_json: dict) -> None:
    """
    Validate input_json against tool.schema_json using JSONSchema.

    Automatically normalizes input types (e.g., string numbers to numbers)
    before validation to handle HTTP/JSON input type mismatches.

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

    # Normalize input types based on schema
    normalized_input = _normalize_input_types(input_json, schema)

    try:
        jsonschema.validate(instance=normalized_input, schema=schema)
    except ValidationError as e:
        raise ValueError(f"Input validation failed: {e.message}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid schema_json format: {e}") from e

