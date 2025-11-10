"""
Unified error schema for MCP Fabric.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class MCPError(Exception):
    """Base exception for MCP Fabric errors."""

    def __init__(
        self,
        error_code: str,
        error_description: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        extra: dict[str, Any] | None = None,
    ):
        self.error_code = error_code
        self.error_description = error_description
        self.http_status = http_status
        self.extra = extra or {}
        super().__init__(error_description)


def mcp_error_response(
    error_code: str,
    error_description: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a unified error response dictionary.

    Args:
        error_code: Machine-readable error code (e.g., "invalid_token", "missing_scope")
        error_description: Human-readable error description
        http_status: HTTP status code
        extra: Additional fields for the response

    Returns:
        Error response dictionary in unified format
    """
    response = {
        "error": error_code,
        "error_description": error_description,
    }
    if extra:
        response.update(extra)
    return response


def raise_mcp_http_exception(
    error_code: str,
    error_description: str,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """
    Create an HTTPException with unified error schema.

    Args:
        error_code: Machine-readable error code
        error_description: Human-readable error description
        http_status: HTTP status code
        headers: Additional HTTP headers (e.g., WWW-Authenticate)

    Returns:
        HTTPException with unified detail format
    """
    detail = mcp_error_response(error_code, error_description)
    return HTTPException(
        status_code=http_status,
        detail=detail,
        headers=headers or {},
    )


# Standard error codes
class ErrorCodes:
    """Standard error codes for MCP Fabric."""

    # Authentication errors (401)
    INVALID_TOKEN = "invalid_token"
    EXPIRED_TOKEN = "expired_token"
    MISSING_TOKEN = "missing_token"
    INVALID_ISSUER = "invalid_issuer"
    INVALID_AUDIENCE = "invalid_audience"
    INVALID_SIGNATURE = "invalid_signature"
    MISSING_SCOPE = "missing_scope"
    INSUFFICIENT_SCOPE = "insufficient_scope"

    # Authorization errors (403)
    FORBIDDEN = "forbidden"
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    ORG_MISMATCH = "org_mismatch"
    ENV_MISMATCH = "env_mismatch"

    # Validation errors (400)
    INVALID_REQUEST = "invalid_request"
    MISSING_TOOL_NAME = "missing_tool_name"
    INVALID_SCHEMA = "invalid_schema"

    # Not found errors (404)
    TOOL_NOT_FOUND = "tool_not_found"
    ORGANIZATION_NOT_FOUND = "organization_not_found"
    ENVIRONMENT_NOT_FOUND = "environment_not_found"

    # Server errors (500)
    EXECUTION_FAILED = "execution_failed"
    INTERNAL_ERROR = "internal_error"

    # Resource/Prompt specific
    RESOURCE_NOT_FOUND = "resource_not_found"
    PROMPT_NOT_FOUND = "prompt_not_found"

