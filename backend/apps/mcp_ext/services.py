"""
Services for mcp_ext: Resource fetching and Prompt rendering.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx
import jsonschema
from django.conf import settings
from jinja2 import Environment, select_autoescape

from apps.agents.models import Agent
from apps.audit.services import log_security_event
from apps.mcp_ext.models import Prompt, Resource
from libs.secretstore import get_secretstore

logger = logging.getLogger(__name__)

# Jinja2 environment with safe defaults
jinja_env = Environment(
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Maximum content size (16KB)
MAX_CONTENT_SIZE = 16384


def _redact_secrets(content: str) -> str:
    """
    Redact potential secrets from content.

    Args:
        content: Content string to redact

    Returns:
        Redacted content string
    """
    # Common secret patterns
    patterns = [
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', r'\1: [REDACTED]'),
        (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', r'\1: [REDACTED]'),
        (r'(?i)(token|secret|bearer)\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', r'\1: [REDACTED]'),
        (r'Bearer\s+([a-zA-Z0-9_-]{20,})', 'Bearer [REDACTED]'),
    ]

    redacted = content
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)

    return redacted


def _truncate_content(content: str, max_size: int = MAX_CONTENT_SIZE) -> tuple[str, bool]:
    """
    Truncate content to maximum size.

    Args:
        content: Content string
        max_size: Maximum size in bytes

    Returns:
        Tuple of (truncated_content, was_truncated)
    """
    if len(content.encode("utf-8")) <= max_size:
        return content, False

    # Truncate to max_size bytes
    truncated = content.encode("utf-8")[:max_size].decode("utf-8", errors="ignore")
    return truncated + "\n... [TRUNCATED]", True


def fetch_resource(resource: Resource, agent: Agent | None = None) -> dict[str, Any] | str:
    """
    Fetch resource content based on type.

    Args:
        resource: Resource instance
        agent: Optional agent instance for audit logging

    Returns:
        Resource content as dict or string

    Raises:
        ValueError: If resource type is not supported or fetch fails
    """
    content = None

    if resource.type == "static":
        value = resource.config_json.get("value", "")
        if isinstance(value, str):
            content, truncated = _truncate_content(value)
            if truncated:
                logger.warning(
                    f"Resource '{resource.name}' content truncated",
                    extra={"resource_id": str(resource.id), "size": len(value)},
                )
        else:
            content = value

    elif resource.type == "http":
        url = resource.config_json.get("url")
        if not url:
            raise ValueError(f"Resource '{resource.name}' missing 'url' in config_json")

        headers = {}
        if resource.secret_ref:
            try:
                secretstore = get_secretstore()
                secret_value = secretstore.get_secret(resource.secret_ref, check_permissions=False)
                # Support common auth patterns
                auth_type = resource.config_json.get("auth_type", "bearer")
                if auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {secret_value}"
                elif auth_type == "api_key":
                    api_key_header = resource.config_json.get("api_key_header", "X-API-Key")
                    headers[api_key_header] = secret_value
            except Exception as e:
                logger.error(
                    f"Failed to retrieve secret for resource '{resource.name}': {e}",
                    extra={"resource_id": str(resource.id), "secret_ref": resource.secret_ref},
                )
                raise ValueError(f"Failed to retrieve secret for resource '{resource.name}'") from e

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                content = response.text

                # Redact and truncate
                content = _redact_secrets(content)
                content, truncated = _truncate_content(content)
                if truncated:
                    logger.warning(
                        f"Resource '{resource.name}' content truncated",
                        extra={"resource_id": str(resource.id), "url": url},
                    )
        except httpx.RequestError as e:
            logger.error(
                f"Failed to fetch HTTP resource '{resource.name}': {e}",
                extra={"resource_id": str(resource.id), "url": url},
            )
            raise ValueError(f"Failed to fetch HTTP resource '{resource.name}': {e}") from e

    elif resource.type == "sql":
        # SQL resource: Execute SQL query and return results
        query = resource.config_json.get("query")
        if not query:
            raise ValueError(f"Resource '{resource.name}' missing 'query' in config_json")

        # Get database connection from config_json or use default
        db_alias = resource.config_json.get("database", "default")

        try:
            from django.db import connections

            with connections[db_alias].cursor() as cursor:
                cursor.execute(query)
                columns = [col[0] for col in cursor.description] if cursor.description else []
                rows = cursor.fetchall()

                # Convert to JSON-serializable format
                if columns:
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    result = []

                # Limit results to prevent huge responses
                max_rows = resource.config_json.get("max_rows", 1000)
                if len(result) > max_rows:
                    result = result[:max_rows]
                    logger.warning(
                        f"SQL resource '{resource.name}' results truncated to {max_rows} rows",
                        extra={"resource_id": str(resource.id)},
                    )

                import json

                content = json.dumps(result, default=str)
                content, truncated = _truncate_content(content)
                if truncated:
                    logger.warning(
                        f"Resource '{resource.name}' content truncated",
                        extra={"resource_id": str(resource.id)},
                    )
                return content
        except Exception as e:
            logger.error(
                f"Failed to execute SQL for resource '{resource.name}': {e}",
                extra={"resource_id": str(resource.id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to execute SQL query: {e}") from e

    elif resource.type == "s3":
        # S3 resource: Fetch file from S3
        bucket = resource.config_json.get("bucket")
        key = resource.config_json.get("key")
        if not bucket or not key:
            raise ValueError(
                f"Resource '{resource.name}' missing 'bucket' or 'key' in config_json"
            )

        try:
            import boto3
            from botocore.exceptions import ClientError

            # Get AWS credentials from secret_ref if provided
            aws_access_key_id = None
            aws_secret_access_key = None
            aws_region = resource.config_json.get("region", "us-east-1")

            if resource.secret_ref:
                try:
                    secretstore = get_secretstore()
                    secret_value = secretstore.get_secret(resource.secret_ref, check_permissions=False)
                    # Assume secret_value is JSON with access_key_id and secret_access_key
                    import json

                    creds = json.loads(secret_value)
                    aws_access_key_id = creds.get("access_key_id")
                    aws_secret_access_key = creds.get("secret_access_key")
                    aws_region = creds.get("region", aws_region)
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve AWS credentials for resource '{resource.name}': {e}",
                        extra={"resource_id": str(resource.id)},
                    )
                    raise ValueError(f"Failed to retrieve AWS credentials: {e}") from e

            # Create S3 client
            s3_kwargs = {"region_name": aws_region}
            if aws_access_key_id and aws_secret_access_key:
                s3_kwargs["aws_access_key_id"] = aws_access_key_id
                s3_kwargs["aws_secret_access_key"] = aws_secret_access_key

            s3_client = boto3.client("s3", **s3_kwargs)

            # Fetch object
            try:
                response = s3_client.get_object(Bucket=bucket, Key=key)
                content = response["Body"].read().decode("utf-8")

                # Redact and truncate
                content = _redact_secrets(content)
                content, truncated = _truncate_content(content)
                if truncated:
                    logger.warning(
                        f"Resource '{resource.name}' content truncated",
                        extra={"resource_id": str(resource.id), "bucket": bucket, "key": key},
                    )
            except ClientError as e:
                logger.error(
                    f"Failed to fetch S3 object for resource '{resource.name}': {e}",
                    extra={"resource_id": str(resource.id), "bucket": bucket, "key": key},
                )
                raise ValueError(f"Failed to fetch S3 object: {e}") from e

        except ImportError:
            raise ValueError("boto3 is required for S3 resources. Install with: pip install boto3")
        except Exception as e:
            logger.error(
                f"Failed to fetch S3 resource '{resource.name}': {e}",
                extra={"resource_id": str(resource.id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to fetch S3 resource: {e}") from e

    elif resource.type == "file":
        # File resource: Read file from filesystem
        file_path = resource.config_json.get("path")
        if not file_path:
            raise ValueError(f"Resource '{resource.name}' missing 'path' in config_json")

        # Security: Validate path is within allowed directory
        import os
        from pathlib import Path

        # Get allowed base directory from config or use current directory
        allowed_base = resource.config_json.get("base_dir", os.getcwd())
        allowed_base = Path(allowed_base).resolve()

        file_path_obj = Path(file_path)
        if not file_path_obj.is_absolute():
            file_path_obj = allowed_base / file_path_obj

        # Resolve to absolute path and check it's within allowed_base
        try:
            resolved_path = file_path_obj.resolve()
            if not str(resolved_path).startswith(str(allowed_base.resolve())):
                raise ValueError(
                    f"File path '{file_path}' is outside allowed directory '{allowed_base}'"
                )
        except (ValueError, OSError) as e:
            logger.error(
                f"Invalid file path for resource '{resource.name}': {e}",
                extra={"resource_id": str(resource.id), "file_path": file_path},
            )
            raise ValueError(f"Invalid file path: {e}") from e

        # Read file
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Redact and truncate
            content = _redact_secrets(content)
            content, truncated = _truncate_content(content)
            if truncated:
                logger.warning(
                    f"Resource '{resource.name}' content truncated",
                    extra={"resource_id": str(resource.id), "file_path": str(resolved_path)},
                )
        except FileNotFoundError:
            raise ValueError(f"File not found: {resolved_path}")
        except PermissionError:
            raise ValueError(f"Permission denied reading file: {resolved_path}")
        except Exception as e:
            logger.error(
                f"Failed to read file for resource '{resource.name}': {e}",
                extra={"resource_id": str(resource.id), "file_path": str(resolved_path)},
                exc_info=True,
            )
            raise ValueError(f"Failed to read file: {e}") from e

    else:
        raise ValueError(f"Unknown resource type: {resource.type}")

    if content is None:
        raise ValueError(f"Failed to fetch content for resource '{resource.name}'")

    # Audit logging
    if agent:
        log_security_event(
            organization_id=str(resource.organization.id),
            event_type="resource_read",
            event_data={
                "resource_id": str(resource.id),
                "resource_name": resource.name,
                "resource_type": resource.type,
                "agent_id": str(agent.id),
            },
        )

    return content


def render_prompt(
    prompt: Prompt, variables: dict[str, Any], agent: Agent | None = None
) -> dict[str, list[dict[str, str]]]:
    """
    Render prompt templates with variables.

    Args:
        prompt: Prompt instance
        variables: Input variables dictionary
        agent: Optional agent instance for audit logging

    Returns:
        Dictionary with "messages" list: [{"role": "system", "content": "..."}, ...]

    Raises:
        ValueError: If input validation fails or template rendering fails
    """
    # Validate input against schema
    if prompt.input_schema:
        try:
            jsonschema.validate(instance=variables, schema=prompt.input_schema)
        except jsonschema.ValidationError as e:
            error_path = ".".join(str(p) for p in e.path) if e.path else "root"
            raise ValueError(
                f"Input validation failed for prompt '{prompt.name}': "
                f"Field '{error_path}': {e.message}"
            ) from e

    messages = []

    # Render system template if present
    if prompt.template_system:
        try:
            template = jinja_env.from_string(prompt.template_system)
            system_content = template.render(**variables)
            # Redact secrets
            system_content = _redact_secrets(system_content)
            messages.append({"role": "system", "content": system_content})
        except Exception as e:
            logger.error(
                f"Failed to render system template for prompt '{prompt.name}': {e}",
                extra={"prompt_id": str(prompt.id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to render system template: {e}") from e

    # Render user template if present
    if prompt.template_user:
        try:
            template = jinja_env.from_string(prompt.template_user)
            user_content = template.render(**variables)
            # Redact secrets
            user_content = _redact_secrets(user_content)
            messages.append({"role": "user", "content": user_content})
        except Exception as e:
            logger.error(
                f"Failed to render user template for prompt '{prompt.name}': {e}",
                extra={"prompt_id": str(prompt.id)},
                exc_info=True,
            )
            raise ValueError(f"Failed to render user template: {e}") from e

    if not messages:
        raise ValueError(f"Prompt '{prompt.name}' has no templates defined")

    # Audit logging
    if agent:
        log_security_event(
            organization_id=str(prompt.organization.id),
            event_type="prompt_invoked",
            event_data={
                "prompt_id": str(prompt.id),
                "prompt_name": prompt.name,
                "agent_id": str(agent.id),
            },
        )

    return {"messages": messages}

